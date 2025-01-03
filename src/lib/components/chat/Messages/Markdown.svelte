<script lang="ts">
import { user } from "$lib/stores";
import { processResponseContent, replaceTokens } from "$lib/utils";
import { marked } from "marked";

import markedExtension from "$lib/utils/marked/extension";
import markedKatexExtension from "$lib/utils/marked/katex-extension";

import { createEventDispatcher } from "svelte";
import MarkdownTokens from "./Markdown/MarkdownTokens.svelte";

const dispatch = createEventDispatcher();

export let id: string;
export let content: string;
export let model = null;
export let save = false;

export let sourceIds = [];
export let onSourceClick = () => {};

let tokens = [];

const options = {
	throwOnError: false,
};

marked.use(markedKatexExtension(options));
marked.use(markedExtension(options));

$: (async () => {
	if (content) {
		tokens = marked.lexer(
			replaceTokens(
				processResponseContent(content),
				sourceIds,
				model?.name,
				$user?.name,
			),
		);
	}
})();
</script>

{#key id}
	<MarkdownTokens
		{tokens}
		{id}
		{save}
		{onSourceClick}
		on:update={(e) => {
			dispatch('update', e.detail);
		}}
		on:code={(e) => {
			dispatch('code', e.detail);
		}}
	/>
{/key}
