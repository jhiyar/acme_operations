import { Navigate, Outlet } from "react-router-dom";

import { useAuth } from "./AuthProvider";
import { ADMIN_ROLES, hasAnyRole } from "../../widgets/PermissionCheck";

export function RequireAdmin() {
  const { user, isReady } = useAuth();

  if (!isReady) {
    return (
      <div className="auth-loading">
        <p className="muted">Checking session…</p>
      </div>
    );
  }

  if (!hasAnyRole(user?.roles, ADMIN_ROLES)) {
    return <Navigate to="/issues" replace />;
  }

  return <Outlet />;
}
