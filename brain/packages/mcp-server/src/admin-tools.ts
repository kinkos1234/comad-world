import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { registerAdminEntityTools } from "./admin-entity-tools.js";
import { registerAdminExportTools } from "./admin-export-tools.js";
import { registerAdminTemporalTools } from "./admin-temporal-tools.js";
import { registerAdminRefineTools } from "./admin-refine-tools.js";

/**
 * Admin-side MCP tools — split by concern to keep each file readable.
 * The public surface (one call to `registerAdminTools`) is preserved so
 * existing callers in server.ts don't change.
 */
export function registerAdminTools(server: McpServer) {
  registerAdminEntityTools(server);
  registerAdminExportTools(server);
  registerAdminTemporalTools(server);
  registerAdminRefineTools(server);
}
