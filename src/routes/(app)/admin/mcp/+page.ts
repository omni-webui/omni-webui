import { client } from "$lib/api";
import type { components } from "$lib/api/v1.js";

/** @type {import('./$types').PageLoad} */
export async function load({
	params,
}): Promise<{ mcpServers: components["schemas"]["Settings"]["mcpServers"] }> {
	const { data } = await client.GET("/mcp/servers");
	if (!data) {
		throw new Error("Failed to load MCP servers");
	}
	return {
		mcpServers: data.mcpServers,
	};
}
