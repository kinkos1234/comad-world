import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { close } from "@comad-brain/core";
import { registerCoreTools } from "./core-tools.js";
import { registerAnalysisTools } from "./analysis-tools.js";
import { registerAdminTools } from "./admin-tools.js";

const server = new McpServer({
  name: "comad-brain",
  version: "0.1.0",
});

registerCoreTools(server);
registerAnalysisTools(server);
registerAdminTools(server);

// ============================================
// Start server
// ============================================

async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((e) => {
  process.stderr.write(`MCP server error: ${e}\n`);
  process.exit(1);
});

// Cleanup on exit
process.on("SIGINT", async () => {
  await close();
  process.exit(0);
});
