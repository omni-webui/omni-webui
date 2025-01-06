<script lang="ts">
import { goto } from "$app/navigation";
import { page } from "$app/state";
import {
	getPromptByCommand,
	getPrompts,
	updatePromptByCommand,
} from "$lib/apis/prompts";
import PromptEditor from "$lib/components/workspace/Prompts/PromptEditor.svelte";
import { prompts } from "$lib/stores";
import { type i18n } from "i18next";
import { getContext, onMount } from "svelte";
import { toast } from "svelte-sonner";
import { type Writable } from "svelte/store";

const i: Writable<i18n> = getContext("i18n");
let prompt = null;
const onSubmit = async (_prompt) => {
	console.log(_prompt);
	const prompt = await updatePromptByCommand(localStorage.token, _prompt).catch(
		(error) => {
			toast.error(error);
			return null;
		},
	);

	if (prompt) {
		toast.success($i.t("Prompt updated successfully"));
		await prompts.set(await getPrompts(localStorage.token));
		await goto("/workspace/prompts");
	}
};

onMount(async () => {
	const command = page.url.searchParams.get("command");
	if (command) {
		const _prompt = await getPromptByCommand(
			localStorage.token,
			command.replace(/\//g, ""),
		).catch((error) => {
			toast.error(error);
			return null;
		});

		if (_prompt) {
			prompt = {
				title: _prompt.title,
				command: _prompt.command,
				content: _prompt.content,
				access_control: _prompt?.access_control ?? null,
			};
		} else {
			goto("/workspace/prompts");
		}
	} else {
		goto("/workspace/prompts");
	}
});
</script>

{#if prompt}
	<PromptEditor {prompt} {onSubmit} edit />
{/if}
