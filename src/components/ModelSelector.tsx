"use client";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useChatStore } from "@/lib/store";
import { ChevronDown } from "lucide-react";

export default function ModelSelector() {
  const models = useChatStore((state) => state.models);
  const selectedModelId = useChatStore((state) => state.selectedModelId);
  const selectModel = useChatStore((state) => state.selectModel);

  const selectedModel = models.find((model) => model.id === selectedModelId);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" className="w-full justify-between">
          <div className="flex items-center">
            <div className="mr-2 h-4 w-4 rounded-full bg-primary/10" />
            <span>{selectedModel?.id || "Select Model"}</span>
          </div>
          <ChevronDown className="h-4 w-4 ml-2" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[200px]">
        {models.map((model) => (
          <DropdownMenuItem
            key={model.id}
            onClick={() => selectModel(model.id)}
            className="flex items-center justify-between"
          >
            <div className="flex items-center">
              <div
                className={`mr-2 h-3 w-3 rounded-full ${selectedModelId === model.id ? "bg-primary" : "bg-primary/10"}`}
              />
              <span>{model.id}</span>
            </div>
            <span className="text-xs text-muted-foreground">
              {model.owned_by}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
