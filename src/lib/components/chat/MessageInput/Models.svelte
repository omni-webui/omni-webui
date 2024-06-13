<script lang="ts">
import { createEventDispatcher } from 'svelte';

import { models } from '$lib/stores';

const dispatch = createEventDispatcher();

export let prompt = '';

let selectedIdx = 0;
let filteredModels = [];

$: filteredModels = $models
	.filter((p) => p.name.includes(prompt.split(' ')?.at(0)?.substring(1) ?? ''))
	.sort((a, b) => a.name.localeCompare(b.name));

$: if (prompt) {
	selectedIdx = 0;
}

export const selectUp = () => {
	selectedIdx = Math.max(0, selectedIdx - 1);
};

export const selectDown = () => {
	selectedIdx = Math.min(selectedIdx + 1, filteredModels.length - 1);
};

const confirmSelect = async (model) => {
	prompt = '';
	dispatch('select', model);
};
</script>

{#if prompt.charAt(0) === '@'}
	{#if filteredModels.length > 0}
		<div class="md:px-2 mb-3 text-left w-full absolute bottom-0 left-0 right-0">
			<div class="flex w-full px-2">
				<div class=" bg-gray-100 dark:bg-gray-700 w-10 rounded-l-xl text-center">
					<div class=" text-lg font-semibold mt-2">@</div>
				</div>

				<div class="max-h-60 flex flex-col w-full rounded-r-xl bg-white">
					<div class="m-1 overflow-y-auto p-1 rounded-r-xl space-y-0.5">
						{#each filteredModels as model, modelIdx}
							<button
								class=" px-3 py-1.5 rounded-xl w-full text-left {modelIdx === selectedIdx
									? ' bg-gray-100 selected-command-option-button'
									: ''}"
								type="button"
								on:click={() => {
									confirmSelect(model);
								}}
								on:mousemove={() => {
									selectedIdx = modelIdx;
								}}
								on:focus={() => {}}
							>
								<div class=" font-medium text-black line-clamp-1">
									{model.name}
								</div>

								<!-- <div class=" text-xs text-gray-600 line-clamp-1">
								{doc.title}
							</div> -->
							</button>
						{/each}
					</div>
				</div>
			</div>
		</div>
	{/if}
{/if}
