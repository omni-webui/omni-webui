import { client } from "@/lib/api";
import type { Chat, Message } from "@/types";
import type { Model } from "openai/resources/models";
import { v4 as uuidv4 } from "uuid";
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ChatStore {
  chats: Chat[];
  selectedChatId: string | null;
  models: Model[];
  selectedModelId: string;

  // Actions
  createChat: (modelId?: string) => string;
  selectChat: (chatId: string) => void;
  deleteChat: (chatId: string) => void;
  clearChats: () => void;
  updateChatTitle: (chatId: string, title: string) => void;

  addMessage: (chatId: string, role: Message["role"], content: string) => void;
  updateMessage: (chatId: string, messageId: string, content: string) => void;
  deleteMessage: (chatId: string, messageId: string) => void;

  getModels: () => void;
  selectModel: (modelId: string) => void;

  // Getters
  getSelectedChat: () => Chat | undefined;
}
export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      chats: [],
      selectedChatId: null,
      models: [],
      selectedModelId: "",

      createChat: (modelId) => {
        const id = uuidv4();
        const newChat: Chat = {
          id,
          title: "New Chat",
          messages: [],
          createdAt: new Date(),
          updatedAt: new Date(),
          modelId: modelId || get().selectedModelId,
        };

        set((state) => ({
          chats: [newChat, ...state.chats],
          selectedChatId: id,
        }));

        return id;
      },

      selectChat: (chatId) => {
        set({ selectedChatId: chatId });
      },

      deleteChat: (chatId) => {
        set((state) => {
          const newChats = state.chats.filter((chat) => chat.id !== chatId);
          let newSelectedChatId = state.selectedChatId;

          if (state.selectedChatId === chatId) {
            newSelectedChatId = newChats.length > 0 ? newChats[0].id : null;
          }

          return {
            chats: newChats,
            selectedChatId: newSelectedChatId,
          };
        });
      },

      clearChats: () => {
        set({ chats: [], selectedChatId: null });
      },

      updateChatTitle: (chatId, title) => {
        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === chatId
              ? { ...chat, title, updatedAt: new Date() }
              : chat,
          ),
        }));
      },

      addMessage: (chatId, role, content) => {
        const message: Message = {
          id: uuidv4(),
          role,
          content,
          createdAt: new Date(),
        };

        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === chatId
              ? {
                  ...chat,
                  messages: [...chat.messages, message],
                  updatedAt: new Date(),
                }
              : chat,
          ),
        }));
      },

      updateMessage: (chatId, messageId, content) => {
        set((state) => ({
          chats: state.chats.map((chat) => {
            if (chat.id !== chatId) return chat;
            const messageExists = chat.messages.some(
              (msg) => msg.id === messageId,
            );
            const messages = messageExists
              ? chat.messages.map((msg) =>
                  msg.id === messageId ? { ...msg, content } : msg,
                )
              : [
                  ...chat.messages,
                  {
                    id: messageId,
                    role: "assistant" as const,
                    content,
                    createdAt: new Date(),
                  },
                ];

            return {
              ...chat,
              messages,
              updatedAt: new Date(),
            };
          }),
        }));
      },

      deleteMessage: (chatId, messageId) => {
        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === chatId
              ? {
                  ...chat,
                  messages: chat.messages.filter((msg) => msg.id !== messageId),
                  updatedAt: new Date(),
                }
              : chat,
          ),
        }));
      },

      getModels: async () => {
        const models = await client.models.list();
        set({ models: models.data });
      },
      selectModel: (modelId) => {
        set({ selectedModelId: modelId });
      },

      getSelectedChat: () => {
        const { chats, selectedChatId } = get();
        return chats.find((chat) => chat.id === selectedChatId);
      },
    }),
    {
      name: "chatbot-store",
    },
  ),
);
