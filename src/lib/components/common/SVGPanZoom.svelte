<script lang="ts">
import { copyToClipboard } from "$lib/utils";
import { type i18n } from "i18next";
import panzoom, { type PanZoom } from "panzoom";
import { getContext } from "svelte";
import { toast } from "svelte-sonner";
import { type Writable } from "svelte/store";
import Clipboard from "../icons/Clipboard.svelte";
import Reset from "../icons/Reset.svelte";
import Tooltip from "./Tooltip.svelte";

export let className = "";
export let svg = "";
export let content = "";
const i: Writable<i18n> = getContext("i18n");

let instance: PanZoom;
let sceneElement: HTMLDivElement;

$: if (sceneElement) {
	instance = panzoom(sceneElement, {
		bounds: true,
		boundsPadding: 0.1,

		zoomSpeed: 0.065,
	});
}
function resetPanZoomViewport() {
	console.log("Reset View");
	instance.moveTo(0, 0);
	instance.zoomAbs(0, 0, 1);
	console.log(instance.getTransform());
}
</script>

<div class="relative {className}">
	<div bind:this={sceneElement} class="flex h-full max-h-full justify-center items-center">
		{@html svg}
	</div>

	{#if content}
		<div class=" absolute top-1 right-1">
			<Tooltip content={$i.t('Copy to clipboard')}>
				<button
					class="p-1.5 rounded-lg border border-gray-100 dark:border-none dark:bg-gray-850 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={() => {
						copyToClipboard(content);
						toast.success($i.t('Copied to clipboard'));
					}}
				>
					<Clipboard className=" size-4" strokeWidth="1.5" />
				</button>
			</Tooltip>
		</div>
		<div class=" absolute top-1 right-10">
			<Tooltip content={$i.t('Reset view')}>
				<button
					class="p-1.5 rounded-lg border border-gray-100 dark:border-none dark:bg-gray-850 hover:bg-gray-50 dark:hover:bg-gray-800 transition"
					on:click={() => {
						resetPanZoomViewport();
						toast.success($i.t('Reset view'));
					}}
				>
					<Reset className=" size-4" />
				</button>
			</Tooltip>
		</div>
	{/if}
</div>
