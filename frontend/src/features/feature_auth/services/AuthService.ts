export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  refresh_expires_in: number;
  token_type: string;
};

export type AuthUser = {
  sub: string;
  username: string;
  email: string;
  roles: string[];
};

const KEYCLOAK_URL =
  import.meta.env.VITE_KEYCLOAK_URL ?? "http://localhost:8080";
const REALM = import.meta.env.VITE_KEYCLOAK_REALM ?? "acme";
const CLIENT_ID = import.meta.env.VITE_KEYCLOAK_CLIENT_ID ?? "acme-frontend";

const ACCESS_KEY = "acme.access_token";
const REFRESH_KEY = "acme.refresh_token";

/** Refresh this many ms before access token expiry. */
const REFRESH_SKEW_MS = 60_000;

type JwtPayload = {
  sub?: string;
  preferred_username?: string;
  email?: string;
  realm_access?: { roles?: string[] };
  resource_access?: Record<string, { roles?: string[] }>;
  exp?: number;
};

function decodeJwt(token: string): JwtPayload {
  const [, payload] = token.split(".");
  if (!payload) {
    throw new Error("Invalid token");
  }
  const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
  const json = atob(
    normalized.padEnd(normalized.length + ((4 - (normalized.length % 4)) % 4), "="),
  );
  return JSON.parse(json) as JwtPayload;
}

class AuthService {
  private listeners = new Set<() => void>();
  private refreshTimer: ReturnType<typeof setTimeout> | null = null;
  private refreshInFlight: Promise<string | null> | null = null;

  get tokenUrl() {
    return `${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/token`;
  }

  get logoutUrl() {
    return `${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/logout`;
  }

  subscribe(listener: () => void) {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  private notify() {
    this.listeners.forEach((listener) => listener());
  }

  getAccessToken(): string | null {
    return localStorage.getItem(ACCESS_KEY);
  }

  getRefreshToken(): string | null {
    return localStorage.getItem(REFRESH_KEY);
  }

  /** Access token present and not expired (with small skew). */
  isAuthenticated(): boolean {
    const token = this.getAccessToken();
    if (!token) {
      return false;
    }
    try {
      const payload = decodeJwt(token);
      if (!payload.exp) {
        return true;
      }
      return payload.exp * 1000 > Date.now() + 5_000;
    } catch {
      return false;
    }
  }

  /** True if we still have a refresh token to try (even if access expired). */
  hasRefreshToken(): boolean {
    return Boolean(this.getRefreshToken());
  }

  getUser(): AuthUser | null {
    const token = this.getAccessToken();
    if (!token) {
      return null;
    }
    try {
      const payload = decodeJwt(token);
      const realmRoles = payload.realm_access?.roles ?? [];
      const clientRoles = payload.resource_access?.[CLIENT_ID]?.roles ?? [];
      return {
        sub: payload.sub ?? "",
        username: payload.preferred_username ?? payload.email ?? "user",
        email: payload.email ?? "",
        roles: [...new Set([...realmRoles, ...clientRoles])],
      };
    } catch {
      return null;
    }
  }

  async login(username: string, password: string): Promise<AuthUser> {
    const body = new URLSearchParams({
      grant_type: "password",
      client_id: CLIENT_ID,
      username,
      password,
      scope: "openid profile email",
    });

    const response = await fetch(this.tokenUrl, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body,
    });

    if (!response.ok) {
      const detail = await response.text();
      throw new Error(
        response.status === 401
          ? "Invalid username or password"
          : `Login failed (${response.status}): ${detail}`,
      );
    }

    const tokens = (await response.json()) as TokenResponse;
    this.persistTokens(tokens);
    const user = this.getUser();
    if (!user) {
      throw new Error("Unable to read user from token");
    }
    this.notify();
    return user;
  }

  /**
   * Ensure a valid access token. Refreshes when expired / near expiry.
   * Clears session and notifies listeners when refresh is impossible.
   */
  async ensureAccessToken(): Promise<string | null> {
    const token = this.getAccessToken();
    if (token && this.isAuthenticated()) {
      return token;
    }
    return this.refresh();
  }

  async refresh(): Promise<string | null> {
    if (this.refreshInFlight) {
      return this.refreshInFlight;
    }

    this.refreshInFlight = this.doRefresh().finally(() => {
      this.refreshInFlight = null;
    });
    return this.refreshInFlight;
  }

  private async doRefresh(): Promise<string | null> {
    const refreshToken = this.getRefreshToken();
    if (!refreshToken) {
      this.clearSession({ notify: true });
      return null;
    }

    const body = new URLSearchParams({
      grant_type: "refresh_token",
      client_id: CLIENT_ID,
      refresh_token: refreshToken,
    });

    try {
      const response = await fetch(this.tokenUrl, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });

      if (!response.ok) {
        this.clearSession({ notify: true });
        return null;
      }

      const tokens = (await response.json()) as TokenResponse;
      this.persistTokens(tokens);
      this.notify();
      return tokens.access_token;
    } catch {
      this.clearSession({ notify: true });
      return null;
    }
  }

  async logout() {
    const refreshToken = this.getRefreshToken();
    this.clearSession({ notify: false });
    if (refreshToken) {
      const body = new URLSearchParams({
        client_id: CLIENT_ID,
        refresh_token: refreshToken,
      });
      void fetch(this.logoutUrl, {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      });
    }
    this.notify();
  }

  /** Call on app boot to restore session / schedule refresh. */
  async bootstrap(): Promise<AuthUser | null> {
    if (this.isAuthenticated()) {
      this.scheduleRefresh();
      return this.getUser();
    }
    if (this.hasRefreshToken()) {
      const token = await this.refresh();
      return token ? this.getUser() : null;
    }
    return null;
  }

  private persistTokens(tokens: TokenResponse) {
    localStorage.setItem(ACCESS_KEY, tokens.access_token);
    localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    this.scheduleRefresh();
  }

  private clearSession({ notify }: { notify: boolean }) {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }
    if (notify) {
      this.notify();
    }
  }

  private scheduleRefresh() {
    if (this.refreshTimer) {
      clearTimeout(this.refreshTimer);
      this.refreshTimer = null;
    }

    const token = this.getAccessToken();
    if (!token) {
      return;
    }

    try {
      const payload = decodeJwt(token);
      if (!payload.exp) {
        return;
      }
      const expiresAt = payload.exp * 1000;
      const delay = Math.max(5_000, expiresAt - Date.now() - REFRESH_SKEW_MS);
      this.refreshTimer = setTimeout(() => {
        void this.refresh();
      }, delay);
    } catch {
      // ignore malformed token; next request will clear
    }
  }
}

export const authService = new AuthService();
export default AuthService;
