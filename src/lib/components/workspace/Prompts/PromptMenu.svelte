<script lang="ts">
import Dropdown from "$lib/components/common/Dropdown.svelte";
import Tooltip from "$lib/components/common/Tooltip.svelte";
import ArrowDownTray from "$lib/components/icons/ArrowDownTray.svelte";
import DocumentDuplicate from "$lib/components/icons/DocumentDuplicate.svelte";
import GarbageBin from "$lib/components/icons/GarbageBin.svelte";
import Share from "$lib/components/icons/Share.svelte";
import { flyAndScale } from "$lib/utils/transitions";
import { DropdownMenu } from "bits-ui";
import { type i18n } from "i18next";
import { getContext } from "svelte";
import { type Writable } from "svelte/store";

const i: Writable<i18n> = getContext("i18n");

export let shareHandler: () => void;
export let cloneHandler: () => void;
export let exportHandler: () => void;
export let deleteHandler: () => Promise<void>;

let show = false;
</script>

<Dropdown bind:show>
	<Tooltip content={$i.t('More')}>
		<slot />
	</Tooltip>

	<div slot="content">
		<DropdownMenu.Content
			class="w-full max-w-[160px] rounded-xl px-1 py-1.5 border border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow"
			sideOffset={-2}
			side="bottom"
			align="start"
			transition={flyAndScale}
		>
			<DropdownMenu.Item
				class="flex gap-2 items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800  rounded-md"
				on:click={shareHandler}
			>
				<Share />
				<div class="flex items-center">{$i.t('Share')}</div>
			</DropdownMenu.Item>

			<DropdownMenu.Item
				class="flex gap-2 items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
				on:click={() => {
					cloneHandler();
				}}
			>
				<DocumentDuplicate />

				<div class="flex items-center">{$i.t('Clone')}</div>
			</DropdownMenu.Item>

			<DropdownMenu.Item
				class="flex gap-2 items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
				on:click={() => {
					exportHandler();
				}}
			>
				<ArrowDownTray />

				<div class="flex items-center">{$i.t('Export')}</div>
			</DropdownMenu.Item>

			<hr class="border-gray-100 dark:border-gray-800 my-1" />

			<DropdownMenu.Item
				class="flex  gap-2  items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
				on:click={() => {
					deleteHandler();
				}}
			>
				<GarbageBin strokeWidth="2" />
				<div class="flex items-center">{$i.t('Delete')}</div>
			</DropdownMenu.Item>
		</DropdownMenu.Content>
	</div>
</Dropdown>
