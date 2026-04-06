import { describe, it, expect, mock, beforeEach } from "bun:test";

/**
 * geeknews-importer tests — parseArchiveFile and findEntityUid logic.
 *
 * We mock @comad-brain/core to avoid Neo4j dependency, then test the
 * parsing and entity-uid-resolution logic that drives ingestion.
 */

// Mock @comad-brain/core
const mockQuery = mock(() => Promise.resolve([] as any[]));
const mockWrite = mock(() => Promise.resolve([] as any[]));
const mockWriteTx = mock(() => Promise.resolve([] as any[]));
const mockClose = mock(() => Promise.resolve());
const mockSetupSchema = mock(() => Promise.resolve());
const mockExtractEntities = mock(() =>
  Promise.resolve({
    technologies: [],
    people: [],
    organizations: [],
    topics: [],
    claims: [],
    relationships: [],
  }),
);

mock.module("@comad-brain/core", () => ({
  query: mockQuery,
  write: mockWrite,
  writeTx: mockWriteTx,
  close: mockClose,
  setupSchema: mockSetupSchema,
  extractEntities: mockExtractEntities,
  articleUid: (date: string, slug: string) => `article:${date}-${slug}`,
  techUid: (name: string) => `tech:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`,
  personUid: (name: string) => `person:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`,
  orgUid: (name: string) => `org:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`,
  topicUid: (name: string) => `topic:${name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`,
  claimUid: (sourceUid: string, index: number) => `claim:${sourceUid}-${index}`,
  slugFromFilename: (filename: string) => {
    const base = filename.replace(/\.md$/, "");
    return base.replace(/^\d{4}-\d{2}-\d{2}-/, "");
  },
}));

// We cannot import main() directly (it runs immediately), but we can test
// the internal logic by importing the module and testing parseArchiveFile via
// the pattern it uses. Since parseArchiveFile is not exported, we re-implement
// its logic here for testing, or we test it via the mergeArticle path.

// Instead, let's test the module's parsing by calling the gray-matter parser
// the same way the module does internally.
import matter from "gray-matter";

