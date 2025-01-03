<script lang="ts">
import { getChatList, updateChatById } from "$lib/apis/chats";
import { user as _user, chats, currentChatPage, settings } from "$lib/stores";
import { type i18n } from "i18next";
import { getContext, tick } from "svelte";
import { toast } from "svelte-sonner";
import { type Writable } from "svelte/store";
import { v4 as uuidv4 } from "uuid";
import Loader from "../common/Loader.svelte";
import Spinner from "../common/Spinner.svelte";
import ChatPlaceholder from "./ChatPlaceholder.svelte";
import Message from "./Messages/Message.svelte";

const i: Writable<i18n> = getContext("i18n");

export let chatId = "";
export let user = $_user;
export let prompt: string;
export let history: OmniWebUI.History;
export let selectedModels: string[];
export let sendPrompt: (
	prompt: string,
	parentId: string,
	{
		modelId,
		modelIdx,
		newChat,
	}?: {
		modelId?: string;
		modelIdx?: number;
		newChat?: boolean;
	},
) => Promise<void>;
export let continueResponse: () => Promise<void> = async () => {};
export let regenerateResponse: (message: OmniWebUI.Message) => Promise<void>;
export let mergeResponses: (
	messageId: string,
	responses: string[],
	_chatId: string,
) => Promise<void>;
export let showMessage: (message: OmniWebUI.Message) => Promise<void> = async (
	_,
) => {};
export let submitMessage: (
	parentId: string | null,
	prompt: string,
) => Promise<void> = async (_, __) => {};
export let addMessages: ({
	modelId,
	parentId,
	messages,
}: {
	modelId: string;
	parentId: string;
	messages: { role: string; content: string }[];
}) => Promise<void>;
export let readOnly = false;
export let bottomPadding = false;
export let autoScroll: boolean;

let messages: OmniWebUI.Message[] = [];
let messagesCount = 20;
let messagesLoading = false;

const loadMoreMessages = async () => {
	// scroll slightly down to disable continuous loading
	const element = document.getElementById("messages-container");
	if (!element) throw new Error("Element not found");
	element.scrollTop = element.scrollTop + 100;

	messagesLoading = true;
	messagesCount += 20;

	await tick();

	messagesLoading = false;
};

$: if (history.currentId) {
	let _messages = [];

	let message: OmniWebUI.Message | null = history.messages[history.currentId];
	while (message && _messages.length <= messagesCount) {
		_messages.unshift({ ...message });
		message = message.parentId ? history.messages[message.parentId] : null;
	}

	messages = _messages;
} else {
	messages = [];
}

$: if (autoScroll && bottomPadding) {
	(async () => {
		await tick();
		scrollToBottom();
	})();
}

const scrollToBottom = () => {
	const element = document.getElementById("messages-container");
	if (!element) throw new Error("Element not found");
	element.scrollTop = element.scrollHeight;
};

const updateChat = async () => {
	await tick();
	await updateChatById(localStorage.token, chatId, {
		history,
		messages: messages,
	});

	currentChatPage.set(1);
	await chats.set(await getChatList(localStorage.token, $currentChatPage));
};

const showPreviousMessage = async (message: OmniWebUI.Message) => {
	if (message.parentId) {
		let messageId =
			history.messages[message.parentId].childrenIds[
				Math.max(
					history.messages[message.parentId].childrenIds.indexOf(message.id) -
						1,
					0,
				)
			];

		if (message.id !== messageId) {
			let messageChildrenIds = history.messages[messageId].childrenIds;

			while (messageChildrenIds.length > 0) {
				messageId = messageChildrenIds.at(-1) as string;
				messageChildrenIds = history.messages[messageId].childrenIds;
			}

			history.currentId = messageId;
		}
	} else {
		let childrenIds = Object.values(history.messages)
			.filter((message) => message.parentId === null)
			.map((message) => message.id);
		let messageId =
			childrenIds[Math.max(childrenIds.indexOf(message.id) - 1, 0)];

		if (message.id !== messageId) {
			let messageChildrenIds = history.messages[messageId].childrenIds;

			while (messageChildrenIds.length !== 0) {
				messageId = messageChildrenIds.at(-1) as string;
				messageChildrenIds = history.messages[messageId].childrenIds;
			}

			history.currentId = messageId;
		}
	}

	await tick();

	if ($settings?.scrollOnBranchChange ?? true) {
		const element = document.getElementById("messages-container");
		if (!element) throw new Error("Element not found");
		autoScroll =
			element.scrollHeight - element.scrollTop <= element.clientHeight + 50;

		setTimeout(() => {
			scrollToBottom();
		}, 100);
	}
};

