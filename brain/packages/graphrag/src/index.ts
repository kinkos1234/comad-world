import { close } from "@comad-brain/core";
import { analyzeQuery } from "./query-analyzer.js";
import { resolveEntities } from "./entity-resolver.js";
import { retrieveSubgraph } from "./subgraph-retriever.js";
import { buildContext } from "./context-builder.js";
import { synthesize } from "./synthesizer.js";

export { analyzeQuery, resolveEntities, retrieveSubgraph, buildContext, synthesize };
export { dualRetrieve } from "./dual-retriever.js";
export type {
  DualRetrieveResult,
  DualRetrieveOptions,
  DualMatch,
  LocalMatch,
  GlobalMatch,
  TemporalMatch,
} from "./dual-retriever.js";

/**
 * Full GraphRAG pipeline: question → answer with graph context.
 */
export async function ask(question: string): Promise<string> {
  // 1. Analyze query
  const analyzed = await analyzeQuery(question);

  // 2. Resolve entities in graph
  const resolved = await resolveEntities(analyzed.entities);

  if (resolved.length === 0) {
    // Fallback: direct fulltext search
    const { query } = await import("@comad-brain/core");
    const fallback = await query(
      `CALL db.index.fulltext.queryNodes("comad_brain_search", $q)
       YIELD node, score
       RETURN node.uid AS uid, labels(node)[0] AS label,
              coalesce(node.name, node.title) AS name, score
       LIMIT 10`,
      { q: question }
    );

    if (fallback.length === 0) {
      return "지식 그래프에서 관련 정보를 찾을 수 없습니다.";
    }

    for (const rec of fallback) {
      resolved.push({
        uid: rec.get("uid"),
        label: rec.get("label"),
        name: rec.get("name"),
        score: rec.get("score"),
      });
    }
  }

  // 3. Retrieve subgraph
  const subgraph = await retrieveSubgraph(resolved.slice(0, 5), 2, 30);

  // 4. Build context
  const context = buildContext(subgraph);

  // 5. Synthesize answer
  const answer = await synthesize(question, context);

  return answer;
}
