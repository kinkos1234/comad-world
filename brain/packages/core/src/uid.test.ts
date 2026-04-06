import { describe, it, expect } from "bun:test";

import {
  paperUid,
  repoUid,
  articleUid,
  techUid,
  personUid,
  orgUid,
  topicUid,
  crawlLogUid,
  claimUid,
  communityUid,
  metaEdgeUid,
  leverUid,
  metaLeverUid,
  slugFromFilename,
} from "./uid.js";

describe("uid", () => {
  describe("paperUid", () => {
    it("returns paper: prefix with arxiv id", () => {
      expect(paperUid("2401.12345")).toBe("paper:2401.12345");
    });

    it("preserves exact id (no normalization)", () => {
      expect(paperUid("2401.12345v2")).toBe("paper:2401.12345v2");
    });

    it("handles empty string", () => {
      expect(paperUid("")).toBe("paper:");
    });
  });

  describe("repoUid", () => {
    it("lowercases the full name", () => {
      expect(repoUid("Owner/Repo")).toBe("repo:owner/repo");
    });

    it("already lowercase stays the same", () => {
      expect(repoUid("owner/repo")).toBe("repo:owner/repo");
    });

    it("handles empty string", () => {
      expect(repoUid("")).toBe("repo:");
    });
  });

  describe("articleUid", () => {
    it("joins date and slug with dash", () => {
      expect(articleUid("2026-04-04", "test-slug")).toBe("article:2026-04-04-test-slug");
    });

    it("handles empty date and slug", () => {
      expect(articleUid("", "")).toBe("article:-");
    });
  });

  describe("techUid", () => {
    it("lowercases and replaces special chars with dashes", () => {
      expect(techUid("React.js")).toBe("tech:react-js");
    });

    it("strips trailing dashes", () => {
      expect(techUid("C++")).toBe("tech:c");
    });

    it("collapses multiple special chars into single dash", () => {
      expect(techUid("Vue.js 3")).toBe("tech:vue-js-3");
    });

    it("handles empty string", () => {
      expect(techUid("")).toBe("tech:");
    });

    it("handles all special characters", () => {
      expect(techUid("@#$%")).toBe("tech:");
    });

    it("handles spaces", () => {
      expect(techUid("Node JS")).toBe("tech:node-js");
    });
  });

  describe("personUid", () => {
    it("lowercases and replaces spaces with dashes", () => {
      expect(personUid("John Doe")).toBe("person:john-doe");
    });

    it("handles special characters", () => {
      expect(personUid("Jean-Luc O'Brien")).toBe("person:jean-luc-o-brien");
    });

    it("handles empty string", () => {
      expect(personUid("")).toBe("person:");
    });
  });

  describe("orgUid", () => {
    it("lowercases and normalizes", () => {
      expect(orgUid("OpenAI Inc.")).toBe("org:openai-inc");
    });

    it("strips trailing dashes from special char endings", () => {
      expect(orgUid("Meta!")).toBe("org:meta");
    });

    it("handles empty string", () => {
      expect(orgUid("")).toBe("org:");
    });
  });

  describe("topicUid", () => {
    it("lowercases and replaces spaces", () => {
      expect(topicUid("Machine Learning")).toBe("topic:machine-learning");
    });

    it("handles slashes and special chars", () => {
      expect(topicUid("NLP/NLU")).toBe("topic:nlp-nlu");
    });

    it("handles empty string", () => {
      expect(topicUid("")).toBe("topic:");
    });
  });

  describe("crawlLogUid", () => {
    it("joins source and date", () => {
      expect(crawlLogUid("arxiv", "2026-04-04")).toBe("crawl:arxiv-2026-04-04");
    });

    it("handles empty strings", () => {
      expect(crawlLogUid("", "")).toBe("crawl:-");
    });
  });

  describe("claimUid", () => {
    it("appends index to source uid", () => {
      expect(claimUid("paper:123", 5)).toBe("claim:paper:123-5");
    });

    it("handles zero index", () => {
      expect(claimUid("paper:abc", 0)).toBe("claim:paper:abc-0");
    });
  });

  describe("communityUid", () => {
    it("includes level and normalized name", () => {
      expect(communityUid(1, "AI Frameworks")).toBe("comm:c1-ai-frameworks");
    });

    it("handles level 0", () => {
      expect(communityUid(0, "Root")).toBe("comm:c0-root");
    });

    it("handles empty name", () => {
      expect(communityUid(2, "")).toBe("comm:c2-");
    });
  });

  describe("metaEdgeUid", () => {
    it("normalizes name", () => {
      expect(metaEdgeUid("influences")).toBe("metaedge:influences");
    });

    it("lowercases and replaces special chars", () => {
      expect(metaEdgeUid("USES_IN")).toBe("metaedge:uses-in");
    });

    it("handles empty string", () => {
      expect(metaEdgeUid("")).toBe("metaedge:");
    });
  });

  describe("leverUid", () => {
    it("normalizes name", () => {
      expect(leverUid("funding boost")).toBe("lever:funding-boost");
    });

    it("handles empty string", () => {
      expect(leverUid("")).toBe("lever:");
    });
  });

  describe("metaLeverUid", () => {
    it("normalizes name", () => {
      expect(metaLeverUid("adoption wave")).toBe("metalever:adoption-wave");
    });

    it("handles empty string", () => {
      expect(metaLeverUid("")).toBe("metalever:");
    });
  });

  describe("slugFromFilename", () => {
    it("removes date prefix and .md extension", () => {
      expect(slugFromFilename("2026-03-22-death-of-the-ide.md")).toBe("death-of-the-ide");
    });

    it("handles filename without date prefix", () => {
      expect(slugFromFilename("some-slug.md")).toBe("some-slug");
    });

    it("handles filename without .md extension", () => {
      expect(slugFromFilename("2026-01-01-hello")).toBe("hello");
    });

    it("handles only date prefix", () => {
      expect(slugFromFilename("2026-01-01-.md")).toBe("");
    });
  });
});
