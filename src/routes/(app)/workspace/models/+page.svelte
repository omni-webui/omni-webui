<script lang="ts">
import { getModels } from "$lib/apis";
import Models from "$lib/components/workspace/Models.svelte";
import { models } from "$lib/stores";
import { onMount } from "svelte";

onMount(async () => {
	await Promise.all([
		(async () => {
			models.set(await getModels(localStorage.token));
		})(),
	]);
});
</script>

{#if $models !== null}
	<Models />
{/if}
