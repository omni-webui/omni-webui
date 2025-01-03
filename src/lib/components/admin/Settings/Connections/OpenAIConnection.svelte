<script lang="ts">
import SensitiveInput from "$lib/components/common/SensitiveInput.svelte";
import Tooltip from "$lib/components/common/Tooltip.svelte";
import Cog6 from "$lib/components/icons/Cog6.svelte";
import type { i18n as i18nType } from "i18next";
import { getContext } from "svelte";
import type { Writable } from "svelte/store";
import AddConnectionModal from "./AddConnectionModal.svelte";

export let onDelete: () => void = () => {};
export let onSubmit = () => {};
export let url = "";
export let key = "";
export let config = {};

const i18n: Writable<i18nType> = getContext("i18n");
let showConfigModal = false;
</script>

<AddConnectionModal
	edit
	bind:show={showConfigModal}
	connection={{
		url,
		key,
		config
	}}
	{onDelete}
	onSubmit={(connection) => {
		url = connection.url;
		key = connection.key;
		config = connection.config;
		onSubmit(connection);
	}}
/>

<div class="flex w-full gap-2 items-center">
	<Tooltip
		className="w-full relative"
		content={$i18n.t(`WebUI will make requests to "{{url}}/chat/completions"`, {
			url
		})}
		placement="top-start"
	>
		{#if !(config?.enable ?? true)}
			<div
				class="absolute top-0 bottom-0 left-0 right-0 opacity-60 bg-white dark:bg-gray-900 z-10"
			></div>
		{/if}
		<div class="flex w-full">
			<div class="flex-1 relative">
				<input
					class=" outline-none w-full bg-transparent"
					placeholder={$i18n.t('API Base URL')}
					bind:value={url}
					autocomplete="off"
				/>
			</div>

			<SensitiveInput
				inputClassName=" outline-none bg-transparent w-full"
				placeholder={$i18n.t('API Key')}
				bind:value={key}
			/>
		</div>
	</Tooltip>

	<div class="flex gap-1">
		<Tooltip content={$i18n.t('Configure')} className="self-start">
			<button
				class="self-center p-1 bg-transparent hover:bg-gray-100 dark:bg-gray-900 dark:hover:bg-gray-850 rounded-lg transition"
				on:click={() => {
					showConfigModal = true;
				}}
				type="button"
			>
				<Cog6 />
			</button>
		</Tooltip>
	</div>
</div>
