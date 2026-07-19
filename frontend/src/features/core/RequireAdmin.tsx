import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthProvider";

export function RequireAdmin() {
  const { user, isReady } = useAuth();

  if (!isReady) {
    return (
      <div className="auth-loading">
        <p className="muted">Checking session…</p>
      </div>
    );
  }

  if (!user?.roles.includes("admin")) {
    return <Navigate to="/issues" replace />;
  }

  return <Outlet />;
}
