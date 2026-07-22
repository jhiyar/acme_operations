import axios, {
  type AxiosInstance,
  type AxiosRequestConfig,
  type InternalAxiosRequestConfig,
} from "axios";

import { authService } from "../features/feature_auth/services/AuthService";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api";

class HttpService {
  private readonly client: AxiosInstance;

  constructor(baseURL: string = API_BASE_URL) {
    this.client = axios.create({
      baseURL,
      headers: { "Content-Type": "application/json" },
      timeout: 120_000,
    });

    this.client.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
      const token = await authService.ensureAccessToken();
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        const status = error?.response?.status;
        const original = error?.config as
          | (InternalAxiosRequestConfig & { _retry?: boolean })
          | undefined;

        if (status === 401 && original && !original._retry) {
          original._retry = true;
          const token = await authService.refresh();
          if (token) {
            original.headers.Authorization = `Bearer ${token}`;
            return this.client.request(original);
          }
          // refresh() already cleared session + notified → RequireAuth → /login
        }

        return Promise.reject(error);
      },
    );
  }

  get<T>(url: string, config?: AxiosRequestConfig) {
    return this.client.get<T>(url, config).then((res) => res.data);
  }

  post<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return this.client.post<T>(url, data, config).then((res) => res.data);
  }

  put<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return this.client.put<T>(url, data, config).then((res) => res.data);
  }

  patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig) {
    return this.client.patch<T>(url, data, config).then((res) => res.data);
  }

  delete<T>(url: string, config?: AxiosRequestConfig) {
    return this.client.delete<T>(url, config).then((res) => res.data);
  }
}

export const httpService = new HttpService();
export default HttpService;
