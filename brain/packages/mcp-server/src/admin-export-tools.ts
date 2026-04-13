import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { query } from "@comad-brain/core";
import { toolError, safeLabel } from "./utils.js";

/** Multi-format graph export (JSON, JSON-LD, CSV). */
export function registerAdminExportTools(server: McpServer) {
  // ============================================
  // Tool: comad_brain_export (multi-format)
  // ============================================
  server.tool(
    "comad_brain_export",
    "그래프 데이터 내보내기 — JSON, JSON-LD (표준 Linked Data), CSV 형식 지원",
    {
      types: z.array(z.string()).optional().describe("내보낼 노드 타입 (기본: 전체)"),
      include_edges: z.boolean().optional().describe("관계 포함 여부 (기본: true)"),
      limit: z.number().optional().describe("노드 수 제한 (기본: 100)"),
      format: z.enum(["json", "jsonld", "csv"]).optional().describe("출력 형식 (기본: json)"),
    },
    async ({ types, include_edges = true, limit = 100, format = "json" }) => {
      try {
      if (types && types.some(t => !safeLabel(t))) return toolError(`Invalid type in: ${types.join(", ")}`);
      let nodeQuery = `MATCH (n)`;
      const params: Record<string, unknown> = { limit };
      if (types && types.length > 0) {
        const labelFilter = types.map(t => `n:${t}`).join(" OR ");
        nodeQuery += ` WHERE ${labelFilter}`;
      }
      nodeQuery += ` RETURN n, labels(n) AS labels LIMIT $limit`;

      const nodeRecords = await query(nodeQuery, params);
      const nodes = nodeRecords.map(r => {
        const n = r.get("n");
        const props = n.properties;
        return {
          id: props.uid,
          labels: r.get("labels"),
          ...props,
        };
      });

      let edges: any[] = [];
      if (include_edges) {
        let edgeQuery = `MATCH (a)-[r]->(b)`;
        if (types && types.length > 0) {
          const filter = types.map(t => `a:${t} OR b:${t}`).join(" OR ");
          edgeQuery += ` WHERE ${filter}`;
        }
        edgeQuery += ` RETURN a.uid AS source, b.uid AS target, type(r) AS type, properties(r) AS props LIMIT $limit`;

        const edgeRecords = await query(edgeQuery, params);
        edges = edgeRecords.map(r => ({
          source: r.get("source"),
          target: r.get("target"),
          type: r.get("type"),
          ...r.get("props"),
        }));
      }

      let output: string;

      if (format === "jsonld") {
        // JSON-LD — W3C Linked Data standard
        const COMAD_NS = "https://comad.dev/ontology/";
        const graph = nodes.map(node => {
          const ldNode: Record<string, unknown> = {
            "@id": `${COMAD_NS}node/${node.id}`,
            "@type": (node.labels as string[]).map(l => `${COMAD_NS}${l}`),
          };
          for (const [k, v] of Object.entries(node)) {
            if (k === "id" || k === "labels" || k === "uid") continue;
            if (v !== null && v !== undefined) ldNode[`${COMAD_NS}${k}`] = v;
          }
          return ldNode;
        });

        if (include_edges) {
          for (const edge of edges) {
            const sourceNode = graph.find(n => n["@id"] === `${COMAD_NS}node/${edge.source}`);
            if (sourceNode) {
              const rel = `${COMAD_NS}${edge.type}`;
              const existing = sourceNode[rel];
              const target = { "@id": `${COMAD_NS}node/${edge.target}` };
              if (existing) {
                sourceNode[rel] = Array.isArray(existing) ? [...existing, target] : [existing, target];
              } else {
                sourceNode[rel] = target;
              }
            }
          }
        }

        output = JSON.stringify({
          "@context": {
            "comad": COMAD_NS,
            "@vocab": COMAD_NS,
          },
          "@graph": graph,
        }, null, 2);

      } else if (format === "csv") {
        // CSV — nodes and edges as separate sections
        const nodeFields = ["id", "labels", "name", "title", "url", "created_at"];
        const nodeHeader = nodeFields.join(",");
        const nodeRows = nodes.map(n => {
          return nodeFields.map(f => {
            const v = (n as any)[f];
            if (v === undefined || v === null) return "";
            const s = Array.isArray(v) ? v.join(";") : String(v);
            return s.includes(",") || s.includes('"') ? `"${s.replace(/"/g, '""')}"` : s;
          }).join(",");
        });

        let csv = `# NODES\n${nodeHeader}\n${nodeRows.join("\n")}`;

        if (include_edges && edges.length > 0) {
          const edgeHeader = "source,target,type";
          const edgeRows = edges.map(e => `${e.source},${e.target},${e.type}`);
          csv += `\n\n# EDGES\n${edgeHeader}\n${edgeRows.join("\n")}`;
        }

        output = csv;

      } else {
        // Default JSON
        output = JSON.stringify({ nodes: nodes.length, edges: edges.length, data: { nodes, edges } }, null, 2);
      }

      return {
        content: [{
          type: "text" as const,
          text: output,
        }],
      };
      } catch (e: any) {
        return toolError(e.message);
      }
    }
  );

}
