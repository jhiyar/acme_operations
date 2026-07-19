import axios from "axios";
import { useMutation } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { httpService } from "../../services/HttpService";
import { ChatComposer } from "./components/ChatComposer";
import {
  ChatMessageList,
  type ChatMessage,
} from "./components/ChatMessageList";

type ChatResponse = {
  reply: string;
  role: string;
  tool_trace?: Array<{
    tool?: string;
    args?: Record<string, unknown>;
    result?: unknown;
  }>;
};

function createId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function errorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") {
      return detail;
    }
    if (err.code === "ECONNABORTED") {
      return "The assistant timed out — try a shorter question.";
    }
    if (err.message) {
      return err.message;
    }
  }
  if (err instanceof Error) {
    return err.message;
  }
  return "Unable to reach the assistant";
}

export function ChatPage() {
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);

  const mutation = useMutation({
    mutationFn: (message: string) =>
      httpService.post<ChatResponse>("/chat/", { message }),
    onSuccess: (data) => {
      const tools = data.tool_trace?.map((step) => step.tool).filter(Boolean);
      setMessages((prev) => [
        ...prev,
        {
          id: createId(),
          role: "assistant",
          content: data.reply,
          toolsUsed: tools?.length ? (tools as string[]) : undefined,
        },
      ]);
    },
    onError: (err) => {
      setMessages((prev) => [
        ...prev,
        {
          id: createId(),
          role: "assistant",
          content: `Something went wrong: ${errorMessage(err)}`,
        },
      ]);
    },
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, mutation.isPending]);

  const send = () => {
    const message = draft.trim();
    if (!message || mutation.isPending) {
      return;
    }
    setMessages((prev) => [
      ...prev,
      { id: createId(), role: "user", content: message },
    ]);
    setDraft("");
    mutation.mutate(message);
  };

  return (
    <div className="chat-page">
      <section className="chat-stage">
        <h1 className="page-title">Assistant</h1>
        <ChatMessageList messages={messages} />
        {mutation.isPending ? (
          <p className="muted typing">Assistant is thinking…</p>
        ) : null}
        <div ref={bottomRef} />
      </section>

      <ChatComposer
        value={draft}
        onChange={setDraft}
        onSubmit={send}
        disabled={mutation.isPending}
      />
    </div>
  );
}