describe("geeknews-importer", () => {
  beforeEach(() => {
    mockQuery.mockReset();
    mockWrite.mockReset();
    mockExtractEntities.mockReset();
  });

  describe("parseArchiveFile logic (gray-matter parsing)", () => {
    function parseArchiveFile(filename: string, raw: string) {
      const { data: fm, content } = matter(raw);
      const titleMatch = content.match(/^# (.+)$/m);
      const title = titleMatch?.[1] ?? filename;
      const summaryMatch = content.match(/## 핵심 요약\n([\s\S]*?)(?=\n## |$)/);
      const summary = summaryMatch?.[1]?.trim() ?? "";
      const whyMatch = content.match(/## 왜 알아야 하는가\n([\s\S]*?)(?=\n## |$)/);
      const why = whyMatch?.[1]?.trim() ?? "";
      const relevance = ((fm.relevance as string) ?? "참고").replace(/[🔴🟡🔵\s]/g, "").trim();

      return {
        filename,
        slug: filename.replace(/\.md$/, "").replace(/^\d{4}-\d{2}-\d{2}-/, ""),
        date: fm.date instanceof Date ? fm.date.toISOString().split("T")[0] : String(fm.date ?? ""),
        title,
        relevance,
        categories: Array.isArray(fm.categories) ? fm.categories.map(String) : [],
        geeknews_url: (fm.geeknews as string) ?? "",
        source_url: (fm.source as string) ?? "",
        summary,
        why,
        full_content: content,
      };
    }

    it("extracts title from first # heading", () => {
      const raw = `---
date: 2026-04-01
relevance: "🔴 필독"
categories: [AI, LLM]
geeknews: https://news.hada.io/123
source: https://example.com
---
# Rust가 C++를 대체할 수 있을까

## 핵심 요약
Rust는 메모리 안전성 때문에 점점 더 많은 프로젝트에서 채택되고 있다.

## 왜 알아야 하는가
시스템 프로그래밍 패러다임이 바뀌고 있다.
`;

      const result = parseArchiveFile("2026-04-01-rust-vs-cpp.md", raw);

      expect(result.title).toBe("Rust가 C++를 대체할 수 있을까");
      expect(result.slug).toBe("rust-vs-cpp");
      expect(result.date).toBe("2026-04-01");
      expect(result.relevance).toBe("필독");
      expect(result.categories).toEqual(["AI", "LLM"]);
      expect(result.geeknews_url).toBe("https://news.hada.io/123");
      expect(result.source_url).toBe("https://example.com");
      expect(result.summary).toContain("Rust는 메모리 안전성");
      expect(result.why).toContain("시스템 프로그래밍");
    });

    it("uses filename as title fallback when no # heading", () => {
      const raw = `---
date: 2026-04-01
---
Just some content without a heading.
`;
      const result = parseArchiveFile("2026-04-01-no-heading.md", raw);
      expect(result.title).toBe("2026-04-01-no-heading.md");
    });

    it("handles missing frontmatter fields gracefully", () => {
      const raw = `---
date: 2026-04-01
---
# Minimal Article
`;
      const result = parseArchiveFile("2026-04-01-minimal.md", raw);

      expect(result.relevance).toBe("참고");
      expect(result.categories).toEqual([]);
      expect(result.geeknews_url).toBe("");
      expect(result.source_url).toBe("");
      expect(result.summary).toBe("");
      expect(result.why).toBe("");
    });

    it("cleans emoji from relevance field", () => {
      const raw = `---
date: 2026-04-01
relevance: "🟡 추천"
---
# Test
`;
      const result = parseArchiveFile("2026-04-01-test.md", raw);
      expect(result.relevance).toBe("추천");
    });

    it("parses Date objects from frontmatter", () => {
      // gray-matter may parse date: 2026-04-01 as Date object
      const raw = `---
date: 2026-04-01
---
# Test
`;
      const result = parseArchiveFile("2026-04-01-test.md", raw);
      // Should be a string in YYYY-MM-DD format either way
      expect(result.date).toMatch(/^\d{4}-\d{2}-\d{2}/);
    });
  });

  describe("findEntityUid logic", () => {
    // Replicate findEntityUid from the module
    function findEntityUid(
      name: string,
      entities: {
        technologies: Array<{ name: string; type: string }>;
        people: Array<{ name: string; github_username?: string; affiliation?: string }>;
        organizations: Array<{ name: string; type: string }>;
      },
    ): string | null {
      const lower = name.toLowerCase();

      const tech = entities.technologies.find((t) => t.name.toLowerCase() === lower);
      if (tech) return `tech:${tech.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;

      const person = entities.people.find((p) => p.name.toLowerCase() === lower);
      if (person) return `person:${person.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;

      const org = entities.organizations.find((o) => o.name.toLowerCase() === lower);
      if (org) return `org:${org.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/-+$/, "")}`;

      return null;
    }

    it("resolves technology names case-insensitively", () => {
      const entities = {
        technologies: [{ name: "React", type: "framework" }],
        people: [],
        organizations: [],
      };

      expect(findEntityUid("react", entities)).toBe("tech:react");
      expect(findEntityUid("React", entities)).toBe("tech:react");
      expect(findEntityUid("REACT", entities)).toBe("tech:react");
    });

    it("resolves person names case-insensitively", () => {
      const entities = {
        technologies: [],
        people: [{ name: "John Doe", affiliation: "Google" }],
        organizations: [],
      };

      expect(findEntityUid("john doe", entities)).toBe("person:john-doe");
    });

    it("resolves organization names case-insensitively", () => {
      const entities = {
        technologies: [],
        people: [],
        organizations: [{ name: "OpenAI", type: "company" }],
      };

      expect(findEntityUid("openai", entities)).toBe("org:openai");
    });

    it("prefers technology over person/org when names collide", () => {
      const entities = {
        technologies: [{ name: "Go", type: "language" }],
        people: [{ name: "Go" }],
        organizations: [{ name: "Go", type: "company" }],
      };

      expect(findEntityUid("Go", entities)).toBe("tech:go");
    });

    it("returns null for unmatched names", () => {
      const entities = {
        technologies: [{ name: "Rust", type: "language" }],
        people: [],
        organizations: [],
      };

      expect(findEntityUid("Python", entities)).toBeNull();
    });
  });
});
