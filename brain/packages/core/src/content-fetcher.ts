/**
 * Fetch and extract article/paper text content from URLs.
 * Supports HTML pages and PDF parsing via opendataloader-pdf.
 * No LLM API calls needed — pure HTTP + text processing.
 */

import { existsSync, readFileSync, mkdirSync, unlinkSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";

const FETCH_TIMEOUT = 10_000; // 10 seconds
const PDF_TIMEOUT = 120_000; // 2 minutes for PDF parsing
const MAX_CONTENT_LENGTH = 50_000; // 50KB text limit
const MIN_USEFUL_CONTENT = 500;
const BROWSE_CLI = join(import.meta.dir, "../../../../browse/src/cli.ts");
const BROWSE_CLI_WORLD = join(import.meta.dir, "../../../comad-world/browse/src/cli.ts");

/**
 * Fetch a URL and extract readable text content.
 * Returns null if the URL is unreachable or content is empty.
 */
export async function fetchContent(url: string, useBrowse = true): Promise<string | null> {
  const native = await fetchContentNative(url);
  if (native && native.length >= MIN_USEFUL_CONTENT) return native;

  if (useBrowse) {
    const rendered = await fetchContentViaBrowse(url);
    if (rendered && rendered.length >= MIN_USEFUL_CONTENT) return rendered;
  }

  return native;
}

async function fetchContentNative(url: string): Promise<string | null> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT);

    const response = await fetch(url, {
      signal: controller.signal,
      headers: {
        "User-Agent": "Mozilla/5.0 (compatible; KnowledgeOntologyBot/1.0)",
        "Accept": "text/html,application/xhtml+xml,text/plain",
      },
      redirect: "follow",
    });

    clearTimeout(timeout);

    if (!response.ok) return null;

    const contentType = response.headers.get("content-type") ?? "";
    const html = await response.text();

    if (contentType.includes("text/plain")) {
      return html.slice(0, MAX_CONTENT_LENGTH);
    }

    return htmlToText(html);
  } catch (e) {
    return null;
  }
}

async function fetchContentViaBrowse(url: string): Promise<string | null> {
  try {
    const cli = existsSync(BROWSE_CLI) ? BROWSE_CLI : existsSync(BROWSE_CLI_WORLD) ? BROWSE_CLI_WORLD : null;
    if (!cli) return null;

    const gotoProc = Bun.spawn(["bun", "run", cli, "goto", url], { stdout: "pipe", stderr: "pipe" });
    const gotoExit = await Promise.race([
      gotoProc.exited,
      new Promise<number>((_, reject) => setTimeout(() => { gotoProc.kill(); reject(new Error("timeout")); }, 15_000)),
    ]);
    if (gotoExit !== 0) return null;

    const textProc = Bun.spawn(["bun", "run", cli, "text"], { stdout: "pipe", stderr: "pipe" });
    const textExit = await Promise.race([
      textProc.exited,
      new Promise<number>((_, reject) => setTimeout(() => { textProc.kill(); reject(new Error("timeout")); }, 10_000)),
    ]);
    if (textExit !== 0) return null;

    let text = await new Response(textProc.stdout).text();
    text = text.replace(/--- BEGIN UNTRUSTED EXTERNAL CONTENT ---\n?/g, "")
      .replace(/--- END UNTRUSTED EXTERNAL CONTENT ---\n?/g, "").trim();

    return text.slice(0, MAX_CONTENT_LENGTH) || null;
  } catch {
    return null;
  }
}

/**
 * Extract readable text from HTML.
 * Strips scripts, styles, nav, footer, and HTML tags.
 * Focuses on article/main content when possible.
 */
