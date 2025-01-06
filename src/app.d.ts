// See https://kit.svelte.dev/docs/types#app
// for information about these interfaces
declare global {
	namespace App {
		// interface Error {}
		// interface Locals {}
		// interface PageData {}
		// interface Platform {}
	}
	namespace OmniWebUI {
		interface Message {
			id: string;
			parentId?: string;
			childrenIds: string[];
			model?: string;
			modelIdx?: number;
			models?: string[];
			content: string;
			files?: { type: string; url: string }[];
			timestamp: number;
			role: string;
			statusHistory?: {
				done: boolean;
				action: string;
				description: string;
				urls?: string[];
				query?: string;
			}[];
			status?: {
				done: boolean;
				action: string;
				description: string;
				urls?: string[];
				query?: string;
			};
			done: boolean;
			error?: boolean | { content: string };
			sources?: string[];
			code_executions?: {
				uuid: string;
				name: string;
				code: string;
				language?: string;
				result?: {
					error?: string;
					output?: string;
					files?: { name: string; url: string }[];
				};
			}[];
			info?: {
				openai?: boolean;
				prompt_tokens?: number;
				completion_tokens?: number;
				total_tokens?: number;
				eval_count?: number;
				eval_duration?: number;
				prompt_eval_count?: number;
				prompt_eval_duration?: number;
				total_duration?: number;
				load_duration?: number;
				usage?: unknown;
			};
			annotation?: { type: string; rating: number };
			merged?: boolean;
		}
		interface History {
			currentId?: string;
			messages: Record<string, Message>;
		}
		type File = (
			| { type: "image"; url: string; itemId: string }
			| {
					type: "file";
					url: string;
					size: number;
					file?: string;
					id: string | null;
					name: string;
					error?: string;
					itemId: string;
			  }
			| {
					type: "doc";
					url: string;
					error?: string;
			  }
		) & {
			name: string;
			status: "uploading" | "uploaded";
			collection_name?: string;
		};
	}
}

export {};
