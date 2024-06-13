<script lang="ts">
import { DropdownMenu } from 'bits-ui';
import { getContext } from 'svelte';

import fileSaver from 'file-saver';
const { saveAs } = fileSaver;

import { flyAndScale } from '$lib/utils/transitions';

import Dropdown from '$lib/components/common/Dropdown.svelte';
import Tags from '$lib/components/chat/Tags.svelte';

import { downloadChatAsPDF } from '$lib/apis/utils';

const i18n = getContext('i18n');

export let shareHandler: () => void;

// export let tagHandler: Function;

export let chat;
export let onClose: () => void = () => {};

const downloadTxt = async () => {
	const _chat = chat.chat;
	console.log('download', chat);

	const chatText = _chat.messages.reduce((a, message) => {
		return `${a}### ${message.role.toUpperCase()}\n${message.content}\n\n`;
	}, '');

	let blob = new Blob([chatText], {
		type: 'text/plain'
	});

	saveAs(blob, `chat-${_chat.title}.txt`);
};

const downloadPdf = async () => {
	const _chat = chat.chat;
	console.log('download', chat);

	const blob = await downloadChatAsPDF(_chat);

	// Create a URL for the blob
	const url = window.URL.createObjectURL(blob);

	// Create a link element to trigger the download
	const a = document.createElement('a');
	a.href = url;
	a.download = `chat-${_chat.title}.pdf`;

	// Append the link to the body and click it programmatically
	document.body.appendChild(a);
	a.click();

	// Remove the link from the body
	document.body.removeChild(a);

	// Revoke the URL to release memory
	window.URL.revokeObjectURL(url);
};

const downloadJSONExport = async () => {
	let blob = new Blob([JSON.stringify([chat])], {
		type: 'application/json'
	});
	saveAs(blob, `chat-export-${Date.now()}.json`);
};
</script>

<Dropdown
	on:change={(e) => {
		if (e.detail === false) {
			onClose();
		}
	}}
>
	<slot />

	<div slot="content">
		<DropdownMenu.Content
			class="w-full max-w-[200px] rounded-xl px-1 py-1.5 border border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
			sideOffset={8}
			side="bottom"
			align="end"
			transition={flyAndScale}
		>
			<DropdownMenu.Item
				class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
				id="chat-share-button"
				on:click={() => {
					shareHandler();
				}}
			>
				<svg
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 24 24"
					fill="currentColor"
					class="size-4"
				>
					<path
						fill-rule="evenodd"
						d="M15.75 4.5a3 3 0 1 1 .825 2.066l-8.421 4.679a3.002 3.002 0 0 1 0 1.51l8.421 4.679a3 3 0 1 1-.729 1.31l-8.421-4.678a3 3 0 1 1 0-4.132l8.421-4.679a3 3 0 0 1-.096-.755Z"
						clip-rule="evenodd"
					/>
				</svg>
				<div class="flex items-center">{$i18n.t('Share')}</div>
			</DropdownMenu.Item>
			<!-- <DropdownMenu.Item
					class="flex gap-2 items-center px-3 py-2 text-sm  font-medium cursor-pointer"
					on:click={() => {
						downloadHandler();
					}}
				/> -->
			<DropdownMenu.Sub>
				<DropdownMenu.SubTrigger
					class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						fill="none"
						viewBox="0 0 24 24"
						stroke-width="1.5"
						stroke="currentColor"
						class="size-4"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							d="M3 16.5v2.25A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75V16.5M16.5 12 12 16.5m0 0L7.5 12m4.5 4.5V3"
						/>
					</svg>

					<div class="flex items-center">{$i18n.t('Download')}</div>
				</DropdownMenu.SubTrigger>
				<DropdownMenu.SubContent
					class="w-full rounded-lg px-1 py-1.5 border border-gray-300/30 dark:border-gray-700/50 z-50 bg-white dark:bg-gray-850 dark:text-white shadow-lg"
					transition={flyAndScale}
					sideOffset={8}
				>
					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						on:click={() => {
							downloadJSONExport();
						}}
					>
						<div class="flex items-center line-clamp-1">
							{$i18n.t('Export chat (.json)')}
						</div>
					</DropdownMenu.Item>
					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						on:click={() => {
							downloadTxt();
						}}
					>
						<div class="flex items-center line-clamp-1">
							{$i18n.t('Plain text (.txt)')}
						</div>
					</DropdownMenu.Item>

					<DropdownMenu.Item
						class="flex gap-2 items-center px-3 py-2 text-sm  cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 rounded-md"
						on:click={() => {
							downloadPdf();
						}}
					>
						<div class="flex items-center line-clamp-1">
							{$i18n.t('PDF document (.pdf)')}
						</div>
					</DropdownMenu.Item>
				</DropdownMenu.SubContent>
			</DropdownMenu.Sub>

			<hr class="border-gray-100 dark:border-gray-800 mt-2.5 mb-1.5" />

			<div class="flex p-1">
				<Tags chatId={chat.id} />
			</div>
		</DropdownMenu.Content>
	</div>
</Dropdown>
