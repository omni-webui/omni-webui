import { WEBUI_BASE_URL } from "$lib/constants";

export const getModels = async (token = "", base = false) => {
	let error = null;
	const res = await fetch(
		`${WEBUI_BASE_URL}/api/models${base ? "/base" : ""}`,
		{
			method: "GET",
			headers: {
				Accept: "application/json",
				"Content-Type": "application/json",
				...(token && { authorization: `Bearer ${token}` }),
			},
		},
	)
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			error = err;
			console.log(err);
			return null;
		});

	if (error) {
		throw error;
	}

	const models = res?.data ?? [];
	return models;
};

type ChatCompletedForm = {
	model: string;
	messages: string[];
	chat_id: string;
	session_id: string;
};

export const chatCompleted = async (token: string, body: ChatCompletedForm) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/chat/completed`, {
		method: "POST",
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			...(token && { authorization: `Bearer ${token}` }),
		},
		body: JSON.stringify(body),
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			if ("detail" in err) {
				error = err.detail;
			} else {
				error = err;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const stopTask = async (token: string, id: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/tasks/stop/${id}`, {
		method: "POST",
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			...(token && { authorization: `Bearer ${token}` }),
		},
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			if ("detail" in err) {
				error = err.detail;
			} else {
				error = err;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getTaskConfig = async (token = "") => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/tasks/config`, {
		method: "GET",
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			...(token && { authorization: `Bearer ${token}` }),
		},
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateTaskConfig = async (token: string, config: object) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/tasks/config/update`, {
		method: "POST",
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			...(token && { authorization: `Bearer ${token}` }),
		},
		body: JSON.stringify(config),
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			if ("detail" in err) {
				error = err.detail;
			} else {
				error = err;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const generateTitle = async (
	token: string,
	model: string,
	messages: string[],
	chat_id?: string,
) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/tasks/title/completions`, {
		method: "POST",
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({
			model: model,
			messages: messages,
			...(chat_id && { chat_id: chat_id }),
		}),
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			if ("detail" in err) {
				error = err.detail;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	return res?.choices[0]?.message?.content.replace(/["']/g, "") ?? "New Chat";
};

export const generateTags = async (
	token: string,
	model: string,
	messages: string,
	chat_id?: string,
) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/tasks/tags/completions`, {
		method: "POST",
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({
			model: model,
			messages: messages,
			...(chat_id && { chat_id: chat_id }),
		}),
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			if ("detail" in err) {
				error = err.detail;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	try {
		// Step 1: Safely extract the response string
		const response = res?.choices[0]?.message?.content ?? "";

		// Step 2: Attempt to fix common JSON format issues like single quotes
		const sanitizedResponse = response.replace(/['‘’`]/g, '"'); // Convert single quotes to double quotes for valid JSON

		// Step 3: Find the relevant JSON block within the response
		const jsonStartIndex = sanitizedResponse.indexOf("{");
		const jsonEndIndex = sanitizedResponse.lastIndexOf("}");

		// Step 4: Check if we found a valid JSON block (with both `{` and `}`)
		if (jsonStartIndex !== -1 && jsonEndIndex !== -1) {
			const jsonResponse = sanitizedResponse.substring(
				jsonStartIndex,
				jsonEndIndex + 1,
			);

			// Step 5: Parse the JSON block
			const parsed = JSON.parse(jsonResponse);

			// Step 6: If there's a "tags" key, return the tags array; otherwise, return an empty array
			if (parsed?.tags) {
				return Array.isArray(parsed.tags) ? parsed.tags : [];
			}
			return [];
		}

		// If no valid JSON block found, return an empty array
		return [];
	} catch (e) {
		// Catch and safely return empty array on any parsing errors
		console.error("Failed to parse response: ", e);
		return [];
	}
};

export const generateEmoji = async (
	token: string,
	model: string,
	prompt: string,
	chat_id?: string,
) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/tasks/emoji/completions`, {
		method: "POST",
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({
			model: model,
			prompt: prompt,
			...(chat_id && { chat_id: chat_id }),
		}),
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			if ("detail" in err) {
				error = err.detail;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	const response =
		res?.choices[0]?.message?.content.replace(/["']/g, "") ?? null;

	if (response) {
		if (/\p{Extended_Pictographic}/u.test(response)) {
			return response.match(/\p{Extended_Pictographic}/gu)[0];
		}
	}

	return null;
};

export const generateAutoCompletion = async (
	token: string,
	model: string,
	prompt: string,
	messages?: object[],
	type = "search query",
) => {
	const controller = new AbortController();
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/tasks/auto/completions`, {
		signal: controller.signal,
		method: "POST",
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({
			model: model,
			prompt: prompt,
			...(messages && { messages: messages }),
			type: type,
			stream: false,
		}),
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			if ("detail" in err) {
				error = err.detail;
			}
			return null;
		});

	if (error) {
		throw error;
	}

	const response = res?.choices[0]?.message?.content ?? "";

	try {
		const jsonStartIndex = response.indexOf("{");
		const jsonEndIndex = response.lastIndexOf("}");

		if (jsonStartIndex !== -1 && jsonEndIndex !== -1) {
			const jsonResponse = response.substring(jsonStartIndex, jsonEndIndex + 1);

			// Step 5: Parse the JSON block
			const parsed = JSON.parse(jsonResponse);

			// Step 6: If there's a "queries" key, return the queries array; otherwise, return an empty array
			if (parsed?.text) {
				return parsed.text;
			}
			return "";
		}

		// If no valid JSON block found, return response as is
		return response;
	} catch (e) {
		// Catch and safely return empty array on any parsing errors
		console.error("Failed to parse response: ", e);
		return response;
	}
};

export const generateMoACompletion = async (
	token: string,
	model: string,
	prompt: string,
	responses: string[],
) => {
	const controller = new AbortController();
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/tasks/moa/completions`, {
		signal: controller.signal,
		method: "POST",
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({
			model: model,
			prompt: prompt,
			responses: responses,
			stream: true,
		}),
	}).catch((err) => {
		console.log(err);
		error = err;
		return null;
	});

	if (error) {
		throw error;
	}

	return [res, controller];
};

export const getBackendConfig = async () => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/config`, {
		method: "GET",
		credentials: "include",
		headers: {
			"Content-Type": "application/json",
		},
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getChangelog = async () => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/changelog`, {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
		},
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getVersionUpdates = async () => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/version/updates`, {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
		},
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getModelFilterConfig = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/config/model/filter`, {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const updateModelFilterConfig = async (
	token: string,
	enabled: boolean,
	models: string[],
) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/config/model/filter`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({
			enabled: enabled,
			models: models,
		}),
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getWebhookUrl = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/webhook`, {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res.url;
};

export const updateWebhookUrl = async (token: string, url: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/webhook`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({
			url: url,
		}),
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res.url;
};

export const getCommunitySharingEnabledStatus = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/community_sharing`, {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const toggleCommunitySharingEnabledStatus = async (token: string) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/community_sharing/toggle`, {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err.detail;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

export const getModelConfig = async (
	token: string,
): Promise<GlobalModelConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/config/models`, {
		method: "GET",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res.models;
};

export interface ModelConfig {
	id: string;
	name: string;
	meta: ModelMeta;
	base_model_id?: string;
	params: ModelParams;
}

export interface ModelMeta {
	description?: string;
	capabilities?: object;
	profile_image_url?: string;
}

export type ModelParams = {
	stream_response?: boolean;
};

export type GlobalModelConfig = ModelConfig[];

export const updateModelConfig = async (
	token: string,
	config: GlobalModelConfig,
) => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/config/models`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
		},
		body: JSON.stringify({
			models: config,
		}),
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.log(err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};
