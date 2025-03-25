"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { SuggestedPrompt } from "@/types";
import { ArrowUpRight } from "lucide-react";

interface SuggestedPromptsProps {
  prompts: SuggestedPrompt[];
  onSelectPrompt: (prompt: string) => void;
}

export default function SuggestedPrompts({
  prompts,
  onSelectPrompt,
}: SuggestedPromptsProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 w-full max-w-4xl">
      {prompts.map((prompt) => (
        <Card
          key={prompt.prompt}
          className="p-4 hover:bg-secondary/10 transition-colors cursor-pointer group"
          onClick={() => onSelectPrompt(prompt.prompt)}
        >
          <div className="flex flex-col h-full">
            <div className="font-medium mb-1">{prompt.title}</div>
            <p className="text-sm text-muted-foreground flex-grow mb-2">
              {prompt.description}
            </p>
            <div className="flex justify-between items-center mt-auto">
              <div className="text-xs text-primary">Prompt</div>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <ArrowUpRight className="h-4 w-4" />
                <span className="sr-only">Use prompt</span>
              </Button>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
