import type { Model } from '$lib/stores';
import type { i18n } from 'i18next';
import type { Writable } from 'svelte/store';

export type Banner = {
	id: string;
	type: string;
	title?: string;
	content: string;
	url?: string;
	dismissible?: boolean;
	timestamp: number;
};

export type Message = {
	model: string;
	content: string;
};

export type GetModelsFunctionType = (token?: string) => Promise<Model[]>;
export type SaveSettingsFunctionType = (settings: Partial<Settings>) => void;

export type I18n = Writable<i18n>;

export type Settings = {
	models: string[];
	conversationMode: boolean;
	speechAutoSend: boolean;
	responseAutoPlayback: boolean;
	audio: Partial<AudioSettings>;
	showUsername: boolean;
	saveChatHistory: boolean;
	notificationEnabled: boolean;
	title: Partial<TitleSettings>;
	splitLargeDeltas: boolean;
	chatDirection: 'LTR' | 'RTL';

	system: string;
	requestFormat: string;
	keepAlive: string | number;
	repeat_penalty: string;
	options: Partial<ModelOptions>;

	params: Partial<Parameters & { stop: string[] }>;
};

type ModelOptions = {
	stop: boolean;
};

type AudioSettings = {
	STTEngine: string;
	TTSEngine: string;
	speaker: string;
	model: string;
	nonLocalVoices: boolean;
};

type TitleSettings = {
	auto: boolean;
	model: string;
	modelExternal: string;
	prompt: string;
};

type Parameters = {
	seed: number;
	temperature: number;
	frequency_penalty: number;
	mirostat: Mirostat;
	mirostat_eta: number;
	mirostat_tau: number;
	repeat_last_n: number;
	tfs_z: number;
	max_tokens: number;
	top_k: number;
	top_p: number;
	num_ctx: number;
	use_mmap: boolean;
	use_mlock: boolean;
	num_thread: number;
	template: string;
};

export type AdvancedSettingParameters = Parameters & { stop: string };

enum Mirostat {
	OFF = 0,
	ON = 1,
	V2 = 2
}
