import { httpService } from "./HttpService";

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  tool_trace?: Array<{ tool?: string }>;
  created_at: string;
};

export type ConversationDetail = ConversationSummary & {
  messages: ConversationMessage[];
};

export type ChatResponse = {
  reply: string;
  role: string;
  conversation_id: string;
  tool_trace?: Array<{
    tool?: string;
    args?: Record<string, unknown>;
    result?: unknown;
  }>;
  trace_id?: string | null;
  latency_ms?: number | null;
};

export async function listConversations() {
  return httpService.get<{ count: number; conversations: ConversationSummary[] }>(
    "/conversations/",
  );
}

export async function createConversation() {
  return httpService.post<ConversationDetail>("/conversations/", {});
}

export async function getConversation(id: string) {
  return httpService.get<ConversationDetail>(`/conversations/${id}/`);
}

export async function deleteConversation(id: string) {
  return httpService.delete(`/conversations/${id}/`);
}

export async function sendChatMessage(message: string, conversationId?: string | null) {
  return httpService.post<ChatResponse>("/chat/", {
    message,
    conversation_id: conversationId || undefined,
  });
}
