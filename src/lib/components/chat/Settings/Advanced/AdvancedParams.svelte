<script lang="ts">
import { getContext, createEventDispatcher } from 'svelte';
import type { I18n, AdvancedSettingParameters } from '$lib/types';

const dispatch = createEventDispatcher();

const i18n: I18n = getContext('i18n');

export let params: Partial<AdvancedSettingParameters> = {};

$: if (params) {
	dispatch('change', params);
}
</script>

<div class=" space-y-1 text-xs">
	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Seed')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.seed = params.seed === undefined ? 0 : undefined;
				}}
			>
				{#if params.seed === undefined}
					<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
				{:else}
					<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
				{/if}
			</button>
		</div>

		{#if params.seed !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-none"
						type="number"
						placeholder="Enter Seed"
						bind:value={params.seed}
						autocomplete="off"
						min="0"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Stop Sequence')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.stop = params.stop === undefined ? '' : undefined;
				}}
			>
				{#if params.stop === undefined}
					<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
				{:else}
					<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
				{/if}
			</button>
		</div>

		{#if params.stop !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						class="w-full rounded-lg py-2 px-4 text-sm dark:text-gray-300 dark:bg-gray-850 outline-none"
						type="text"
						placeholder={$i18n.t('Enter stop sequence')}
						bind:value={params.stop}
						autocomplete="off"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Temperature')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.temperature = params.temperature === undefined ? 0.8 : undefined;
				}}
			>
				{#if params.temperature === undefined}
					<span class="ml-2 self-center"> {$i18n.t('Default')} </span>
				{:else}
					<span class="ml-2 self-center"> {$i18n.t('Custom')} </span>
				{/if}
			</button>
		</div>

		{#if params.temperature !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="1"
						step="0.05"
						bind:value={params.temperature}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.temperature}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="1"
						step="0.05"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Mirostat')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.mirostat = params.mirostat === undefined ? 0 : undefined;
				}}
			>
				{#if params.mirostat === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.mirostat !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="2"
						step="1"
						bind:value={params.mirostat}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.mirostat}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="2"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Mirostat Eta')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.mirostat_eta = params.mirostat_eta === undefined ? 0.1 : undefined;
				}}
			>
				{#if params.mirostat_eta === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.mirostat_eta !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="1"
						step="0.05"
						bind:value={params.mirostat_eta}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.mirostat_eta}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="1"
						step="0.05"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Mirostat Tau')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.mirostat_tau = params.mirostat_tau === undefined ? 5.0 : undefined;
				}}
			>
				{#if params.mirostat_tau === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.mirostat_tau !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="10"
						step="0.5"
						bind:value={params.mirostat_tau}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.mirostat_tau}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="10"
						step="0.5"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Top K')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.top_k = params.top_k === undefined ? 40 : undefined;
				}}
			>
				{#if params.top_k === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.top_k !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="100"
						step="0.5"
						bind:value={params.top_k}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.top_k}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="100"
						step="0.5"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Top P')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.top_p = params.top_p === undefined ? 0.9 : undefined;
				}}
			>
				{#if params.top_p === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.top_p !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="1"
						step="0.05"
						bind:value={params.top_p}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.top_p}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="1"
						step="0.05"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Frequency Penalty')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.frequency_penalty = params.frequency_penalty === undefined ? 1.1 : undefined;
				}}
			>
				{#if params.frequency_penalty === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.frequency_penalty !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="2"
						step="0.05"
						bind:value={params.frequency_penalty}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.frequency_penalty}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="2"
						step="0.05"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Repeat Last N')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.repeat_last_n = params.repeat_last_n === undefined ? 64 : undefined;
				}}
			>
				{#if params.repeat_last_n === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.repeat_last_n !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-1"
						max="128"
						step="1"
						bind:value={params.repeat_last_n}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.repeat_last_n}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-1"
						max="128"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Tfs Z')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.tfs_z = params.tfs_z === undefined ? 1 : undefined;
				}}
			>
				{#if params.tfs_z === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.tfs_z !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="0"
						max="2"
						step="0.05"
						bind:value={params.tfs_z}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div>
					<input
						bind:value={params.tfs_z}
						type="number"
						class=" bg-transparent text-center w-14"
						min="0"
						max="2"
						step="0.05"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Context Length')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.num_ctx = params.num_ctx === undefined ? 2048 : undefined;
				}}
			>
				{#if params.num_ctx === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.num_ctx !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-1"
						max="10240000"
						step="1"
						bind:value={params.num_ctx}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div class="">
					<input
						bind:value={params.num_ctx}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-1"
						step="10"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">
				{$i18n.t('Max Tokens (num_predict)')}
			</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.max_tokens = params.max_tokens === undefined ? 128 : undefined;
				}}
			>
				{#if params.max_tokens === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.max_tokens !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="-2"
						max="16000"
						step="1"
						bind:value={params.max_tokens}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div class="">
					<input
						bind:value={params.max_tokens}
						type="number"
						class=" bg-transparent text-center w-14"
						min="-2"
						max="16000"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('use_mmap (Ollama)')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.use_mmap = params.use_mmap === undefined ? true : undefined;
				}}
			>
				{#if !params.use_mmap}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('On')}</span>
				{/if}
			</button>
		</div>
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('use_mlock (Ollama)')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.use_mlock = params.use_mlock === undefined ? true : undefined;
				}}
			>
				{#if !params.use_mlock}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('On')}</span>
				{/if}
			</button>
		</div>
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('num_thread (Ollama)')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.num_thread = params.num_thread === undefined ? 2 : undefined;
				}}
			>
				{#if params.num_thread === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.num_thread !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<input
						id="steps-range"
						type="range"
						min="1"
						max="256"
						step="1"
						bind:value={params.num_thread}
						class="w-full h-2 rounded-lg appearance-none cursor-pointer dark:bg-gray-700"
					/>
				</div>
				<div class="">
					<input
						bind:value={params.num_thread}
						type="number"
						class=" bg-transparent text-center w-14"
						min="1"
						max="256"
						step="1"
					/>
				</div>
			</div>
		{/if}
	</div>

	<div class=" py-0.5 w-full justify-between">
		<div class="flex w-full justify-between">
			<div class=" self-center text-xs font-medium">{$i18n.t('Template')}</div>

			<button
				class="p-1 px-3 text-xs flex rounded transition"
				type="button"
				on:click={() => {
					params.template = params.template === undefined ? '' : undefined;
				}}
			>
				{#if params.template === undefined}
					<span class="ml-2 self-center">{$i18n.t('Default')}</span>
				{:else}
					<span class="ml-2 self-center">{$i18n.t('Custom')}</span>
				{/if}
			</button>
		</div>

		{#if params.template !== undefined}
			<div class="flex mt-0.5 space-x-2">
				<div class=" flex-1">
					<textarea
						class="px-3 py-1.5 text-sm w-full bg-transparent border dark:border-gray-600 outline-none rounded-lg -mb-1"
						placeholder="Write your model template content here"
						rows="4"
						bind:value={params.template}
					/>
				</div>
			</div>
		{/if}
	</div>
</div>
