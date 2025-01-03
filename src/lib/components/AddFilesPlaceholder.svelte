<script lang="ts">
import { type i18n } from "i18next";
import { getContext } from "svelte";
import { type Writable } from "svelte/store";

export let title = "";
export let content = "";
const i: Writable<i18n> = getContext("i18n");
</script>

<div class="px-3">
	<div class="text-center text-6xl mb-3">📄</div>
	<div class="text-center dark:text-white text-xl font-semibold z-50">
		{#if title}
			{title}
		{:else}
			{$i.t('Add Files')}
		{/if}
	</div>

	<slot>
		<div class="px-2 mt-2 text-center text-sm dark:text-gray-200 w-full">
			{#if content}
				{content}
			{:else}
				{$i.t('Drop any files here to add to the conversation')}
			{/if}
		</div>
	</slot>
</div>
