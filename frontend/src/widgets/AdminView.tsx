import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../features/core/AuthProvider";

type AdminViewProps = {
  children: ReactNode;
  /** When true, non-admins are redirected instead of seeing a message */
  redirect?: boolean;
};

/**
 * Gate UI for admin-only sections. Prefer wrapping page content with this
 * widget so admin checks stay consistent across features.
 */
export function AdminView({ children, redirect = false }: AdminViewProps) {
  const { user, isReady } = useAuth();

  if (!isReady) {
    return (
      <div className="auth-loading">
        <p className="muted">Checking session…</p>
      </div>
    );
  }

  const isAdmin = user?.roles.includes("admin") ?? false;
  if (!isAdmin) {
    if (redirect) {
      return <Navigate to="/issues" replace />;
    }
    return (
      <div className="issues-page">
        <section className="issues-content">
          <h1>Admin only</h1>
          <p className="muted">You need the admin role to open this page.</p>
        </section>
      </div>
    );
  }

  return <>{children}</>;
}
