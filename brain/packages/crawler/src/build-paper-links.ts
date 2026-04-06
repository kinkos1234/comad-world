/**
 * Build Paper↔Paper relationships by:
 * 1. Mining full_content for arxiv ID cross-references
 * 2. Adding known lineage relationships (EVOLVED_FROM, INFLUENCED_BY, CITES)
 *
 * Usage: bun run packages/crawler/src/build-paper-links.ts
 */

import { write, close, query } from "@comad-brain/core";

// ─── Phase 1: Mine cross-references from full_content ───

async function mineCrossReferences() {
  console.log("=== Phase 1: Mining arxiv ID cross-references ===\n");

  const papers = await query(
    `MATCH (p:Paper) WHERE p.arxiv_id IS NOT NULL
     RETURN p.uid AS uid, p.arxiv_id AS arxiv_id, p.title AS title, p.full_content AS content`
  );

  // Build arxiv_id → uid lookup
  const idToUid = new Map<string, string>();
  const idToTitle = new Map<string, string>();
  for (const r of papers) {
    const id = r.get("arxiv_id") as string;
    if (id) {
      idToUid.set(id, r.get("uid") as string);
      idToTitle.set(id, r.get("title") as string);
    }
  }

  const allIds = [...idToUid.keys()];
  console.log(`  ${allIds.length} papers with arxiv IDs\n`);

  let totalLinks = 0;
  const now = new Date().toISOString();

  for (const r of papers) {
    const uid = r.get("uid") as string;
    const arxivId = r.get("arxiv_id") as string;
    const title = (r.get("title") as string ?? "").substring(0, 50);
    const content = r.get("content") as string ?? "";

    if (!content || content.length < 100) continue;

    // Find all arxiv IDs mentioned in this paper's content
    const mentions = new Set<string>();
    for (const targetId of allIds) {
      if (targetId === arxivId) continue; // skip self
      if (content.includes(targetId)) {
        mentions.add(targetId);
      }
    }

    if (mentions.size > 0) {
      console.log(`  ${title}... → ${mentions.size} references`);
      for (const targetId of mentions) {
        const targetUid = idToUid.get(targetId)!;
        await write(
          `MATCH (a:Paper {uid: $from}), (b:Paper {uid: $to})
           MERGE (a)-[r:CITES]->(b)
           ON CREATE SET r.confidence = 0.9, r.source = 'content-mining',
                         r.extracted_at = $now, r.analysis_space = 'temporal'`,
          { from: uid, to: targetUid, now }
        );
        totalLinks++;
      }
    }
  }

  console.log(`\n  Phase 1 result: ${totalLinks} CITES links created\n`);
  return totalLinks;
}

// ─── Phase 2: Known lineage relationships ───

interface Lineage {
  from: string; // arxiv_id or uid-suffix
  to: string;
  type: "EVOLVED_FROM" | "INFLUENCED_BY";
  context?: string;
}

