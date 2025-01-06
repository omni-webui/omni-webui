<script lang="ts">
import { WEBUI_BASE_URL } from "$lib/constants";
import { type i18n } from "i18next";
import { getContext } from "svelte";
import { type Writable } from "svelte/store";
import Marquee from "./common/Marquee.svelte";
import SlideShow from "./common/SlideShow.svelte";
import ArrowRightCircle from "./icons/ArrowRightCircle.svelte";

export let show = true;
export let getStartedHandler = () => {};

const i: Writable<i18n> = getContext("i18n");
</script>

{#if show}
	<div class="w-full h-screen max-h-[100dvh] text-white relative">
		<div class="fixed m-10 z-50">
			<div class="flex space-x-2">
				<div class=" self-center">
					<img
						crossorigin="anonymous"
						src="{WEBUI_BASE_URL}/static/favicon.png"
						class=" w-6 rounded-full"
						alt="logo"
					/>
				</div>
			</div>
		</div>

		<SlideShow duration={5000} />

		<div
			class="w-full h-full absolute top-0 left-0 bg-gradient-to-t from-20% from-black to-transparent"
		></div>

		<div class="w-full h-full absolute top-0 left-0 backdrop-blur-sm bg-black/50"></div>

		<div class="relative bg-transparent w-full min-h-screen flex z-10">
			<div class="flex flex-col justify-end w-full items-center pb-10 text-center">
				<div class="text-5xl lg:text-7xl font-secondary">
					<Marquee
						duration={5000}
						words={[
							$i.t('Explore the cosmos'),
							$i.t('Unlock mysteries'),
							$i.t('Chart new frontiers'),
							$i.t('Dive into knowledge'),
							$i.t('Discover wonders'),
							$i.t('Ignite curiosity'),
							$i.t('Forge new paths'),
							$i.t('Unravel secrets'),
							$i.t('Pioneer insights'),
							$i.t('Embark on adventures')
						]}
					/>

					<div class="mt-0.5">{$i.t(`wherever you are`)}</div>
				</div>

				<div class="flex justify-center mt-8">
					<div class="flex flex-col justify-center items-center">
						<button
							class="relative z-20 flex p-1 rounded-full bg-white/5 hover:bg-white/10 transition font-medium text-sm"
							on:click={() => {
								getStartedHandler();
							}}
						>
							<ArrowRightCircle className="size-6" />
						</button>
						<div class="mt-1.5 font-primary text-base font-medium">{$i.t(`Get started`)}</div>
					</div>
				</div>
			</div>

			<!-- <div class="absolute bottom-12 left-0 right-0 w-full"></div> -->
		</div>
	</div>
{/if}
