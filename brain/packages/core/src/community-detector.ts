/**
 * Community detection pipeline — facade.
 *
 * Based on SOS (ONS Guide) C01 GraphRAG:
 * - Leiden community detection with C0-C3 hierarchy
 * - Community summary generation via Claude -p
 *
 * Since Neo4j Community Edition lacks GDS, we use Cypher-based
 * label propagation via connected component analysis.
 *
 * Implementation is split into two files:
 * - `community-detectors` — the three detect* algorithms + linkCommunityHierarchy
 * - `community-enrich`    — member enrichment + summary generation + naming helpers
 *
 * Everything is re-exported from here so downstream imports keep working.
 */

export {
  detectTechCommunities,
  detectTopicCommunities,
  detectMetaCommunities,
  linkCommunityHierarchy,
} from "./community-detectors.js";

export {
  generateCommunitySummaries,
  enrichCommunityMembers,
  generateCommunityName,
  claudeSummarize,
} from "./community-enrich.js";

import {
  detectTechCommunities,
  detectTopicCommunities,
  detectMetaCommunities,
  linkCommunityHierarchy,
} from "./community-detectors.js";
import {
  enrichCommunityMembers,
  generateCommunitySummaries,
} from "./community-enrich.js";

/** Run full community detection pipeline. */
export async function runCommunityDetection(): Promise<{
  c1_communities: number;
  c2_communities: number;
  c3_communities: number;
  hierarchy_links: number;
  summaries_updated: number;
}> {
  console.log("  Running community detection...");

  const c1 = await detectTechCommunities();
  console.log(`  ✓ C1 (Tech clusters): ${c1} communities`);

  const c2 = await detectTopicCommunities();
  console.log(`  ✓ C2 (Topic clusters): ${c2} communities`);

  const enriched = await enrichCommunityMembers();
  console.log(`  ✓ Enriched: ${enriched} person/org members added to communities`);

  const c3 = await detectMetaCommunities();
  console.log(`  ✓ C3 (Meta-communities): ${c3} communities`);

  const hierarchy = await linkCommunityHierarchy();
  console.log(`  ✓ Hierarchy links: ${hierarchy} PARENT_COMMUNITY relationships`);

  const summaries = await generateCommunitySummaries();
  console.log(`  ✓ Summaries updated: ${summaries}`);

  return {
    c1_communities: c1,
    c2_communities: c2,
    c3_communities: c3,
    hierarchy_links: hierarchy,
    summaries_updated: summaries,
  };
}