function htmlToText(html: string): string {
  let text = html;

  // Remove script, style, nav, footer, header, aside elements
  text = text.replace(/<script[\s\S]*?<\/script>/gi, "");
  text = text.replace(/<style[\s\S]*?<\/style>/gi, "");
  text = text.replace(/<nav[\s\S]*?<\/nav>/gi, "");
  text = text.replace(/<footer[\s\S]*?<\/footer>/gi, "");
  text = text.replace(/<header[\s\S]*?<\/header>/gi, "");
  text = text.replace(/<aside[\s\S]*?<\/aside>/gi, "");
  text = text.replace(/<noscript[\s\S]*?<\/noscript>/gi, "");
  text = text.replace(/<!--[\s\S]*?-->/g, "");

  // Try to extract just the main content area
  const articleMatch = text.match(/<article[\s\S]*?<\/article>/i)
    ?? text.match(/<main[\s\S]*?<\/main>/i)
    ?? text.match(/<div[^>]*class="[^"]*(?:content|article|post|entry|body)[^"]*"[\s\S]*?<\/div>/i);

  if (articleMatch) {
    text = articleMatch[0];
  }

  // Convert block elements to newlines
  text = text.replace(/<\/?(p|div|br|h[1-6]|li|tr|blockquote|pre|section)[^>]*>/gi, "\n");

  // Remove remaining HTML tags
  text = text.replace(/<[^>]+>/g, "");

  // Decode HTML entities
  text = text
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, " ")
    .replace(/&#x([0-9a-f]+);/gi, (_, hex) => String.fromCharCode(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => String.fromCharCode(parseInt(dec)));

  // Clean up whitespace
  text = text
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .join("\n");

  // Remove very short lines (likely navigation/menu items)
  const lines = text.split("\n");
  const meaningfulLines = lines.filter((line) => line.length > 20 || line.match(/^[#\-*]|^\d+\./));

  const result = meaningfulLines.join("\n").trim();
  return result.slice(0, MAX_CONTENT_LENGTH) || null as any;
}

/**
 * Fetch deep content from an arxiv paper PDF via opendataloader-pdf.
 * Downloads the PDF, parses to markdown, returns full body text.
 * Falls back to arxiv HTML version if PDF parsing fails.
 */
export async function fetchPaperContent(pdfUrl: string, arxivId?: string): Promise<string | null> {
  // Strategy: try arxiv HTML first (faster), then PDF parsing (deeper)
  if (arxivId) {
    const htmlContent = await fetchArxivHtml(arxivId);
    if (htmlContent && htmlContent.length > 5000) return htmlContent;
  }

  // Fall back to PDF parsing
  return fetchPdfContent(pdfUrl);
}

/**
 * Fetch arxiv HTML version (available for most papers since 2023).
 */
async function fetchArxivHtml(arxivId: string): Promise<string | null> {
  const url = `https://arxiv.org/html/${arxivId}`;
  try {
    const content = await fetchContent(url);
    if (content && content.length > 2000) return content;
  } catch {}
  return null;
}

/**
 * Download a PDF and parse it using opendataloader-pdf CLI.
 * Returns markdown text content.
 */
async function fetchPdfContent(pdfUrl: string): Promise<string | null> {
  const workDir = join(tmpdir(), `odl-pdf-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`);
  const pdfPath = join(workDir, "paper.pdf");
  const outDir = join(workDir, "output");

  try {
    mkdirSync(workDir, { recursive: true });
    mkdirSync(outDir, { recursive: true });

    // Download PDF — stream to disk instead of loading entire buffer into RAM
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT * 3);
    const response = await fetch(pdfUrl, {
      signal: controller.signal,
      headers: { "User-Agent": "Mozilla/5.0 (compatible; KnowledgeOntologyBot/1.0)" },
      redirect: "follow",
    });
    clearTimeout(timeout);

    if (!response.ok) return null;

    await Bun.write(pdfPath, response);

    // Parse with opendataloader-pdf
    const javaHome = "/opt/homebrew/opt/openjdk@21";
    const proc = Bun.spawn(
      ["opendataloader-pdf", "-f", "markdown", "-o", outDir, pdfPath],
      {
        env: {
          ...process.env,
          PATH: `${javaHome}/bin:${process.env.PATH}`,
          JAVA_HOME: javaHome,
        },
        stdout: "pipe",
        stderr: "pipe",
      }
    );

    const exitCode = await Promise.race([
      proc.exited,
      new Promise<number>((_, reject) =>
        setTimeout(() => { proc.kill(); reject(new Error("timeout")); }, PDF_TIMEOUT)
      ),
    ]);

    if (exitCode !== 0) return null;

    // Read the output markdown
    const mdPath = join(outDir, "paper.md");
    if (!existsSync(mdPath)) return null;

    const md = readFileSync(mdPath, "utf-8");
    return md.slice(0, MAX_CONTENT_LENGTH) || null;
  } catch {
    return null;
  } finally {
    // Cleanup temp files
    try { rmSync(workDir, { recursive: true, force: true }); } catch {}
  }
}

/**
 * Fetch content for multiple URLs in parallel with concurrency limit.
 */
export async function fetchContents(
  urls: string[],
  concurrency = 3
): Promise<Map<string, string | null>> {
  const results = new Map<string, string | null>();
  const queue = [...urls];

  async function worker() {
    while (queue.length > 0) {
      const url = queue.shift()!;
      const content = await fetchContent(url);
      results.set(url, content);
    }
  }

  const workers = Array.from({ length: Math.min(concurrency, urls.length) }, () => worker());
  await Promise.all(workers);

  return results;
}
