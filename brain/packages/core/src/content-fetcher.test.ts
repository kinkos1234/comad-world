import { describe, it, expect, mock, beforeEach } from "bun:test";

// Save original fetch
const originalFetch = globalThis.fetch;

// We need to mock global fetch to test fetchContent / htmlToText indirectly
const mockFetch = mock(() => Promise.resolve(new Response("")));

beforeEach(() => {
  mockFetch.mockReset();
  globalThis.fetch = mockFetch as any;
});

// Import after setup (no module mocking needed — we mock global fetch)
const { fetchContent, fetchContents } = await import("./content-fetcher.js");

// Helper to create a mock Response
function htmlResponse(body: string, contentType = "text/html"): Response {
  return new Response(body, {
    status: 200,
    headers: { "content-type": contentType },
  });
}

describe("content-fetcher", () => {
  describe("fetchContent — HTML cleanup", () => {
    it("strips script tags", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          '<div class="content"><p>This is meaningful content that is long enough.</p><script>alert("xss")</script></div>',
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).not.toContain("alert");
      expect(result).not.toContain("<script>");
    });

    it("strips style tags", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          '<div class="content"><p>This is meaningful content that is quite long enough.</p><style>.hidden{display:none}</style></div>',
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).not.toContain("display:none");
      expect(result).not.toContain("<style>");
    });

    it("strips nav, footer, header, aside, noscript tags", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          `<nav>Menu items here in nav block</nav>
           <header>Site header content block</header>
           <article><p>This is the real article content that we actually want to keep.</p></article>
           <aside>Sidebar content that should be removed here.</aside>
           <footer>Copyright footer text here too.</footer>
           <noscript>Enable JS please for this content.</noscript>`,
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).not.toContain("Menu items");
      expect(result).not.toContain("Site header");
      expect(result).not.toContain("Sidebar content");
      expect(result).not.toContain("Copyright footer");
      expect(result).not.toContain("Enable JS");
      expect(result).toContain("real article content");
    });

    it("strips HTML comments", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          '<div class="content"><p>Visible content that should appear in output here.</p><!-- This is a secret comment --></div>',
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).not.toContain("secret comment");
    });
  });

  describe("fetchContent — article content extraction", () => {
    it("extracts content from <article> tag", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          `<body>
            <div>Noise that should not appear in the output.</div>
            <article><p>This is the article content we want to extract from the page.</p></article>
           </body>`,
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).toContain("article content we want");
    });

    it("extracts content from <main> tag when no article", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          `<body>
            <div>Some random noise content here outside main block.</div>
            <main><p>This is the main content section of the page we want.</p></main>
           </body>`,
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).toContain("main content section");
    });

    it("extracts content from div.content", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          `<body>
            <div>Unwanted noise text that should not be included here.</div>
            <div class="content"><p>This is the content div section with real text in it.</p></div>
           </body>`,
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).toContain("content div section");
    });
  });

  describe("fetchContent — HTML entity decoding", () => {
    it("decodes common HTML entities", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          '<article><p>Apples &amp; oranges are &lt;great&gt; fruits &quot;indeed&quot; they&#39;re good and &nbsp;healthy</p></article>',
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).toContain("Apples & oranges");
      expect(result).toContain("<great>");
      expect(result).toContain('"indeed"');
      expect(result).toContain("they're");
    });

    it("decodes hex numeric entities (&#x...)", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          '<article><p>Copyright &#x00A9; 2026 dash &#x2014; em dash symbol here.</p></article>',
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).toContain("\u00A9"); // ©
      expect(result).toContain("\u2014"); // —
    });

    it("decodes decimal numeric entities (&#...)", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          '<article><p>Check mark &#10004; and heart &#9829; symbols are decoded here.</p></article>',
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).toContain(String.fromCharCode(10004)); // ✔
      expect(result).toContain(String.fromCharCode(9829)); // ♥
    });
  });

  describe("fetchContent — block elements to newlines", () => {
    it("converts block elements to newlines", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          '<article><p>First paragraph with enough content here.</p><p>Second paragraph with enough content here.</p><h2>Heading text that is long enough for filter.</h2></article>',
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).toContain("First paragraph");
      expect(result).toContain("Second paragraph");
      // Lines should be separated (not concatenated)
      const lines = result!.split("\n").filter((l: string) => l.trim());
      expect(lines.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe("fetchContent — short line filtering", () => {
    it("filters lines shorter than 20 chars (unless list-like)", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          `<article>
            <p>Short</p>
            <p>This is a long enough paragraph that should be kept in the output.</p>
            <p>Tiny</p>
            <p>Another sufficiently long paragraph that passes the filter check.</p>
          </article>`,
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).not.toContain("Short");
      expect(result).not.toContain("Tiny");
      expect(result).toContain("long enough paragraph");
      expect(result).toContain("sufficiently long paragraph");
    });

    it("keeps short lines that look like list items", async () => {
      mockFetch.mockResolvedValue(
        htmlResponse(
          `<article>
            <p>- list item here</p>
            <p>* starred item</p>
            <p>1. numbered item</p>
            <p>This is a long enough paragraph that should definitely be kept.</p>
          </article>`,
        ),
      );

      const result = await fetchContent("http://example.com");
      expect(result).toContain("- list item here");
      expect(result).toContain("* starred item");
      expect(result).toContain("1. numbered item");
    });
  });

  describe("fetchContent — MAX_CONTENT_LENGTH truncation", () => {
    it("truncates content to 50KB", async () => {
      const longContent = "A".repeat(60_000);
      mockFetch.mockResolvedValue(
        htmlResponse(`<article><p>${longContent}</p></article>`),
      );

      const result = await fetchContent("http://example.com");
      expect(result!.length).toBeLessThanOrEqual(50_000);
    });
  });

  describe("fetchContent — text/plain passthrough", () => {
    it("returns plain text content directly (sliced to max)", async () => {
      const plainText = "This is plain text content that should be returned as-is.";
      mockFetch.mockResolvedValue(
        new Response(plainText, {
          status: 200,
          headers: { "content-type": "text/plain; charset=utf-8" },
        }),
      );

      const result = await fetchContent("http://example.com");
      expect(result).toBe(plainText);
    });
  });

  describe("fetchContent — error handling", () => {
    it("returns null on fetch failure", async () => {
      mockFetch.mockRejectedValue(new Error("Network error"));

      const result = await fetchContent("http://example.com");
      expect(result).toBeNull();
    });

    it("returns null on non-OK response", async () => {
      mockFetch.mockResolvedValue(new Response("Not Found", { status: 404 }));

      const result = await fetchContent("http://example.com");
      expect(result).toBeNull();
    });

    it("returns null on empty content", async () => {
      // All lines are short, so they all get filtered → empty result → null
      mockFetch.mockResolvedValue(htmlResponse("<p>X</p><p>Y</p>"));

      const result = await fetchContent("http://example.com");
      expect(result).toBeNull();
    });
  });

  describe("fetchContents — parallel fetching", () => {
    it("fetches all URLs and returns a Map", async () => {
      (globalThis as any).fetch = (url: any) => {
        const urlStr = typeof url === "string" ? url : url.toString();
        return Promise.resolve(
          htmlResponse(
            `<article><p>Content from ${urlStr} which is long enough to keep.</p></article>`,
          ),
        );
      };

      const urls = ["http://a.com", "http://b.com", "http://c.com"];
      const results = await fetchContents(urls);

      expect(results.size).toBe(3);
      expect(results.get("http://a.com")).toContain("Content from http://a.com");
      expect(results.get("http://b.com")).toContain("Content from http://b.com");
      expect(results.get("http://c.com")).toContain("Content from http://c.com");
    });

    it("handles mixed success and failure", async () => {
      let callCount = 0;
      mockFetch.mockImplementation(() => {
        callCount++;
        if (callCount === 2) {
          return Promise.reject(new Error("fail"));
        }
        return Promise.resolve(
          htmlResponse(
            `<article><p>Some valid content that is long enough to pass filter.</p></article>`,
          ),
        );
      });

      const urls = ["http://a.com", "http://fail.com", "http://c.com"];
      const results = await fetchContents(urls);

      expect(results.size).toBe(3);
      expect(results.get("http://fail.com")).toBeNull();
    });

    it("respects concurrency parameter", async () => {
      let concurrent = 0;
      let maxConcurrent = 0;

      mockFetch.mockImplementation(async () => {
        concurrent++;
        maxConcurrent = Math.max(maxConcurrent, concurrent);
        await new Promise((r) => setTimeout(r, 10));
        concurrent--;
        return htmlResponse(
          `<article><p>Content that is sufficiently long enough to pass the filter.</p></article>`,
        );
      });

      const urls = Array.from({ length: 6 }, (_, i) => `http://site${i}.com`);
      await fetchContents(urls, 2);

      // With concurrency=2, max concurrent should be at most 2
      expect(maxConcurrent).toBeLessThanOrEqual(2);
    });
  });
});
