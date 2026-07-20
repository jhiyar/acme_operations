import { useQuery } from "@tanstack/react-query";

import { httpService } from "../../../services/HttpService";

export type IssueUpdate = {
  id: number;
  author: string;
  body: string;
  created_at: string;
};

export type Issue = {
  id: number;
  title: string;
  description: string;
  status: string;
  priority: string;
  assigned_to: string;
  customer: {
    id: number;
    name: string;
  };
  created_at: string;
  updated_at: string;
  updates?: IssueUpdate[];
};

export type IssuesResponse = {
  scope: "all" | "assigned";
  count: number;
  issues: Issue[];
};

export function useIssues(params?: { status?: string; customer?: string }) {
  return useQuery({
    queryKey: ["issues", params?.status ?? "", params?.customer ?? ""],
    queryFn: () =>
      httpService.get<IssuesResponse>("/issues/", {
        params: {
          status: params?.status || undefined,
          customer: params?.customer || undefined,
        },
      }),
  });
}
