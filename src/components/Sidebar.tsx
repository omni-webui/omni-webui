"use client";

import ModelSelector from "@/components/ModelSelector";
import ThemeToggle from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { filterChats, formatDate } from "@/lib/chatHelpers";
import { useChatStore } from "@/lib/store";
import { Info, PlusCircle, Search, Settings, Trash } from "lucide-react";
import { useState } from "react";

export default function Sidebar() {
  const [searchQuery, setSearchQuery] = useState("");

  const chats = useChatStore((state) => state.chats);
  const selectedChatId = useChatStore((state) => state.selectedChatId);
  const createChat = useChatStore((state) => state.createChat);
  const selectChat = useChatStore((state) => state.selectChat);
  const deleteChat = useChatStore((state) => state.deleteChat);
  const clearChats = useChatStore((state) => state.clearChats);

  const filteredChats = filterChats(chats, searchQuery);

  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-4">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-bold">Omni WebUI</h1>
          <div className="flex items-center space-x-1">
            <ThemeToggle />

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon">
                  <Settings className="h-5 w-5" />
                  <span className="sr-only">Settings</span>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem onClick={() => clearChats()}>
                  <Trash className="mr-2 h-4 w-4" />
                  <span>Clear all chats</span>
                </DropdownMenuItem>
                <DropdownMenuItem>
                  <Info className="mr-2 h-4 w-4" />
                  <span>About</span>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>

        <Button className="w-full mb-4" onClick={() => createChat()}>
          <PlusCircle className="mr-2 h-4 w-4" />
          New Chat
        </Button>

        <ModelSelector />

        <div className="relative my-4">
          <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search chats..."
            className="pl-8"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>

        <Separator className="my-2" />
      </div>

      <div className="flex-1 overflow-auto px-4 pb-4">
        {filteredChats.length === 0 ? (
          <div className="text-center text-muted-foreground py-4">
            {searchQuery ? "No chats found" : "No chats yet"}
          </div>
        ) : (
          <ul className="space-y-2">
            {filteredChats.map((chat) => (
              <li key={chat.id}>
                <div
                  className={`w-full flex items-center justify-between text-left text-sm h-auto py-3 group cursor-pointer rounded-md ${
                    selectedChatId === chat.id
                      ? "bg-secondary"
                      : "hover:bg-accent"
                  }`}
                  onClick={() => selectChat(chat.id)}
                >
                  <div className="truncate flex-1">
                    <div className="truncate font-medium pl-2">
                      {chat.title}
                    </div>
                    <div className="text-xs text-muted-foreground truncate pl-2">
                      {formatDate(chat.updatedAt)}
                    </div>
                  </div>
                  {selectedChatId === chat.id && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6 ml-2 opacity-0 group-hover:opacity-100"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteChat(chat.id);
                      }}
                    >
                      <Trash className="h-4 w-4" />
                      <span className="sr-only">Delete</span>
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
