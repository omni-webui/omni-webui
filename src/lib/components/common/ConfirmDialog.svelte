<script lang="ts">
import { flyAndScale } from "$lib/utils/transitions";
import { type i18n } from "i18next";
import { createEventDispatcher, getContext, onMount } from "svelte";
import { type Writable } from "svelte/store";
import { fade } from "svelte/transition";

const i: Writable<i18n> = getContext("i18n");
export let title = "";
export let message = "";
export let cancelLabel = $i.t("Cancel");
export let confirmLabel = $i.t("Confirm");
export let onConfirm = () => {};
export let input = false;
export let inputPlaceholder = "";
export let inputValue = "";
export let show = false;

const dispatch = createEventDispatcher();
let modalElement: HTMLDivElement | null = null;
let mounted = false;

const handleKeyDown = (event: KeyboardEvent) => {
	if (event.key === "Escape") {
		console.log("Escape");
		show = false;
	}

	if (event.key === "Enter") {
		console.log("Enter");
		confirmHandler();
	}
};

const confirmHandler = async () => {
	show = false;
	await onConfirm();
	dispatch("confirm", inputValue);
};

onMount(() => {
	mounted = true;
});

$: if (mounted) {
	if (show && modalElement) {
		document.body.appendChild(modalElement);

		window.addEventListener("keydown", handleKeyDown);
		document.body.style.overflow = "hidden";
	} else if (modalElement) {
		window.removeEventListener("keydown", handleKeyDown);
		document.body.removeChild(modalElement);

		document.body.style.overflow = "unset";
	}
}
</script>

{#if show}
	<!-- svelte-ignore a11y-click-events-have-key-events -->
	<!-- svelte-ignore a11y-no-static-element-interactions -->
	<div
		bind:this={modalElement}
		class=" fixed top-0 right-0 left-0 bottom-0 bg-black/60 w-full h-screen max-h-[100dvh] flex justify-center z-[99999999] overflow-hidden overscroll-contain"
		in:fade={{ duration: 10 }}
		on:mousedown={() => {
			show = false;
		}}
	>
		<div
			class=" m-auto rounded-2xl max-w-full w-[32rem] mx-2 bg-gray-50 dark:bg-gray-950 max-h-[100dvh] shadow-3xl"
			in:flyAndScale
			on:mousedown={(e) => {
				e.stopPropagation();
			}}
		>
			<div class="px-[1.75rem] py-6 flex flex-col">
				<div class=" text-lg font-semibold dark:text-gray-200 mb-2.5">
					{#if title !== ''}
						{title}
					{:else}
						{$i.t('Confirm your action')}
					{/if}
				</div>

				<slot>
					<div class=" text-sm text-gray-500 flex-1">
						{#if message !== ''}
							{message}
						{:else}
							{$i.t('This action cannot be undone. Do you wish to continue?')}
						{/if}

						{#if input}
							<textarea
								bind:value={inputValue}
								placeholder={inputPlaceholder ? inputPlaceholder : $i.t('Enter your message')}
								class="w-full mt-2 rounded-lg px-4 py-2 text-sm dark:text-gray-300 dark:bg-gray-900 outline-none resize-none"
								rows="3"
								required
							/>
						{/if}
					</div>
				</slot>

				<div class="mt-6 flex justify-between gap-1.5">
					<button
						class="bg-gray-100 hover:bg-gray-200 text-gray-800 dark:bg-gray-850 dark:hover:bg-gray-800 dark:text-white font-medium w-full py-2.5 rounded-lg transition"
						on:click={() => {
							show = false;
							dispatch('cancel');
						}}
						type="button"
					>
						{cancelLabel}
					</button>
					<button
						class="bg-gray-900 hover:bg-gray-850 text-gray-100 dark:bg-gray-100 dark:hover:bg-white dark:text-gray-800 font-medium w-full py-2.5 rounded-lg transition"
						on:click={() => {
							confirmHandler();
						}}
						type="button"
					>
						{confirmLabel}
					</button>
				</div>
			</div>
		</div>
	</div>
{/if}

<style>
	.modal-content {
		animation: scaleUp 0.1s ease-out forwards;
	}

	@keyframes scaleUp {
		from {
			transform: scale(0.985);
			opacity: 0;
		}
		to {
			transform: scale(1);
			opacity: 1;
		}
	}
</style>
