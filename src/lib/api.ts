import type { Message, Model } from "@/types";

// Mock responses for the demo
const mockResponses: Record<string, string[]> = {
  "gpt-4": [
    "That's an interesting question. Let me think about it...",
    "Based on my knowledge, here's what I can tell you about that topic.",
    "Great question! There are several aspects to consider here.",
    "I'd be happy to help you with that. Here's what you need to know:",
    "Let me break this down for you step by step.",
  ],
  "gpt-3.5-turbo": [
    "I can help with that! Here's some information on your question:",
    "Thanks for asking. Here's what I know about that:",
    "That's a good question. Let me explain:",
    "I'll do my best to address your query.",
    "Here's my response to your question:",
  ],
  "claude-3": [
    "I appreciate your question. Let me provide some insights:",
    "I'm happy to explore this topic with you. Here's what I found:",
    "Interesting question! Here's my perspective:",
    "Thank you for asking. Let me share what I know:",
    "I'd be delighted to help with this. Here's my analysis:",
  ],
};

// Mock delay for API calls (ms)
const MOCK_DELAY = 1000;

// API for sending a message to a model
export async function sendMessage(
  modelId: string,
  messages: Message[],
): Promise<{ response: string }> {
  try {
    // In a real app, this would be a fetch to an actual API
    // For static sites, we need to mock the response client-side

    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, MOCK_DELAY));

    // Get last user message
    const lastUserMessage = [...messages]
      .reverse()
      .find((m) => m.role === "user");

    if (!lastUserMessage) {
      throw new Error("No user message found");
    }

    // Get model-specific responses or fallback to default
    const modelResponses =
      mockResponses[modelId] || mockResponses["gpt-3.5-turbo"];

    // Pick a random response from the available options
    const randomIndex = Math.floor(Math.random() * modelResponses.length);
    const baseResponse = modelResponses[randomIndex];

    // Generate a longer contextual response by using parts of the user's message
    const userWords = lastUserMessage.content
      .split(" ")
      .filter((word: string) => word.length > 4)
      .filter(() => Math.random() > 0.7) // Only keep some words randomly
      .slice(0, 3); // Take up to 3 words

    // Create a more natural-sounding response with some of the user's words
    let contextualResponse = baseResponse;

    if (userWords.length > 0) {
      contextualResponse += ` I noticed you mentioned ${userWords.join(", ")}. `;
    }

    // Add some markdown formatting to make the response look more realistic
    contextualResponse += "\n\n## Key Points\n\n";
    contextualResponse +=
      "- This is a simulated response for demonstration purposes\n";
    contextualResponse += `- You're using the ${modelId} model in this chat\n`;
    contextualResponse +=
      "- The actual implementation would connect to a real AI model API\n\n";

    // Add some code example if the user message contains certain keywords
    if (
      lastUserMessage.content.match(/code|program|function|script|develop/i)
    ) {
      contextualResponse += `\`\`\`javascript\n// Example code\nfunction demonstrationCode() {\n  console.log("This is just a mock response");\n  return "Actual AI would generate relevant code here";\n}\n\`\`\`\n`;
    }

    return { response: contextualResponse };
  } catch (error) {
    console.error("Error in sendMessage:", error);
    throw error;
  }
}

// Mock API for fetching available models
export async function getAvailableModels(): Promise<Model[]> {
  // In a real application, this would be an API call
  // For demo purposes, we're returning mock data
  await new Promise((resolve) => setTimeout(resolve, 500));

  return [
    {
      id: "gpt-4",
      name: "GPT-4",
      provider: "OpenAI",
      description: "Most advanced OpenAI model",
    },
    {
      id: "gpt-3.5-turbo",
      name: "GPT-3.5 Turbo",
      provider: "OpenAI",
      description: "Fast and efficient OpenAI model",
    },
    {
      id: "claude-3",
      name: "Claude 3",
      provider: "Anthropic",
      description: "Anthropic's latest model",
    },
  ];
}
