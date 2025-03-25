"use client";

import Sidebar from "@/components/Sidebar";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { useChatStore } from "@/lib/store";
import { Menu, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const ChatArea = dynamic(() => import("@/components/ChatArea"), { ssr: false });

export default function ChatLayout() {
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const selectedChatId = useChatStore((state) => state.selectedChatId);
  const createChat = useChatStore((state) => state.createChat);

  // Create a new chat if none is selected
  useEffect(() => {
    if (!selectedChatId) {
      createChat();
    }
  }, [selectedChatId, createChat]);

  // Close mobile sidebar when chat is selected
  useEffect(() => {
    if (selectedChatId && isMobileOpen) {
      setIsMobileOpen(false);
    }
  }, [selectedChatId, isMobileOpen]);

  return (
    <div className="flex h-screen bg-background overflow-hidden">
      {/* Desktop Sidebar */}
      <div className="hidden md:flex md:w-72 md:flex-col border-r">
        <Sidebar />
      </div>

      {/* Mobile Sidebar (Sheet) */}
      <Sheet open={isMobileOpen} onOpenChange={setIsMobileOpen}>
        <SheetTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden absolute top-4 left-4 z-10"
          >
            <Menu className="h-6 w-6" />
            <span className="sr-only">Toggle menu</span>
          </Button>
        </SheetTrigger>
        <SheetContent side="left" className="p-0 w-72">
          <Button
            variant="ghost"
            size="icon"
            className="absolute right-4 top-4"
            onClick={() => setIsMobileOpen(false)}
          >
            <X className="h-4 w-4" />
            <span className="sr-only">Close menu</span>
          </Button>
          <Sidebar />
        </SheetContent>
      </Sheet>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <ChatArea />
      </div>
    </div>
  );
}
