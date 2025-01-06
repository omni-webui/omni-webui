<script lang="ts">
import { goto } from "$app/navigation";
import { onMount } from "svelte";

onMount(() => {
	const params = new URLSearchParams(window.location.search);

	const v = params.get("v");
	if (v) {
		goto(`/?youtube=${encodeURIComponent(v)}`);
	} else {
		goto("/");
	}
});
</script>
