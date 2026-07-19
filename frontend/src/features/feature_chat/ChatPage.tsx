import axios from "axios";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import {
  createConversation,
  deleteConversation,
  getConversation,
  listConversations,
  sendChatMessage,
} from "../../services/ChatService";
import { ChatComposer } from "./components/ChatComposer";
import {
  ChatMessageList,
  type ChatMessage,
} from "./components/ChatMessageList";
import { ConversationPanel } from "./components/ConversationPanel";

const ACTIVE_KEY = "acme.chat.activeConversationId";

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

function toUiMessages(
  messages: Array<{
    id: string;
    role: "user" | "assistant";
    content: string;
    tool_trace?: Array<{ tool?: string }>;
  }>,
): ChatMessage[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    toolsUsed: message.tool_trace
      ?.map((step) => step.tool)
      .filter((tool): tool is string => Boolean(tool)),
  }));
}

function HistoryIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path
        d="M7 7h10M7 12h10M7 17h6"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <rect
        x="3.75"
        y="3.75"
        width="16.5"
        height="16.5"
        rx="3"
        stroke="currentColor"
        strokeWidth="1.8"
      />
    </svg>
  );
}

export function ChatPage() {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(() => {
    return localStorage.getItem(ACTIVE_KEY);
  });
  const [panelOpen, setPanelOpen] = useState(false);
  const [bootstrapping, setBootstrapping] = useState(() => Boolean(localStorage.getItem(ACTIVE_KEY)));
  const bottomRef = useRef<HTMLDivElement>(null);

  const conversationsQuery = useQuery({
    queryKey: ["conversations"],
    queryFn: listConversations,
  });

  useEffect(() => {
    if (!conversationId) {
      setBootstrapping(false);
      return;
    }

    let cancelled = false;
    setBootstrapping(true);
    getConversation(conversationId)
      .then((detail) => {
        if (cancelled) {
          return;
        }
        setMessages(toUiMessages(detail.messages));
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        localStorage.removeItem(ACTIVE_KEY);
        setConversationId(null);
        setMessages([]);
      })
      .finally(() => {
        if (!cancelled) {
          setBootstrapping(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (conversationId) {
      localStorage.setItem(ACTIVE_KEY, conversationId);
    } else {
      localStorage.removeItem(ACTIVE_KEY);
    }
  }, [conversationId]);

  const mutation = useMutation({
    mutationFn: (message: string) => sendChatMessage(message, conversationId),
    onSuccess: (data) => {
      setConversationId(data.conversation_id);
      const tools = data.tool_trace
        ?.map((step: { tool?: string }) => step.tool)
        .filter(Boolean);
      setMessages((prev) => [
        ...prev,
        {
          id: createId(),
          role: "assistant",
          content: data.reply,
          toolsUsed: tools?.length ? (tools as string[]) : undefined,
        },
      ]);
      void queryClient.invalidateQueries({ queryKey: ["conversations"] });
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

  const startNewConversation = async () => {
    const created = await createConversation();
    setConversationId(created.id);
    setMessages([]);
    setPanelOpen(false);
    void queryClient.invalidateQueries({ queryKey: ["conversations"] });
  };

  const selectConversation = async (id: string) => {
    const detail = await getConversation(id);
    setConversationId(detail.id);
    setMessages(toUiMessages(detail.messages));
    setPanelOpen(false);
  };

  const removeConversation = async (id: string) => {
    await deleteConversation(id);
    if (conversationId === id) {
      setConversationId(null);
      setMessages([]);
    }
    void queryClient.invalidateQueries({ queryKey: ["conversations"] });
  };

  return (
    <div className="chat-page">
      <section className="chat-stage">
        <header className="chat-header">
          <h1 className="page-title">Assistant</h1>
          <div className="chat-header-actions">
            <button
              type="button"
              className="btn btn-ghost btn-icon"
              aria-label="Conversations"
              aria-expanded={panelOpen}
              onClick={() => setPanelOpen((open) => !open)}
            >
              <HistoryIcon />
            </button>
            <ConversationPanel
              open={panelOpen}
              onClose={() => setPanelOpen(false)}
              conversations={conversationsQuery.data?.conversations ?? []}
              activeId={conversationId}
              loading={conversationsQuery.isLoading}
              onSelect={(id) => void selectConversation(id)}
              onNew={() => void startNewConversation()}
              onDelete={(id) => void removeConversation(id)}
            />
          </div>
        </header>

        {bootstrapping ? (
          <p className="muted">Loading conversation…</p>
        ) : (
          <ChatMessageList messages={messages} />
        )}
        {mutation.isPending ? (
          <p className="muted typing">Assistant is thinking…</p>
        ) : null}
        <div ref={bottomRef} />
      </section>

      <ChatComposer
        value={draft}
        onChange={setDraft}
        onSubmit={send}
        disabled={mutation.isPending || bootstrapping}
      />
    </div>
  );
}
