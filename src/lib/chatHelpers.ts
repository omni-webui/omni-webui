import type { Chat, Message } from "@/types";
import { format } from "date-fns";
import { nanoid } from "nanoid";

// Default prompt suggestions
export const defaultPrompts = [
  {
    title: "Help me study",
    prompt: "I need help studying for my exam on ",
    description: "Get help with studying for an exam",
  },
  {
    title: "Explain a concept",
    prompt: "Explain the concept of ",
    description: "Get a clear explanation of any concept",
  },
  {
    title: "Coding assistance",
    prompt: "Help me write code for ",
    description: "Get help with coding tasks and problems",
  },
  {
    title: "Creative writing",
    prompt: "Write a short story about ",
    description: "Generate creative writing content",
  },
];

// Generate a short id for new chats/messages
export const generateId = () => nanoid(10);

// Format dates for display
export const formatDate = (date: Date) => {
  return format(new Date(date), "MMM d, yyyy h:mm a");
};

// Get a suitable title for a chat based on first message
export const generateChatTitle = (messages: Message[]): string => {
  if (messages.length === 0) return "New Chat";

  const firstUserMessage = messages.find((m) => m.role === "user");
  if (!firstUserMessage) return "New Chat";

  const content = firstUserMessage.content.trim();

  // Limit to first line, cut off at reasonable length
  const firstLine = content.split("\n")[0] || "";
  const title =
    firstLine.length > 50 ? `${firstLine.substring(0, 50)}...` : firstLine;

  return title || "New Chat";
};

// Filter chats for search
export const filterChats = (chats: Chat[], searchTerm: string): Chat[] => {
  if (!searchTerm.trim()) return chats;

  const lowerSearch = searchTerm.toLowerCase();

  return chats.filter((chat) => {
    // Search in title
    if (chat.title.toLowerCase().includes(lowerSearch)) return true;

    // Search in messages
    return chat.messages.some((message) =>
      message.content.toLowerCase().includes(lowerSearch),
    );
  });
};
