<script lang="ts">
import { goto } from "$app/navigation";
import { page } from "$app/state";
import { getModels } from "$lib/apis";
import { getChatByShareId } from "$lib/apis/chats";
import { getUserById } from "$lib/apis/users";
import Messages from "$lib/components/chat/Messages.svelte";
import { WEBUI_NAME, chatId, models } from "$lib/stores";
import { convertMessagesToHistory, createMessagesList } from "$lib/utils";
import dayjs from "dayjs";
import { type i18n } from "i18next";
import { getContext, tick } from "svelte";
import { type Writable } from "svelte/store";

const i: Writable<i18n> = getContext("i18n");

let loaded = false;

let autoScroll = true;
let processing = "";

let selectedModels = [""];

let chat = null;
let user = null;

let title = "";
let files = [];

let messages = [];
let history = {
	messages: {},
	currentId: null,
};

$: messages = createMessagesList(history, history.currentId);

$: if (page.params.id) {
	(async () => {
		if (await loadSharedChat()) {
			await tick();
			loaded = true;
		} else {
			await goto("/");
		}
	})();
}

//////////////////////////
// Web functions
//////////////////////////

const loadSharedChat = async () => {
	await models.set(await getModels(localStorage.token));
	await chatId.set(page.params.id);
	chat = await getChatByShareId(localStorage.token, $chatId).catch(
		async (error) => {
			await goto("/");
			return null;
		},
	);

	if (chat) {
		user = await getUserById(localStorage.token, chat.user_id).catch(
			(error) => {
				console.error(error);
				return null;
			},
		);

		const chatContent = chat.chat;

		if (chatContent) {
			console.log(chatContent);

			selectedModels =
				(chatContent?.models ?? undefined) !== undefined
					? chatContent.models
					: [chatContent.models ?? ""];
			history =
				(chatContent?.history ?? undefined) !== undefined
					? chatContent.history
					: convertMessagesToHistory(chatContent.messages);
			title = chatContent.title;

			autoScroll = true;
			await tick();

			if (messages.length > 0) {
				history.messages[messages.at(-1).id].done = true;
			}
			await tick();

			return true;
		}
		return null;
	}
};
</script>

<svelte:head>
	<title>
		{title
			? `${title.length > 30 ? `${title.slice(0, 30)}...` : title} | ${$WEBUI_NAME}`
			: `${$WEBUI_NAME}`}
	</title>
</svelte:head>

{#if loaded}
	<div
		class="min-h-screen max-h-screen w-full flex flex-col text-gray-700 dark:text-gray-100 bg-white dark:bg-gray-900"
	>
		<div class="flex flex-col flex-auto justify-center py-8">
			<div class="px-3 w-full max-w-5xl mx-auto">
				<div>
					<div class=" text-3xl font-semibold line-clamp-1">
						{title}
					</div>

					<div class=" mt-1 text-gray-400">
						{dayjs(chat.chat.timestamp).format($i.t('MMMM DD, YYYY'))}
					</div>
				</div>

				<hr class="border-gray-50 dark:border-gray-850 mt-6 mb-2" />
			</div>

			<div class=" flex flex-col w-full flex-auto overflow-auto h-0" id="messages-container">
				<div class=" h-full w-full flex flex-col py-4">
					<div class="py-2">
						<Messages
							{user}
							chatId={$chatId}
							readOnly={true}
							{selectedModels}
							{processing}
							bind:history
							bind:messages
							bind:autoScroll
							bottomPadding={files.length > 0}
							sendPrompt={() => {}}
							regenerateResponse={() => {}}
						/>
					</div>
				</div>
			</div>
		</div>
	</div>
{/if}
