import type { ReactNode } from "react";

import { ADMIN_ROLES, PermissionCheck } from "./PermissionCheck";

type AdminViewProps = {
  children: ReactNode;
  /** When true, non-admins are redirected instead of seeing a message */
  redirect?: boolean;
};

/**
 * Admin-only gate — thin wrapper over PermissionCheck for admin pages.
 */
export function AdminView({ children, redirect = false }: AdminViewProps) {
  return (
    <PermissionCheck
      roles={ADMIN_ROLES}
      redirect={redirect}
      fallback={
        <div className="issues-page">
          <section className="issues-content">
            <h1>Admin only</h1>
            <p className="muted">You need the admin role to open this page.</p>
          </section>
        </div>
      }
    >
      {children}
    </PermissionCheck>
  );
}
