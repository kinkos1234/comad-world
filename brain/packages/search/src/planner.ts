/**
 * Adoption Planner — powered by unified pattern registry (Hickey improvement)
 *
 * Reads reference card patterns and maps them to concrete file changes
 * using the single source of truth in patterns.ts.
 */

import { startTimer, recordTiming } from "@comad-brain/core";
import { getPatternDef, PATTERN_REGISTRY } from "./patterns.js";
import type { ReferenceCard } from "./types.js";

export interface FileChange {
  file: string;
  action: "create" | "modify" | "delete";
  description: string;
  pattern_source: string;
}

export interface Risk {
  description: string;
  severity: "low" | "medium" | "high";
  mitigation: string;
}

export interface AdoptionPlan {
  reference: ReferenceCard;
  summary: string;
  changes: FileChange[];
  risks: Risk[];
  effort: "trivial" | "moderate" | "significant";
  target_modules: string[];
  approved: boolean;
  created_at: string;
}

function estimateEffort(changes: FileChange[]): "trivial" | "moderate" | "significant" {
  if (changes.length === 0) return "trivial";
  if (changes.length <= 2) return "moderate";
  return "significant";
}

/**
 * Generate adoption plan for a reference card
 */
/**
 * Internalization Principle (내재화 원칙)
 *
 * All adoptions MUST follow these rules:
 * ✅ Learn patterns/algorithms and reimplement in our code
 * ✅ Borrow ideas, implement ourselves
 * ✅ Allowed: infra deps already in stack (Neo4j, Bun, Python)
 * ❌ No new npm/pip packages
 * ❌ No external API/SaaS dependencies
 * ❌ No framework additions/replacements
 *
 * Plans that violate these rules are auto-rejected.
 */
const DEPENDENCY_KEYWORDS = [
  "npm install", "pip install", "bun add", "yarn add",
  "package.json", "requirements.txt", "import from",
  "add_dependency", "new dependency",
];

function violatesInternalization(changes: FileChange[]): boolean {
  return changes.some(c =>
    DEPENDENCY_KEYWORDS.some(kw =>
      c.description.toLowerCase().includes(kw)
    ) || c.action === "create" && c.file.includes("package.json")
  );
}

export function createAdoptionPlan(card: ReferenceCard): AdoptionPlan {
  const elapsed = startTimer();

  const changes: FileChange[] = [];
  const risks: Risk[] = [];
  const seen = new Set<string>();

  for (const patternName of card.extracted_patterns) {
    const def = getPatternDef(patternName);
    if (!def || seen.has(def.file)) continue;
    seen.add(def.file);

    changes.push({
      file: def.file,
      action: def.action,
      description: def.description(card.repo.candidate.name),
      pattern_source: patternName,
    });

    if (def.risk) {
      risks.push(def.risk);
    }
  }

  // Internalization gate: reject plans that add external dependencies
  if (violatesInternalization(changes)) {
    risks.push({
      description: "내재화 원칙 위반: 외부 의존성 추가 감지. 패턴만 학습하여 자체 구현해야 함.",
      severity: "high",
      mitigation: "패키지 설치 대신 핵심 알고리즘을 직접 구현. 참조 코드를 읽고 패턴만 차용.",
    });
  }

  if (changes.length === 0) {
    risks.push({
      description: "참조만 하고 적용할 패턴이 없을 수 있음",
      severity: "low",
      mitigation: "reference card를 study로 보관. 향후 필요 시 재검토",
    });
  }

  const plan: AdoptionPlan = {
    reference: card,
    summary: `${card.repo.candidate.name}에서 ${changes.length}개 패턴을 ${card.applicable_to.join(", ")}에 적용`,
    changes,
    risks,
    effort: estimateEffort(changes),
    target_modules: card.applicable_to,
    approved: false,
    created_at: new Date().toISOString(),
  };

  recordTiming("search:plan", elapsed());
  return plan;
}

/**
 * Format plan as readable text for user approval
 */
export function formatPlan(plan: AdoptionPlan): string {
  const lines: string[] = [
    `## Adoption Plan: ${plan.reference.repo.candidate.name}`,
    ``,
    `**Summary:** ${plan.summary}`,
    `**Effort:** ${plan.effort}`,
    `**Target:** ${plan.target_modules.join(", ")}`,
    ``,
  ];

  if (plan.changes.length > 0) {
    lines.push(`### Changes (${plan.changes.length})`);
    for (const c of plan.changes) {
      lines.push(`- **${c.action}** \`${c.file}\``);
      lines.push(`  ${c.description}`);
      lines.push(`  Pattern: ${c.pattern_source}`);
    }
    lines.push(``);
  }

  if (plan.risks.length > 0) {
    lines.push(`### Risks`);
    for (const r of plan.risks) {
      lines.push(`- [${r.severity.toUpperCase()}] ${r.description}`);
      lines.push(`  Mitigation: ${r.mitigation}`);
    }
    lines.push(``);
  }

  return lines.join("\n");
}
