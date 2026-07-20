import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { httpService } from "../../../services/HttpService";

export type Customer = {
  id: number;
  name: string;
  industry: string;
  tier: string;
  account_owner: string;
  contact_email: string;
  notes: string;
};

export type CustomersResponse = {
  count: number;
  customers: Customer[];
};

export type CustomerWritePayload = {
  name: string;
  industry?: string;
  tier?: string;
  account_owner?: string;
  contact_email?: string;
  notes?: string;
};

export function useCustomers(enabled = true) {
  return useQuery({
    queryKey: ["customers"],
    queryFn: () => httpService.get<CustomersResponse>("/customers/"),
    enabled,
  });
}

export function useCreateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: CustomerWritePayload) =>
      httpService.post<{ created: boolean; customer: Customer }>(
        "/customers/",
        payload,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useUpdateCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      customerId,
      ...payload
    }: CustomerWritePayload & { customerId: number }) =>
      httpService.patch<{ updated: boolean; customer: Customer }>(
        `/customers/${customerId}/`,
        payload,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}

export function useDeleteCustomer() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (customerId: number) =>
      httpService.delete(`/customers/${customerId}/`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["customers"] });
    },
  });
}
