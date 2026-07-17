import { useQuery } from "@tanstack/react-query";

import { httpService } from "../../../services/HttpService";

export type HealthResponse = {
  status: string;
  service: string;
};

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => httpService.get<HealthResponse>("/health/"),
  });
}
