import type { Model, Settings } from '$lib/stores';

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
