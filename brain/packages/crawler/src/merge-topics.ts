/**
 * Merge fragmented Topic nodes by normalizing names and deduplicating.
 *
 * Strategy:
 * 1. Normalize: lowercase, trim, remove duplicates like "LLM" vs "Large Language Models"
 * 2. Merge Korean↔English duplicates
 * 3. Absorb singleton topics into broader categories
 * 4. Transfer all relationships from merged nodes
 *
 * Usage: bun run packages/crawler/src/merge-topics.ts
 */

import { write, close, query } from "@comad-brain/core";

// Manual merge map: source names → canonical name
const MERGE_MAP: Record<string, string> = {
  // LLM variants
  "대규모 언어 모델(LLM)": "Large Language Models",
  "대규모 언어 모델": "Large Language Models",
  "LLM": "Large Language Models",
  "LLMs": "Large Language Models",

  // AI variants
  "인공지능": "Artificial Intelligence",
  "AI": "Artificial Intelligence",
  "인공지능(AI)": "Artificial Intelligence",

  // ML variants
  "머신러닝": "Machine Learning",
  "기계학습": "Machine Learning",

  // Deep Learning
  "딥러닝": "Deep Learning",
  "심층학습": "Deep Learning",

  // NLP variants
  "자연어처리": "Natural Language Processing",
  "자연어 처리": "Natural Language Processing",
  "NLP": "Natural Language Processing",

  // Open source
  "오픈소스 AI": "Open-Source AI",
  "오픈소스": "Open Source",
  "Open Source": "Open Source",

  // RAG variants
  "RAG": "Retrieval-Augmented Generation",
  "검색 증강 생성": "Retrieval-Augmented Generation",

  // Reasoning
  "추론": "Reasoning",
  "AI 추론": "Reasoning",

  // RL
  "강화학습": "Reinforcement Learning",
  "Reinforcement Learning for LLMs": "Reinforcement Learning",

  // CV
  "컴퓨터 비전": "Computer Vision",
  "이미지 인식": "Computer Vision",

  // Alignment
  "AI 정렬(Alignment)": "AI Alignment",
  "AI 안전": "AI Safety",
  "AI Safety": "AI Safety",

  // Agents
  "AI Agent": "AI Agents",
  "AI 에이전트": "AI Agents",
  "Agentic AI": "AI Agents",

  // Code
  "Code Generation": "Code Generation",
  "코드 생성": "Code Generation",

  // Transformers
  "Transformer Architecture": "Transformer",
  "Transformer 아키텍처": "Transformer",

  // Diffusion
  "Diffusion Models": "Diffusion Models",
  "확산 모델": "Diffusion Models",

  // Knowledge Graph
  "Knowledge Graphs": "Knowledge Graphs",
  "지식 그래프": "Knowledge Graphs",

  // Embeddings
  "Word Embeddings": "Embeddings",
  "Text Embeddings": "Embeddings",

  // MoE
  "Mixture-of-Experts 아키텍처": "Mixture-of-Experts",
  "Mixture-of-Experts (MoE)": "Mixture-of-Experts",

  // Benchmark
  "AI 평가 방법론": "AI Benchmarks",
  "벤치마크": "AI Benchmarks",

  // Multimodal
  "멀티모달": "Multimodal AI",
  "Multimodal Learning": "Multimodal AI",

  // CoT
  "Chain-of-Thought Reasoning": "Chain-of-Thought",
  "Chain-of-Thought Prompting": "Chain-of-Thought",

  // Computation and Language (arxiv category, not useful as topic)
  "Computation and Language": "Natural Language Processing",
};

async function main() {
  console.log("=== Phase 1: Merge known duplicates ===\n");

  const now = new Date().toISOString();
  let merged = 0;

  for (const [source, canonical] of Object.entries(MERGE_MAP)) {
    if (source === canonical) continue;

    // Check if source topic exists
    const exists = await query(
      `MATCH (t:Topic {name: $name}) RETURN t.uid AS uid`,
      { name: source }
    );
    if (exists.length === 0) continue;

    // Ensure canonical topic exists (merge by name to avoid uid conflicts)
    await write(
      `MERGE (t:Topic {name: $canonical})`,
      { canonical }
    );

    // Transfer all incoming relationships from source to canonical
    await write(
      `MATCH (source:Topic {name: $source})<-[r]-(n)
       MATCH (target:Topic {name: $canonical})
       WHERE NOT (n)-[:TAGGED_WITH]->(target)
       CREATE (n)-[r2:TAGGED_WITH]->(target)
       SET r2 = properties(r)`,
      { source, canonical }
    );

    // Transfer MEMBER_OF
    await write(
      `MATCH (source:Topic {name: $source})-[r:MEMBER_OF]->(c)
       MATCH (target:Topic {name: $canonical})
       WHERE NOT (target)-[:MEMBER_OF]->(c)
       CREATE (target)-[r2:MEMBER_OF]->(c)
       SET r2 = properties(r)`,
      { source, canonical }
    );

    // Delete source
    await write(`MATCH (t:Topic {name: $name}) DETACH DELETE t`, { name: source });
    merged++;
    console.log(`  "${source}" → "${canonical}"`);
  }

  console.log(`\n  Merged: ${merged} topic pairs\n`);

  // Phase 2: Delete singletons that are too specific
  console.log("=== Phase 2: Clean low-value singleton topics ===\n");

  const singletons = await query(`
    MATCH (t:Topic)
    WHERE NOT (t)<-[:TAGGED_WITH]-()
    RETURN t.name AS name, t.uid AS uid
  `);

  let deleted = 0;
  for (const r of singletons) {
    await write(`MATCH (t:Topic {uid: $uid}) DETACH DELETE t`, { uid: r.get("uid") });
    deleted++;
  }
  console.log(`  Deleted ${deleted} orphaned topics\n`);

  // Phase 3: Merge very similar English topics (case-insensitive)
  console.log("=== Phase 3: Case-insensitive dedup ===\n");

  const allTopics = await query(`
    MATCH (t:Topic)<-[:TAGGED_WITH]-(x)
    RETURN t.name AS name, t.uid AS uid, count(x) AS usage
    ORDER BY usage DESC
  `);

  const seen = new Map<string, { name: string; uid: string; usage: number }>();
  let caseMerged = 0;

  for (const r of allTopics) {
    const name = r.get("name") as string;
    const uid = r.get("uid") as string;
    const usage = (r.get("usage") as any)?.low ?? r.get("usage") ?? 0;
    const key = name.toLowerCase().trim();

    if (seen.has(key)) {
      const canonical = seen.get(key)!;
      // Merge into the one with more usage
      await write(
        `MATCH (source:Topic {uid: $sourceUid})<-[r:TAGGED_WITH]-(n)
         MATCH (target:Topic {uid: $targetUid})
         WHERE NOT (n)-[:TAGGED_WITH]->(target)
         CREATE (n)-[r2:TAGGED_WITH]->(target)
         SET r2 = properties(r)`,
        { sourceUid: uid, targetUid: canonical.uid }
      );
      await write(`MATCH (t:Topic {uid: $uid}) DETACH DELETE t`, { uid });
      caseMerged++;
    } else {
      seen.set(key, { name, uid, usage });
    }
  }
  console.log(`  Case-merged: ${caseMerged} topics\n`);

  // Final count
  const final = await query(`MATCH (t:Topic) RETURN count(t) AS c`);
  console.log(`=== Final topic count: ${final[0].get("c").low} ===`);

  await close();
}

main().catch(e => { console.error(e); process.exit(1); });
