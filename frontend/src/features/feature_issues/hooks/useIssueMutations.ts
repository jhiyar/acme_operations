import { useMutation, useQueryClient } from "@tanstack/react-query";

import { httpService } from "../../../services/HttpService";
import type { Issue } from "./useIssues";

export type IssueWritePayload = {
  customer_id: number;
  title: string;
  description?: string;
  status?: string;
  priority?: string;
  assigned_to?: string;
};

export type IssuePatchPayload = {
  issueId: number;
  status?: string;
  priority?: string;
  assigned_to?: string;
  title?: string;
  description?: string;
  customer_id?: number;
};

export function useUpdateIssue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ issueId, ...payload }: IssuePatchPayload) =>
      httpService.patch<{ updated: boolean; issue: Issue }>(
        `/issues/${issueId}/`,
        payload,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });
}

export function useCreateIssue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: IssueWritePayload) =>
      httpService.post<{ created: boolean; issue: Issue }>("/issues/", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });
}

export function useDeleteIssue() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (issueId: number) => httpService.delete(`/issues/${issueId}/`),
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

export function useDeleteIssueUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      issueId,
      updateId,
    }: {
      issueId: number;
      updateId: number;
    }) => httpService.delete(`/issues/${issueId}/updates/${updateId}/`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["issues"] });
    },
  });
}
