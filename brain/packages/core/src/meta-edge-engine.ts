/**
 * Meta-Edge Engine — "relationships about relationships".
 *
 * This file is a facade that re-exports from the split modules. The engine
 * was split into concerns so each part stays readable:
 *
 * - `meta-edge-rules`     — declarative rule catalogue + bootstrap/evaluate/status
 * - `meta-edge-boosters`  — imperative confidence boosting + cross-verify + contradiction
 * - `meta-edge-impact`    — entity impact analysis + Lever linkage
 * - `meta-edge-backfills` — analysis_space / extracted_at / confidence backfills
 *
 * Based on SOS (ONS Guide) C03 Meta-Edge concept:
 * - constraint: validates existing relationships
 * - inference: creates new relationships when conditions are met
 * - cascade: propagates changes through the graph
 */

export {
  bootstrapMetaEdges,
  evaluateMetaEdges,
  getMetaEdgeStatus,
} from "./meta-edge-rules.js";

export {
  boostSupportedClaimConfidence,
  boostFactClaimConfidence,
  crossVerifyClaims,
  detectContradictions,
} from "./meta-edge-boosters.js";

export {
  analyzeEntityImpact,
  linkMetaEdgesToSystem,
} from "./meta-edge-impact.js";

export {
  backfillAnalysisSpaces,
  backfillExtractedAt,
  backfillConfidence,
} from "./meta-edge-backfills.js";
