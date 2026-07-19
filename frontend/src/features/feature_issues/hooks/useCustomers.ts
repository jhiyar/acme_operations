import { useQuery } from "@tanstack/react-query";

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

type CustomersResponse = {
  count: number;
  customers: Customer[];
};

export function useCustomers(enabled = true) {
  return useQuery({
    queryKey: ["customers"],
    queryFn: () => httpService.get<CustomersResponse>("/customers/"),
    enabled,
  });
}
