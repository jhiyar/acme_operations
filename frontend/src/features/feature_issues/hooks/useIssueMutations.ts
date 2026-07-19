import { useMutation, useQueryClient } from "@tanstack/react-query";

import { httpService } from "../../../services/HttpService";
import type { Issue } from "./useIssues";

export function useUpdateIssue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      issueId,
      status,
      priority,
    }: {
      issueId: number;
      status?: string;
      priority?: string;
    }) =>
      httpService.patch<{ updated: boolean; issue: Issue }>(`/issues/${issueId}/`, {
        status,
        priority,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });
}

export function useAddIssueUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ issueId, body }: { issueId: number; body: string }) =>
      httpService.post(`/issues/${issueId}/updates/`, { body }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });
}
