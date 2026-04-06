/**
 * Fetch JS-rendered pages (OpenAI, DeepMind blogs) using Playwright.
 * Updates the articles-crawl-bulk.json with full_content for previously failed items.
 *
 * Usage: bun run packages/crawler/src/playwright-fetcher.ts
 */

import { readFileSync, writeFileSync } from "fs";
import { chromium } from "playwright";

const INPUT = "data/articles-crawl-bulk.json";
const JS_DOMAINS = ["openai.com", "deepmind.google", "chat.openai.com", "beta.openai.com", "community.openai.com", "blog.gopenai.com"];

function getDomain(url: string): string {
  try { return new URL(url).hostname.replace("www.", ""); } catch { return ""; }
}

function needsPlaywright(url: string): boolean {
  const domain = getDomain(url);
  return JS_DOMAINS.some(d => domain.includes(d));
}

async function main() {
  const data = JSON.parse(readFileSync(INPUT, "utf-8"));
  const items = data.items as any[];

  const targets = items.filter(i =>
    (!i.full_content || i.full_content.length < 200) && needsPlaywright(i.url)
  );

  console.log(`Found ${targets.length} JS-rendered pages to fetch\n`);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
  });

  let fixed = 0;

  for (let i = 0; i < targets.length; i++) {
    const item = targets[i];
    console.log(`[${i + 1}/${targets.length}] ${item.url.substring(0, 70)}...`);

    const page = await context.newPage();
    try {
      await page.goto(item.url, { waitUntil: "domcontentloaded", timeout: 20000 });

      // Wait for content to render
      await page.waitForTimeout(2000);

      // Extract text content from main/article area
      const content = await page.evaluate(() => {
        const el = document.querySelector("article") ||
          document.querySelector("main") ||
          document.querySelector('[class*="content"]') ||
          document.querySelector('[class*="post"]') ||
          document.body;
        return el?.innerText ?? "";
      });

      if (content && content.length > 200) {
        item.full_content = content.slice(0, 50000);
        fixed++;
        console.log(`  -> ${content.length} chars`);
      } else {
        console.log(`  -> too short (${content?.length ?? 0} chars)`);
      }
    } catch (e) {
      console.log(`  -> error: ${e}`);
    } finally {
      await page.close();
    }
  }

  await browser.close();

  // Save updated data
  writeFileSync(INPUT, JSON.stringify(data, null, 2));

  console.log(`\nFixed: ${fixed}/${targets.length}`);

  const totalSuccess = items.filter(i => i.full_content && i.full_content.length >= 200).length;
  console.log(`Total with full_content: ${totalSuccess}/${items.length} (${(totalSuccess / items.length * 100).toFixed(1)}%)`);
}

main().catch(e => { console.error(e); process.exit(1); });
