import OpenAI from "openai";

export const client = new OpenAI({
  apiKey: import.meta.env.OPENAI_API_KEY,
  baseURL: import.meta.env.OPENAI_BASE_URL,
  dangerouslyAllowBrowser: true, // Allow running in the browser because backend is under control.
});