const showNextMessage = async (message: OmniWebUI.Message) => {
	if (message.parentId !== null) {
		let messageId =
			history.messages[message.parentId].childrenIds[
				Math.min(
					history.messages[message.parentId].childrenIds.indexOf(message.id) +
						1,
					history.messages[message.parentId].childrenIds.length - 1,
				)
			];

		if (message.id !== messageId) {
			let messageChildrenIds = history.messages[messageId].childrenIds;

			while (messageChildrenIds.length !== 0) {
				messageId = messageChildrenIds.at(-1) as string;
				messageChildrenIds = history.messages[messageId].childrenIds;
			}

			history.currentId = messageId;
		}
	} else {
		let childrenIds = Object.values(history.messages)
			.filter((message) => message.parentId === null)
			.map((message) => message.id);
		let messageId =
			childrenIds[
				Math.min(childrenIds.indexOf(message.id) + 1, childrenIds.length - 1)
			];

		if (message.id !== messageId) {
			let messageChildrenIds = history.messages[messageId].childrenIds;

			while (messageChildrenIds.length !== 0) {
				messageId = messageChildrenIds.at(-1) as string;
				messageChildrenIds = history.messages[messageId].childrenIds;
			}

			history.currentId = messageId;
		}
	}

	await tick();

	if ($settings?.scrollOnBranchChange ?? true) {
		const element = document.getElementById("messages-container");
		if (!element) throw new Error("Element not found");
		autoScroll =
			element.scrollHeight - element.scrollTop <= element.clientHeight + 50;

		setTimeout(() => {
			scrollToBottom();
		}, 100);
	}
};

const editMessage = async (
	messageId: string,
	content: string,
	submit = true,
) => {
	if (history.messages[messageId].role === "user") {
		if (submit) {
			// New user message
			let userPrompt = content;
			let userMessageId = uuidv4();

			let userMessage = {
				id: userMessageId,
				parentId: history.messages[messageId].parentId,
				childrenIds: [],
				role: "user",
				content: userPrompt,
				...(history.messages[messageId].files && {
					files: history.messages[messageId].files,
				}),
				models: selectedModels,
			};

			let messageParentId = history.messages[messageId].parentId;

			if (messageParentId !== null) {
				history.messages[messageParentId].childrenIds = [
					...history.messages[messageParentId].childrenIds,
					userMessageId,
				];
			}

			history.messages[userMessageId] = userMessage;
			history.currentId = userMessageId;

			await tick();
			await sendPrompt(userPrompt, userMessageId);
		} else {
			// Edit user message
			history.messages[messageId].content = content;
			await updateChat();
		}
	} else {
		if (submit) {
			// New response message
			const responseMessageId = uuidv4();
			const message = history.messages[messageId];
			const parentId = message.parentId;

			const responseMessage = {
				...message,
				id: responseMessageId,
				parentId: parentId,
				childrenIds: [],
				files: undefined,
				content: content,
				timestamp: Math.floor(Date.now() / 1000), // Unix epoch
			};

			history.messages[responseMessageId] = responseMessage;
			history.currentId = responseMessageId;

			// Append messageId to childrenIds of parent message
			if (parentId !== null) {
				history.messages[parentId].childrenIds = [
					...history.messages[parentId].childrenIds,
					responseMessageId,
				];
			}

			await updateChat();
		} else {
			// Edit response message
			history.messages[messageId].originalContent =
				history.messages[messageId].content;
			history.messages[messageId].content = content;
			await updateChat();
		}
	}
};

