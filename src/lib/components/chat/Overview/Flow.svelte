<script lang="ts">
import { theme } from "$lib/stores";
import type { Edge, Node, NodeTypes } from "@xyflow/svelte";
import {
	Background,
	BackgroundVariant,
	Controls,
	SvelteFlow,
} from "@xyflow/svelte";
import { createEventDispatcher } from "svelte";
import type { Writable } from "svelte/store";

const dispatch = createEventDispatcher();
export let nodes: Writable<Node[]>;
export let nodeTypes: NodeTypes | undefined;
export let edges: Writable<Edge[]>;
</script>

<SvelteFlow
	{nodes}
	{nodeTypes}
	{edges}
	fitView
	minZoom={0.001}
	colorMode={$theme.includes('dark')
		? 'dark'
		: $theme === 'system'
			? window.matchMedia('(prefers-color-scheme: dark)').matches
				? 'dark'
				: 'light'
			: 'light'}
	nodesConnectable={false}
	nodesDraggable={false}
	on:nodeclick={(e) => dispatch('nodeclick', e.detail)}
	oninit={() => {
		console.log('Flow initialized');
	}}
>
	<Controls showLock={false} />
	<Background variant={BackgroundVariant.Dots} />
</SvelteFlow>
