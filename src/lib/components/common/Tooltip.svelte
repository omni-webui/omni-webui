<script lang="ts">
import { onDestroy } from 'svelte';
import tippy, { type Props, type Instance } from 'tippy.js';

export let placement = 'top';
export let content = `I'm a tooltip!`;
export let touch = true;
export let className = 'flex';

let tooltipElement: HTMLDivElement;
let tooltipInstance: Instance<Props>;

$: if (tooltipElement && content) {
	if (tooltipInstance) {
		tooltipInstance.setContent(content);
	} else {
		tooltipInstance = tippy(tooltipElement, {
			content: content,
			placement: placement,
			allowHTML: true,
			touch: touch
		});
	}
} else if (tooltipInstance && content === '') {
	if (tooltipInstance) {
		tooltipInstance.destroy();
	}
}

onDestroy(() => {
	if (tooltipInstance) {
		tooltipInstance.destroy();
	}
});
</script>

<div bind:this={tooltipElement} aria-label={content} class={className}>
	<slot />
</div>
