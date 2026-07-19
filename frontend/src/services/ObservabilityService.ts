import { httpService } from "./HttpService";

export type AgentRunSummary = {
  id: string;
  conversation_id: string | null;
  username: string;
  owner_sub: string;
  user_message: string;
  assistant_reply: string;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency_ms: number | null;
  tool_count: number;
  llm_call_count: number;
  error: string;
  trace_id: string;
  created_at: string;
};

export type AgentRunDetail = AgentRunSummary & {
  llm_calls: Array<{
    id: string;
    provider: string;
    model: string;
    purpose: string;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    latency_ms: number | null;
    request_id: string;
    error: string;
    created_at: string;
  }>;
  tool_calls: Array<{
    id: string;
    tool: string;
    args: Record<string, unknown>;
    result_preview: string;
    sequence: number;
    created_at: string;
  }>;
};

export async function listAgentRuns(limit = 50) {
  return httpService.get<{ count: number; runs: AgentRunSummary[] }>(
    `/admin/runs/?limit=${limit}`,
  );
}

export async function getAgentRun(id: string) {
  return httpService.get<AgentRunDetail>(`/admin/runs/${id}/`);
}
