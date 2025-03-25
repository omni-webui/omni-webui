export type MessageRole = "user" | "assistant" | "system";

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: Date;
}

export interface Chat {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  updatedAt: Date;
  modelId: string;
}

export interface Model {
  id: string;
  name: string;
  description?: string;
  provider: string;
  iconUrl?: string;
}

export interface SuggestedPrompt {
  title: string;
  prompt: string;
  description?: string;
}
