import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { httpService } from "../../../services/HttpService";

export type ManagedUser = {
  id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  enabled: boolean;
  roles: string[];
};

export type UsersResponse = {
  count: number;
  users: ManagedUser[];
};

export type UserWritePayload = {
  username: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  password: string;
  role: string;
  enabled?: boolean;
};

export type UserPatchPayload = {
  userId: string;
  email?: string;
  first_name?: string;
  last_name?: string;
  password?: string;
  role?: string;
  enabled?: boolean;
};

export function useUsers(enabled = true) {
  return useQuery({
    queryKey: ["users"],
    queryFn: () => httpService.get<UsersResponse>("/users/"),
    enabled,
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: UserWritePayload) =>
      httpService.post<{ created: boolean; user: ManagedUser }>("/users/", payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, ...payload }: UserPatchPayload) =>
      httpService.patch<{ updated: boolean; user: ManagedUser }>(
        `/users/${userId}/`,
        payload,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (userId: string) => httpService.delete(`/users/${userId}/`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
    },
  });
}
