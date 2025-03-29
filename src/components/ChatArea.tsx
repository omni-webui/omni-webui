import SuggestedPrompts from "@/components/SuggestedPrompts";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { client } from "@/lib/api";
import { defaultPrompts } from "@/lib/chatHelpers";
import { useChatStore } from "@/lib/store";
import { Bot, SendHorizontal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import rehypeMathjax from "rehype-mathjax";
import remarkMath from "remark-math";

export default function ChatArea() {
  const [userInput, setUserInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const chatContainerRef = useRef<HTMLDivElement>(null);

  const selectedChat = useChatStore((state) => state.getSelectedChat());
  const addMessage = useChatStore((state) => state.addMessage);
  const updateMessage = useChatStore((state) => state.updateMessage);
  const updateChatTitle = useChatStore((state) => state.updateChatTitle);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop =
        chatContainerRef.current.scrollHeight;
    }
  });

  // Handle submitting a new message
  const handleSubmit = async () => {
    if (!userInput.trim() || !selectedChat) return;

    const chatId = selectedChat.id;
    const modelId = selectedChat.modelId;

    // Add user message to chat
    addMessage(chatId, "user", userInput);
    setUserInput("");

    // Generate chat title if this is the first message
    if (selectedChat.messages.length === 0) {
      const titleText =
        userInput.length > 30 ? `${userInput.substring(0, 30)}...` : userInput;
      updateChatTitle(chatId, titleText);
    }

    // Get AI response
    setIsLoading(true);
    try {
      const stream = await client.chat.completions.create({
        model: modelId,
        messages: [
          ...selectedChat.messages,
          { role: "user", content: userInput },
        ],
        stream: true,
      });

      let fullResponse = "";
      for await (const chunk of stream) {
        const content = chunk.choices[0]?.delta?.content || "";
        fullResponse += content;
        updateMessage(chatId, chunk.id, fullResponse);
      }
    } catch (error) {
      console.error("Error getting response:", error);
      addMessage(
        chatId,
        "assistant",
        "Sorry, I encountered an error processing your request.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  // Handle keyboard shortcuts
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Chat Messages */}
      <div
        ref={chatContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-6"
      >
        {selectedChat?.messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full">
            <Bot className="h-12 w-12 text-primary/60 mb-4" />
            <h2 className="text-2xl font-bold mb-2">Omni WebUI</h2>
            <p className="text-muted-foreground text-center max-w-md mb-6">
              Start a conversation with the AI assistant. Select from the
              suggested prompts below or type your own message.
            </p>
            <SuggestedPrompts
              prompts={defaultPrompts}
              onSelectPrompt={(prompt) => setUserInput(prompt)}
            />
          </div>
        ) : (
          selectedChat?.messages.map((message) => (
            <div
              key={message.id}
              className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`flex gap-3 max-w-3xl ${message.role === "user" ? "flex-row-reverse" : ""}`}
              >
                <Avatar
                  className={
                    message.role === "user" ? "bg-primary" : "bg-secondary"
                  }
                >
                  <AvatarFallback>
                    {message.role === "user" ? "U" : "AI"}
                  </AvatarFallback>
                </Avatar>
                <Card
                  className={`p-4 ${message.role === "user" ? "bg-primary/10" : ""}`}
                >
                  {message.role === "assistant" ? (
                    <div className="prose prose-sm dark:prose-invert max-w-none">
                      <ReactMarkdown
                        remarkPlugins={[remarkMath]}
                        rehypePlugins={[rehypeMathjax]}
                        components={{
                          code({ node, className, children, ...props }) {
                            const match = /language-(\w+)/.exec(
                              className || "",
                            );
                            return match ? (
                              <SyntaxHighlighter
                                style={vscDarkPlus}
                                language={match[1]}
                                PreTag="div"
                                {...props}
                              >
                                {String(children).replace(/\n$/, "")}
                              </SyntaxHighlighter>
                            ) : (
                              <code className={className} {...props}>
                                {children}
                              </code>
                            );
                          },
                        }}
                      >
                        {message.content}
                      </ReactMarkdown>
                      {message.isStreaming && (
                        <span className="ml-1 inline-block h-2 w-2 animate-pulse rounded-full bg-current" />
                      )}
                    </div>
                  ) : (
                    <p className="whitespace-pre-wrap">{message.content}</p>
                  )}
                </Card>
              </div>
            </div>
          ))
        )}
      </div>

      {/* Input Area */}
      <div className="border-t p-4">
        <div className="flex space-x-2">
          <Textarea
            placeholder="Type your message..."
            value={userInput}
            onChange={(e) => setUserInput(e.target.value)}
            onKeyDown={handleKeyDown}
            className="min-h-[60px] resize-none"
            disabled={isLoading}
          />
          <Button
            onClick={handleSubmit}
            disabled={!userInput.trim() || isLoading}
            className="shrink-0 h-[60px]"
          >
            <SendHorizontal className="h-5 w-5" />
            <span className="sr-only">Send</span>
          </Button>
        </div>
        <div className="text-xs text-muted-foreground mt-2 text-center">
          AI assistants can make mistakes. Consider checking important
          information.
        </div>
      </div>
    </div>
  );
}