const KNOWN_LINEAGE: Lineage[] = [
  // Transformer lineage
  { from: "1810.04805", to: "1706.03762", type: "EVOLVED_FROM", context: "BERT built on Transformer architecture" },
  { from: "2005.14165", to: "1706.03762", type: "EVOLVED_FROM", context: "GPT-3 uses Transformer decoder architecture" },
  { from: "gpt-1-2018", to: "1706.03762", type: "EVOLVED_FROM", context: "GPT-1 first applied Transformer to language pretraining" },
  { from: "gpt-2-2019", to: "gpt-1-2018", type: "EVOLVED_FROM", context: "GPT-2 scales up GPT-1" },
  { from: "2005.14165", to: "gpt-2-2019", type: "EVOLVED_FROM", context: "GPT-3 scales up GPT-2" },
  { from: "2303.08774", to: "2005.14165", type: "EVOLVED_FROM", context: "GPT-4 evolves from GPT-3" },

  // LLaMA lineage
  { from: "2302.13971", to: "1706.03762", type: "EVOLVED_FROM", context: "LLaMA uses Transformer with RMSNorm, SwiGLU, RoPE" },
  { from: "2307.09288", to: "2302.13971", type: "EVOLVED_FROM", context: "Llama 2 evolves from LLaMA" },
  { from: "2407.21783", to: "2307.09288", type: "EVOLVED_FROM", context: "Llama 3 evolves from Llama 2" },

  // DeepSeek lineage
  { from: "2405.04434", to: "2401.06066", type: "EVOLVED_FROM", context: "DeepSeek-V2 builds on DeepSeek-MoE with MLA" },
  { from: "2412.19437", to: "2405.04434", type: "EVOLVED_FROM", context: "DeepSeek-V3 evolves from V2" },
  { from: "2501.12948", to: "2412.19437", type: "EVOLVED_FROM", context: "DeepSeek-R1 built on V3-Base via RL" },

  // Mistral lineage
  { from: "2401.04088", to: "2310.06825", type: "EVOLVED_FROM", context: "Mixtral is MoE variant of Mistral 7B" },
  { from: "2410.07073", to: "2310.06825", type: "EVOLVED_FROM", context: "Pixtral builds on Mistral Nemo (Mistral family)" },

  // RLHF/DPO lineage
  { from: "2203.02155", to: "1707.06347", type: "EVOLVED_FROM", context: "InstructGPT uses PPO for RLHF" },
  { from: "2305.18290", to: "2203.02155", type: "EVOLVED_FROM", context: "DPO simplifies RLHF, removes reward model" },
  { from: "2501.12948", to: "1707.06347", type: "INFLUENCED_BY", context: "DeepSeek-R1 uses GRPO, a PPO variant" },

  // Reasoning lineage
  { from: "2201.11903", to: "2005.14165", type: "INFLUENCED_BY", context: "CoT prompting discovered in GPT-3 scale models" },
  { from: "2305.10601", to: "2201.11903", type: "EVOLVED_FROM", context: "Tree of Thoughts extends Chain-of-Thought" },
  { from: "2501.04682", to: "2201.11903", type: "EVOLVED_FROM", context: "Meta-CoT extends CoT with meta-reasoning" },
  { from: "2305.20050", to: "2201.11903", type: "INFLUENCED_BY", context: "Process reward models verify CoT steps" },
  { from: "2501.19393", to: "2305.20050", type: "INFLUENCED_BY", context: "s1 uses test-time compute scaling inspired by step verification" },

  // Agent lineage
  { from: "2210.03629", to: "2201.11903", type: "INFLUENCED_BY", context: "ReAct combines reasoning (CoT) with acting" },
  { from: "2302.04761", to: "2210.03629", type: "INFLUENCED_BY", context: "Toolformer extends tool-use concept from ReAct" },
  { from: "2405.15793", to: "2310.06770", type: "EVOLVED_FROM", context: "SWE-agent built for SWE-bench" },
  { from: "2308.08155", to: "2210.03629", type: "INFLUENCED_BY", context: "AutoGen multi-agent uses ReAct-style reasoning" },
  { from: "2308.00352", to: "2308.08155", type: "INFLUENCED_BY", context: "MetaGPT and AutoGen are concurrent multi-agent frameworks" },

  // RAG lineage
  { from: "2404.16130", to: "2005.11401", type: "EVOLVED_FROM", context: "GraphRAG extends RAG with knowledge graphs" },
  { from: "2405.14831", to: "2005.11401", type: "EVOLVED_FROM", context: "HippoRAG extends RAG with hippocampal memory" },
  { from: "2401.18059", to: "2005.11401", type: "EVOLVED_FROM", context: "RAPTOR extends RAG with hierarchical tree retrieval" },
  { from: "2410.05779", to: "2404.16130", type: "EVOLVED_FROM", context: "LightRAG simplifies GraphRAG with dual-level retrieval" },
  { from: "2310.11511", to: "2005.11401", type: "EVOLVED_FROM", context: "Self-RAG adds self-reflection to RAG" },
  { from: "2401.15884", to: "2005.11401", type: "EVOLVED_FROM", context: "CRAG adds corrective retrieval to RAG" },
  { from: "2403.14403", to: "2005.11401", type: "EVOLVED_FROM", context: "Adaptive-RAG dynamically selects RAG strategy" },
  { from: "2005.11401", to: "2004.04906", type: "INFLUENCED_BY", context: "RAG uses DPR for dense retrieval" },

  // Vision lineage
  { from: "1512.03385", to: "alexnet-2012", type: "EVOLVED_FROM", context: "ResNet deepens CNN architecture from AlexNet era" },
  { from: "2010.11929", to: "1706.03762", type: "INFLUENCED_BY", context: "ViT applies Transformer to vision" },
  { from: "2103.00020", to: "2010.11929", type: "INFLUENCED_BY", context: "CLIP combines ViT with language" },
  { from: "2304.02643", to: "2010.11929", type: "INFLUENCED_BY", context: "SAM uses ViT-based encoder" },
  { from: "2408.00714", to: "2304.02643", type: "EVOLVED_FROM", context: "SAM 2 extends SAM to video" },
  { from: "2304.08485", to: "2103.00020", type: "INFLUENCED_BY", context: "LLaVA uses CLIP visual encoder" },
  { from: "2301.12597", to: "2103.00020", type: "INFLUENCED_BY", context: "BLIP-2 bridges frozen CLIP with LLM" },

  // Diffusion lineage
  { from: "2112.10752", to: "2006.11239", type: "EVOLVED_FROM", context: "Latent Diffusion (Stable Diffusion) applies DDPM in latent space" },
  { from: "2212.09748", to: "2112.10752", type: "EVOLVED_FROM", context: "DiT replaces U-Net with Transformer in diffusion" },
  { from: "2403.03206", to: "2112.10752", type: "EVOLVED_FROM", context: "SD3 uses rectified flow transformers" },
  { from: "2204.06125", to: "2103.00020", type: "INFLUENCED_BY", context: "DALL-E 2 uses CLIP latents for image generation" },

  // KG embedding lineage
  { from: "1507.05279", to: "1301.4083", type: "EVOLVED_FROM", context: "TransR extends TransE with relation-specific spaces" },
  { from: "1902.10197", to: "1301.4083", type: "EVOLVED_FROM", context: "RotatE extends TransE with complex rotations" },
  { from: "1906.07854", to: "1710.10903", type: "INFLUENCED_BY", context: "KGAT applies GAT to knowledge graphs" },

  // Finetuning lineage
  { from: "2305.14314", to: "2106.09685", type: "EVOLVED_FROM", context: "QLoRA quantizes LoRA for efficiency" },
  { from: "2404.03592", to: "2106.09685", type: "EVOLVED_FROM", context: "ReFT moves from weight to representation finetuning, inspired by LoRA" },

  // Architecture alternatives
  { from: "2305.13048", to: "1706.03762", type: "INFLUENCED_BY", context: "RWKV as Transformer alternative combining RNN efficiency" },
  { from: "2312.00752", to: "1706.03762", type: "INFLUENCED_BY", context: "Mamba as state space alternative to Transformer" },
  { from: "2403.19887", to: "2312.00752", type: "EVOLVED_FROM", context: "Jamba hybridizes Transformer with Mamba" },

  // Embedding/retrieval
  { from: "2004.12832", to: "1810.04805", type: "INFLUENCED_BY", context: "ColBERT uses BERT for late-interaction retrieval" },

  // Qwen lineage
  { from: "2505.09388", to: "2407.10671", type: "EVOLVED_FROM", context: "Qwen3 evolves from Qwen2" },
];

