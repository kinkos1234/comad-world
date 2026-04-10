# MCP Tools — Stability Guide

All Comad MCP tools follow a three-tier stability model. Check the stability level before building integrations.

## Stability Levels

| Level | Meaning | Contract |
|-------|---------|----------|
| **Stable** | Production-ready. Parameters and response shape won't change without a major version bump. | Safe for automation and external integrations. |
| **Beta** | Functional and tested, but parameter names or response fields may change. | Fine for interactive use. Pin to a known version for automation. |
| **Alpha** | Experimental. May be removed, renamed, or fundamentally reworked. | Manual use only. |

## Brain Tools (22 tools)

### Stable

| Tool | Purpose |
|------|---------|
| `comad_brain_search` | Full-text search across all nodes |
| `comad_brain_ask` | GraphRAG Q&A (question → answer with graph context) |
| `comad_brain_stats` | Node/relationship counts |
| `comad_brain_recent` | Recently added nodes |
| `comad_brain_related` | Find related entities by uid |
| `comad_brain_explore` | Neighborhood traversal from a node |
| `comad_brain_claims` | List claims with confidence scores |
| `comad_brain_communities` | Community detection results |
| `comad_brain_stale` | Nodes not updated recently |
| `comad_brain_perf` | Query performance metrics |

### Beta

| Tool | Purpose | Notes |
|------|---------|-------|
| `comad_brain_export` | Export subgraph as JSON | Response format may expand |
| `comad_brain_impact` | Entity impact analysis | Scoring algorithm under tuning |
| `comad_brain_impact_v2` | Impact v2 (weighted) | May replace v1 |
| `comad_brain_trend` | Temporal trend detection | Time window params may change |
| `comad_brain_temporal` | Time-scoped queries | Filter syntax under review |
| `comad_brain_claim_timeline` | Claim confidence over time | Chart format TBD |
| `comad_brain_contradictions` | Find conflicting claims | Threshold params may change |
| `comad_brain_meta` | Graph metadata/schema | Response shape may expand |
| `comad_brain_dedup` | Find duplicate entities | Merge strategy under review |
| `comad_brain_refine` | Refine entity extraction | Prompt-dependent |

### Alpha

| Tool | Purpose | Notes |
|------|---------|-------|
| `comad_brain_graph_export` | Full graph export | Performance concerns at scale |
| `comad_brain_ontology_meta` | Ontology schema introspection | May merge into `meta` |

## Eye Tools (7 tools)

### Stable

| Tool | Purpose |
|------|---------|
| `comad_eye_status` | Pipeline/job status check |
| `comad_eye_jobs` | List completed analysis jobs |
| `comad_eye_lenses` | Available analysis lenses |

### Beta

| Tool | Purpose | Notes |
|------|---------|-------|
| `comad_eye_analyze` | Run full simulation pipeline | Long-running (minutes). Params may change. |
| `comad_eye_preflight` | Estimate cost/tokens before run | Token counting heuristics under refinement |
| `comad_eye_report` | Retrieve analysis report | Report format evolving |
| `comad_eye_ask` | Interactive Q&A on analysis | Session management under review |

## Sleep Tool (1 tool)

### Stable

| Tool | Purpose |
|------|---------|
| `comad_sleep_info` | Memory consolidation status |

### Beta

| Tool | Purpose | Notes |
|------|---------|-------|
| `comad_sleep_history` | Consolidation history | Response shape may change |

## Version History

| Date | Change |
|------|--------|
| 2026-04-11 | Initial stability classification |
