<script lang="ts">
import client from "$lib/api";
import * as m from "$lib/paraglide/messages";
import { linter } from "@codemirror/lint";
import { EditorState } from "@codemirror/state";
import { hoverTooltip } from "@codemirror/view";
import { EditorView } from "@codemirror/view";
import { handleRefresh, stateExtensions } from "codemirror-json-schema";
import {
	json5Completion,
	json5SchemaHover,
	json5SchemaLinter,
} from "codemirror-json-schema/json5";
import { json5, json5Language, json5ParseLinter } from "codemirror-json5";
import { onMount } from "svelte";
import type { PageData } from "./$types";

const schema = {
	type: "object",
	properties: {
		mcpServers: {
			type: "object",
			patternProperties: {
				"^[a-zA-Z0-9_]+$": {
					type: "object",
					properties: {
						command: { type: "string" },
						args: { type: "array", items: { type: "string" } },
						env: {
							type: "object",
							patternProperties: { "^[a-zA-Z0-9_]+$": { type: "string" } },
						},
					},
					required: ["command"],
					additionalProperties: false,
				},
			},
		},
	},
	required: ["mcpServers"],
	additionalProperties: false,
};

export let data: PageData;
const json5State = EditorState.create({
	doc: JSON.stringify(data, null, 2),
	extensions: [
		json5(),
		linter(json5ParseLinter(), {
			// the default linting delay is 750ms
			delay: 300,
		}),
		linter(json5SchemaLinter(), {
			needsRefresh: handleRefresh,
		}),
		hoverTooltip(json5SchemaHover()),
		json5Language.data.of({
			autocomplete: json5Completion(),
		}),
		stateExtensions(schema),
	],
});
let editor: EditorView;
onMount(() => {
	const parent = document.getElementById("mcp-servers-config-textarea");
	if (!parent) {
		throw new Error("Element not found");
	}
	editor = new EditorView({
		state: json5State,
		parent,
	});
});
</script>

<svelte:head>
	<title>
		{m.mcpServers()}
	</title>
</svelte:head>
<form
	class=" flex flex-col max-h-[100dvh] h-full"
	on:submit|preventDefault={async () => {

		const {error} = await client.POST("/mcp/servers", { body: JSON.parse(editor.state.doc.toString()) });
		if (error) {
			console.error(error);
			return;
		}
	}}
>
	<div class="flex flex-col flex-1 overflow-auto h-0 rounded-lg">
		<div class="mb-2 flex-1 overflow-auto h-0 rounded-lg">
			<div id="mcp-servers-config-textarea" class="h-full w-full" />
		</div>
		<div class="pb-3 flex justify-between">
			<div class="flex-1 pr-3">
				<div class="text-xs text-gray-500 line-clamp-2">
					<span class=" font-semibold dark:text-gray-200">{m.warning()}</span>
					{m.mcpWarning()}
				</div>
			</div>

			<button
				class="px-3.5 py-1.5 text-sm font-medium bg-black hover:bg-gray-900 text-white dark:bg-white dark:text-black dark:hover:bg-gray-100 transition rounded-full"
				type="submit"
			>
				{m.save()}
			</button>
		</div>
	</div>
</form>