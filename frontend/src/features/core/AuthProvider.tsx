import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import {
  authService,
  type AuthUser,
} from "../feature_auth/services/AuthService";

type AuthContextValue = {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isReady: boolean;
  login: (username: string, password: string) => Promise<AuthUser>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const sync = () => {
      setUser(authService.getUser());
      setIsAuthenticated(authService.isAuthenticated());
    };

    const boot = async () => {
      await authService.bootstrap();
      if (cancelled) {
        return;
      }
      sync();
      setIsReady(true);
    };

    void boot();
    const unsubscribe = authService.subscribe(sync);
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isAuthenticated,
      isReady,
      login: async (username, password) => {
        const next = await authService.login(username, password);
        setUser(next);
        setIsAuthenticated(true);
        return next;
      },
      logout: async () => {
        await authService.logout();
        setUser(null);
        setIsAuthenticated(false);
      },
    }),
    [user, isAuthenticated, isReady],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