const saveMessage = async (messageId: string, message: OmniWebUI.Message) => {
	history.messages[messageId] = message;
	await updateChat();
};

const deleteMessage = async (messageId: string) => {
	const messageToDelete = history.messages[messageId];
	const parentMessageId = messageToDelete.parentId;
	const childMessageIds = messageToDelete.childrenIds ?? [];

	// Collect all grandchildren
	const grandchildrenIds = childMessageIds.flatMap(
		(childId) => history.messages[childId]?.childrenIds ?? [],
	);

	// Update parent's children
	if (parentMessageId && history.messages[parentMessageId]) {
		history.messages[parentMessageId].childrenIds = [
			...history.messages[parentMessageId].childrenIds.filter(
				(id) => id !== messageId,
			),
			...grandchildrenIds,
		];
	}

	// Update grandchildren's parent
	for (const grandchildId of grandchildrenIds) {
		if (history.messages[grandchildId]) {
			history.messages[grandchildId].parentId = parentMessageId;
		}
	}

	// Delete the message and its children
	for (const id of [messageId, ...childMessageIds]) {
		history.messages[id] = undefined;
	}

	await tick();

	showMessage({ id: parentMessageId });

	// Update the chat
	await updateChat();
};

const triggerScroll = () => {
	if (autoScroll) {
		const element = document.getElementById(
			"messages-container",
		) as HTMLElement;
		autoScroll =
			element.scrollHeight - element.scrollTop <= element.clientHeight + 50;
		setTimeout(() => {
			scrollToBottom();
		}, 100);
	}
};
</script>

<div class="h-full flex pt-8">
	{#if Object.keys(history?.messages ?? {}).length == 0}
		<ChatPlaceholder
			modelIds={selectedModels}
			submitPrompt={async (p) => {
				let text = p;

				if (p.includes('{{CLIPBOARD}}')) {
					const clipboardText = await navigator.clipboard.readText().catch((err) => {
						toast.error($i.t('Failed to read clipboard contents'));
						return '{{CLIPBOARD}}';
					});

					text = p.replaceAll('{{CLIPBOARD}}', clipboardText);
				}

				prompt = text;

				await tick();

				const chatInputContainerElement = document.getElementById('chat-input-container');
				if (chatInputContainerElement) {
					prompt = p;

					chatInputContainerElement.style.height = '';
					chatInputContainerElement.style.height =
						Math.min(chatInputContainerElement.scrollHeight, 200) + 'px';
					chatInputContainerElement.focus();
				}

				await tick();
			}}
		/>
	{:else}
		<div class="w-full pt-2">
			{#key chatId}
				<div class="w-full">
					{#if messages.at(0)?.parentId !== null}
						<Loader
							on:visible={(e) => {
								console.log('visible');
								if (!messagesLoading) {
									loadMoreMessages();
								}
							}}
						>
							<div class="w-full flex justify-center py-1 text-xs animate-pulse items-center gap-2">
								<Spinner className=" size-4" />
								<div class=" ">Loading...</div>
							</div>
						</Loader>
					{/if}

					{#each messages as message, messageIdx (message.id)}
						<Message
							{chatId}
							bind:history
							messageId={message.id}
							idx={messageIdx}
							{user}
							{showPreviousMessage}
							{showNextMessage}
							{updateChat}
							{editMessage}
							{deleteMessage}
							{saveMessage}
							{submitMessage}
							{regenerateResponse}
							{continueResponse}
							{mergeResponses}
							{addMessages}
							{triggerScroll}
							{readOnly}
						/>
					{/each}
				</div>
				<div class="pb-12" />
				{#if bottomPadding}
					<div class="  pb-6" />
				{/if}
			{/key}
		</div>
	{/if}
</div>