async function buildKnownLineage() {
  console.log("=== Phase 2: Known lineage relationships ===\n");

  // Build uid lookup by arxiv_id AND uid suffix
  const papers = await query(
    `MATCH (p:Paper) RETURN p.uid AS uid, p.arxiv_id AS arxiv_id`
  );
  const lookup = new Map<string, string>();
  for (const r of papers) {
    const uid = r.get("uid") as string;
    const aid = r.get("arxiv_id") as string;
    if (aid) lookup.set(aid, uid);
    // Also map uid suffixes like "alexnet-2012"
    const suffix = uid.replace("paper:", "");
    lookup.set(suffix, uid);
  }

  const now = new Date().toISOString();
  let created = 0;
  let skipped = 0;

  for (const link of KNOWN_LINEAGE) {
    const fromUid = lookup.get(link.from);
    const toUid = lookup.get(link.to);

    if (!fromUid || !toUid) {
      console.log(`  skip: ${link.from} → ${link.to} (not found)`);
      skipped++;
      continue;
    }

    await write(
      `MATCH (a:Paper {uid: $from}), (b:Paper {uid: $to})
       MERGE (a)-[r:${link.type}]->(b)
       ON CREATE SET r.confidence = 0.95, r.source = 'curated',
                     r.context = $context, r.extracted_at = $now,
                     r.analysis_space = 'temporal'`,
      { from: fromUid, to: toUid, context: link.context ?? "", now }
    );
    created++;
  }

  console.log(`\n  Phase 2 result: ${created} lineage links, ${skipped} skipped\n`);
  return created;
}

// ─── Main ───

async function main() {
  const mined = await mineCrossReferences();
  const lineage = await buildKnownLineage();

  // Final count
  const result = await query(
    `MATCH (p1:Paper)-[r]->(p2:Paper) RETURN type(r) AS t, count(r) AS c ORDER BY c DESC`
  );
  console.log("=== Final Paper↔Paper Connections ===");
  result.forEach(r => console.log(`  ${r.get("t")}: ${r.get("c").low}`));

  const total = await query(`MATCH (p1:Paper)-[r]->(p2:Paper) RETURN count(r) AS c`);
  console.log(`\nTotal: ${total[0].get("c").low} Paper↔Paper links`);

  await close();
}

main().catch(e => { console.error(e); process.exit(1); });
