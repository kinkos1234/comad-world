/**
 * GraphRAG Benchmark Runner
 *
 * Runs all 20 benchmark questions, measures latency and entity recall,
 * and writes results to data/benchmark-{date}.json
 *
 * Usage: bun run benchmark
 */

import { ask } from "./index.js";
import { BENCHMARK_QUESTIONS, type BenchmarkResult, type BenchmarkReport } from "./benchmark.js";
import { query, close } from "@comad-brain/core";
import { resolveEntities } from "./entity-resolver.js";
import { writeFileSync, mkdirSync } from "fs";
import { join } from "path";

async function getGraphSize(): Promise<{ nodes: number; edges: number }> {
  const result = await query(
    "MATCH (n) WITH count(n) AS nodes MATCH ()-[r]->() RETURN nodes, count(r) AS edges"
  );
  const row = result[0];
  return {
    nodes: row?.get("nodes") ?? 0,
    edges: row?.get("edges") ?? 0,
  };
}

async function runBenchmark(): Promise<void> {
  console.log("GraphRAG Benchmark — Starting...\n");

  const graphSize = await getGraphSize();
  console.log(`Graph: ${graphSize.nodes.toLocaleString()} nodes, ${graphSize.edges.toLocaleString()} edges\n`);

  const results: BenchmarkResult[] = [];

  for (const q of BENCHMARK_QUESTIONS) {
    process.stdout.write(`[${q.id}] ${q.difficulty.padEnd(6)} ${q.question.slice(0, 50)}... `);

    const start = performance.now();
    let answer = "";
    let answerQuality: BenchmarkResult["answer_quality"] = "no_answer";

    try {
      answer = await ask(q.question);
      const latency = Math.round(performance.now() - start);

      // Check entity recall
      const entitiesFound: string[] = [];
      for (const expected of q.expected_entities) {
        if (answer.toLowerCase().includes(expected.toLowerCase())) {
          entitiesFound.push(expected);
        }
      }

      const entityRecall = q.expected_entities.length > 0
        ? entitiesFound.length / q.expected_entities.length
        : 1;

      // Check topic relevance
      const topicHits = q.expected_topics.filter(t =>
        answer.toLowerCase().includes(t.toLowerCase())
      ).length;
      const contextRelevant = topicHits > 0 || q.expected_topics.length === 0;

      // Quality assessment
      if (entityRecall >= 0.8 && contextRelevant) {
        answerQuality = "good";
      } else if (entityRecall >= 0.5 || contextRelevant) {
        answerQuality = "partial";
      } else if (answer && !answer.includes("찾을 수 없습니다")) {
        answerQuality = "poor";
      }

      const result: BenchmarkResult = {
        question_id: q.id,
        entities_found: entitiesFound,
        entities_expected: q.expected_entities,
        entity_recall: entityRecall,
        context_relevant: contextRelevant,
        answer_quality: answerQuality,
        latency_ms: latency,
      };

      results.push(result);

      const icon = answerQuality === "good" ? "✓" : answerQuality === "partial" ? "~" : "✗";
      console.log(`${icon} ${latency}ms (recall: ${Math.round(entityRecall * 100)}%)`);
    } catch (e) {
      const latency = Math.round(performance.now() - start);
      results.push({
        question_id: q.id,
        entities_found: [],
        entities_expected: q.expected_entities,
        entity_recall: 0,
        context_relevant: false,
        answer_quality: "no_answer",
        latency_ms: latency,
      });
      console.log(`✗ ERROR ${latency}ms — ${(e as Error).message?.slice(0, 60)}`);
    }
  }

  // Summary
  const good = results.filter(r => r.answer_quality === "good").length;
  const partial = results.filter(r => r.answer_quality === "partial").length;
  const poor = results.filter(r => r.answer_quality === "poor").length;
  const noAnswer = results.filter(r => r.answer_quality === "no_answer").length;
  const avgLatency = Math.round(results.reduce((s, r) => s + r.latency_ms, 0) / results.length);
  const avgRecall = results.reduce((s, r) => s + r.entity_recall, 0) / results.length;

  const byDifficulty: Record<string, { count: number; entity_recall_avg: number; good_rate: number }> = {};
  for (const diff of ["easy", "medium", "hard"]) {
    const subset = results.filter((r, i) => BENCHMARK_QUESTIONS[i].difficulty === diff);
    byDifficulty[diff] = {
      count: subset.length,
      entity_recall_avg: subset.reduce((s, r) => s + r.entity_recall, 0) / subset.length,
      good_rate: subset.filter(r => r.answer_quality === "good").length / subset.length,
    };
  }

  const report: BenchmarkReport = {
    run_date: new Date().toISOString().slice(0, 10),
    graph_size: graphSize,
    results,
    summary: {
      total: results.length,
      entity_recall_avg: Math.round(avgRecall * 100) / 100,
      good_answers: good,
      partial_answers: partial,
      poor_answers: poor,
      avg_latency_ms: avgLatency,
      by_difficulty: byDifficulty,
    },
  };

  // Write report
  const dataDir = join(import.meta.dir, "../../../../data");
  mkdirSync(dataDir, { recursive: true });
  const outPath = join(dataDir, `benchmark-${report.run_date}.json`);
  writeFileSync(outPath, JSON.stringify(report, null, 2));

  // Print summary
  console.log("\n═══════════════════════════════════════");
  console.log(`  GraphRAG Benchmark — ${report.run_date}`);
  console.log(`  Graph: ${graphSize.nodes.toLocaleString()} nodes`);
  console.log(`  Good: ${good}  Partial: ${partial}  Poor: ${poor}  No Answer: ${noAnswer}`);
  console.log(`  Entity Recall: ${Math.round(avgRecall * 100)}%`);
  console.log(`  Avg Latency: ${avgLatency}ms`);
  console.log("───────────────────────────────────────");
  for (const [diff, stats] of Object.entries(byDifficulty)) {
    console.log(`  ${diff.padEnd(8)} recall: ${Math.round(stats.entity_recall_avg * 100)}%  good: ${Math.round(stats.good_rate * 100)}%`);
  }
  console.log("═══════════════════════════════════════");
  console.log(`\nReport saved: ${outPath}`);

  await close();
}

runBenchmark().catch(e => {
  console.error("Benchmark failed:", e);
  process.exit(1);
});
