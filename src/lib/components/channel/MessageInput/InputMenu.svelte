<script lang="ts">
import Dropdown from "$lib/components/common/Dropdown.svelte";
import Tooltip from "$lib/components/common/Tooltip.svelte";
import CameraSolid from "$lib/components/icons/CameraSolid.svelte";
import DocumentArrowUpSolid from "$lib/components/icons/DocumentArrowUpSolid.svelte";
import { tools as _tools, mobile } from "$lib/stores";
import { flyAndScale } from "$lib/utils/transitions";
import { DropdownMenu } from "bits-ui";
import { getContext } from "svelte";

const i18n = getContext("i18n");

export let screenCaptureHandler: Function;
export let uploadFilesHandler: Function;
export let onClose: Function = () => {};

let show = false;

$: if (show) {
	init();
}

const init = async () => {};
</script>

<Dropdown
	bind:show
	on:change={(e) => {
		if (e.detail === false) {
			onClose();
		}
	}}
>
	<Tooltip content={$i18n.t('More')}>
		<slot />
	</Tooltip>

	<div slot="content">
		<DropdownMenu.Content
			class="w-full max-w-[200px] rounded-xl px-1 py-1  border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow"
			sideOffset={15}
			alignOffset={-8}
			side="top"
			align="start"
			transition={flyAndScale}
		>
			{#if !$mobile}
				<DropdownMenu.Item
					class="flex gap-2 items-center px-3 py-2 text-sm  font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800  rounded-xl"
					on:click={() => {
						screenCaptureHandler();
					}}
				>
					<CameraSolid />
					<div class=" line-clamp-1">{$i18n.t('Capture')}</div>
				</DropdownMenu.Item>
			{/if}

			<DropdownMenu.Item
				class="flex gap-2 items-center px-3 py-2 text-sm font-medium cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-xl"
				on:click={() => {
					uploadFilesHandler();
				}}
			>
				<DocumentArrowUpSolid />
				<div class="line-clamp-1">{$i18n.t('Upload Files')}</div>
			</DropdownMenu.Item>
		</DropdownMenu.Content>
	</div>
</Dropdown>
