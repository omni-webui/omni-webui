<script lang="ts">
import { settings } from "$lib/stores";
import MultiResponseMessages from "./MultiResponseMessages.svelte";
import ResponseMessage from "./ResponseMessage.svelte";
import UserMessage from "./UserMessage.svelte";

export let chatId: string;
export let idx = 0;
export let history: OmniWebUI.History;
export let messageId: string;
export let user;
export let showPreviousMessage: (message: OmniWebUI.Message) => Promise<void>;
export let showNextMessage: (message: OmniWebUI.Message) => Promise<void>;
export let updateChat: () => Promise<void>;
export let editMessage: (
	messageId: string,
	content: string,
	submit?: boolean,
) => Promise<void>;
export let saveMessage: (
	messageId: string,
	message: OmniWebUI.Message,
) => Promise<void>;
export let deleteMessage: (messageId: string) => Promise<void>;
export let submitMessage: (
	parentId: string | null,
	prompt: string,
) => Promise<void>;
export let regenerateResponse: (message: OmniWebUI.Message) => Promise<void>;
export let continueResponse: () => Promise<void>;
export let mergeResponses: (
	messageId: string,
	responses: string[],
	_chatId: string,
) => Promise<void>;
export let addMessages: ({
	modelId,
	parentId,
	messages,
}: {
	modelId: string;
	parentId: string;
	messages: { role: string; content: string }[];
}) => Promise<void>;
export let triggerScroll: () => void;
export let readOnly = false;
const message = history.messages[messageId];
const parentMessage = message.parentId
	? history.messages[message.parentId]
	: undefined;
</script>

<div
	class="flex flex-col justify-between px-5 mb-3 w-full {($settings?.widescreenMode ?? null)
		? 'max-w-full'
		: 'max-w-5xl'} mx-auto rounded-lg group"
>
	{#if message}
		{#if message.role === 'user'}
			<UserMessage
				{user}
				{history}
				{messageId}
				isFirstMessage={idx === 0}
				siblings={parentMessage
					? parentMessage.childrenIds ?? []
					: (Object.values(history.messages)
							.filter((message) => message.parentId === null)
							.map((message) => message.id) ?? [])}
				{showPreviousMessage}
				{showNextMessage}
				{editMessage}
				{deleteMessage}
				{readOnly}
			/>
		{:else if (parentMessage?.models?.length ?? 1) === 1}
			<ResponseMessage
				{chatId}
				{history}
				{messageId}
				isLastMessage={messageId === history.currentId}
				siblings={parentMessage?.childrenIds ?? []}
				{showPreviousMessage}
				{showNextMessage}
				{updateChat}
				{editMessage}
				{saveMessage}
				{submitMessage}
				{continueResponse}
				{regenerateResponse}
				{addMessages}
				{readOnly}
			/>
		{:else}
			<MultiResponseMessages
				bind:history
				{chatId}
				{messageId}
				isLastMessage={messageId === history?.currentId}
				{updateChat}
				{editMessage}
				{saveMessage}
				{submitMessage}
				{continueResponse}
				{regenerateResponse}
				{mergeResponses}
				{triggerScroll}
				{addMessages}
				{readOnly}
			/>
		{/if}
	{/if}
</div>
