import { setupSchema, close } from "./neo4j-client.js";
import { bootstrapMetaEdges, evaluateMetaEdges, backfillAnalysisSpaces, backfillConfidence, backfillExtractedAt, linkMetaEdgesToSystem, boostSupportedClaimConfidence, boostFactClaimConfidence, detectContradictions, crossVerifyClaims } from "./meta-edge-engine.js";
import { bootstrapLevers, bootstrapMetaLevers, recordInitialCrawlLog } from "./lever-system.js";
import { runCommunityDetection } from "./community-detector.js";
import { initClaimHistory } from "./claim-tracker.js";
import { fetchContent } from "./content-fetcher.js";
import { query, write } from "./neo4j-client.js";

async function main() {
  const enrichMode = process.argv.includes("--enrich");

  try {
    await setupSchema();

    // Bootstrap ontology system nodes (v2)
    console.log("\nBootstrapping ontology system...");
    await bootstrapMetaEdges();
    await bootstrapLevers();
    await bootstrapMetaLevers();
    await recordInitialCrawlLog();
    await linkMetaEdgesToSystem();

    if (enrichMode) {
      // Full enrichment pipeline
      console.log("\nRunning enrichment pipeline...");

      console.log("  → Backfilling edge metadata...");
      const spaces = await backfillAnalysisSpaces();
      const conf = await backfillConfidence();
      const timestamps = await backfillExtractedAt();
      console.log(`    ${spaces} analysis_space + ${conf} confidence + ${timestamps} extracted_at backfilled`);

      console.log("  → Evaluating MetaEdge rules...");
      const inferred = await evaluateMetaEdges();
      console.log(`    ${inferred} inferred relationships created`);

      console.log("  → Running community detection...");
      const communities = await runCommunityDetection();
      console.log(`    C1: ${communities.c1_communities}, C2: ${communities.c2_communities}, C3: ${communities.c3_communities}`);

      console.log("  → Boosting claim confidence...");
      const boosted = await boostSupportedClaimConfidence();
      const factBoosted = await boostFactClaimConfidence();
      console.log(`    ${boosted} supported + ${factBoosted} fact claims boosted`);

      console.log("  → Cross-verifying claims...");
      const verified = await crossVerifyClaims();
      console.log(`    ${verified} claims cross-verified`);

      console.log("  → Detecting contradictions...");
      const contradictions = await detectContradictions();
      console.log(`    ${contradictions} potential contradictions detected`);

      console.log("  → Initializing claim history...");
      const historyInit = await initClaimHistory();
      console.log(`    ${historyInit} claims initialized with baseline history`);

      // Fetch full content for articles missing it
      console.log("  → Fetching full content for articles...");
      const noContentRecs = await query(
        `MATCH (a:Article) WHERE a.full_content IS NULL AND a.url IS NOT NULL RETURN a.uid AS uid, a.url AS url LIMIT 20`
      );
      let fetched = 0;
      for (const rec of noContentRecs) {
        const url = rec.get("url") as string;
        const uid = rec.get("uid") as string;
        const content = await fetchContent(url);
        if (content && content.length > 100) {
          await write(
            `MATCH (a:Article {uid: $uid}) SET a.full_content = $content`,
            { uid, content: content.slice(0, 10000) }
          );
          fetched++;
        }
      }
      console.log(`    ${fetched}/${noContentRecs.length} articles fetched`);
    }

    console.log("\nDone.");
  } catch (e) {
    console.error("Schema setup failed:", e);
    process.exit(1);
  } finally {
    await close();
  }
}

main();
