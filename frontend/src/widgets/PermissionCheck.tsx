import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "../features/core/AuthProvider";

/** Realm roles used by Acme Operations RBAC. */
export const ROLE_SALES = "sales_user";
export const ROLE_SUPPORT = "support_user";
export const ROLE_ADMIN = "admin";

/** Roles that can use the assistant and read customer/issue data. */
export const ASSISTANT_ROLES = [ROLE_SALES, ROLE_SUPPORT, ROLE_ADMIN] as const;

/** support + admin may update issue status / timeline notes. */
export const ISSUE_UPDATE_ROLES = [ROLE_SUPPORT, ROLE_ADMIN] as const;

/** admin-only mutations (issue/customer CRUD, observability, users). */
export const ADMIN_ROLES = [ROLE_ADMIN] as const;

export type AppRole = typeof ROLE_SALES | typeof ROLE_SUPPORT | typeof ROLE_ADMIN;

export function hasAnyRole(
  userRoles: string[] | undefined,
  allowed: readonly string[],
): boolean {
  if (!userRoles?.length || !allowed.length) {
    return false;
  }
  return allowed.some((role) => userRoles.includes(role));
}

type PermissionCheckProps = {
  /** User must have at least one of these realm roles. */
  roles: readonly string[];
  children: ReactNode;
  /** Optional content when the user lacks permission (ignored if redirect). */
  fallback?: ReactNode;
  /** When true, non-matching users are sent to /issues. */
  redirect?: boolean;
};

/**
 * Declarative RBAC gate for menu items, actions, and page sections.
 *
 * @example
 * <PermissionCheck roles={["admin"]}>
 *   <button>New issue</button>
 * </PermissionCheck>
 */
export function PermissionCheck({
  roles,
  children,
  fallback = null,
  redirect = false,
}: PermissionCheckProps) {
  const { user, isReady } = useAuth();

  if (!isReady) {
    return null;
  }

  if (!hasAnyRole(user?.roles, roles)) {
    if (redirect) {
      return <Navigate to="/issues" replace />;
    }
    return <>{fallback}</>;
  }

  return <>{children}</>;
}

/** Hook for imperative role checks (subtitles, disabled state, etc.). */
export function useHasRole(roles: readonly string[]): boolean {
  const { user, isReady } = useAuth();
  if (!isReady) {
    return false;
  }
  return hasAnyRole(user?.roles, roles);
}
