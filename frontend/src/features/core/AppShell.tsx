import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { Button } from "../../widgets/Button";
import { useAuth } from "./AuthProvider";

const SIDEBAR_KEY = "acme.sidebar.collapsed";

const BASE_NAV = [
  { to: "/chat", label: "Assistant", short: "A" },
  { to: "/issues", label: "Issues", short: "I" },
  { to: "/customers", label: "Customers", short: "C" },
] as const;

export function AppShell() {
  const { user, logout } = useAuth();
  const isAdmin = user?.roles.includes("admin") ?? false;
  const navItems = useMemo(
    () =>
      isAdmin
        ? [...BASE_NAV, { to: "/observability", label: "Observability", short: "O" }]
        : [...BASE_NAV],
    [isAdmin],
  );
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(SIDEBAR_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(SIDEBAR_KEY, collapsed ? "1" : "0");
    } catch {
      // ignore storage failures
    }
  }, [collapsed]);

  return (
    <div className={`app-frame ${collapsed ? "sidebar-collapsed" : ""}`}>
      <aside className="app-sidebar" aria-label="Main navigation">
        <div className="sidebar-top">
          <div className="sidebar-brand">
            {!collapsed ? (
              <p className="brand-mark compact">Acme Operations</p>
            ) : (
              <p className="brand-mark compact brand-mark-mini" title="Acme Operations">
                AO
              </p>
            )}
          </div>
          <button
            type="button"
            className="sidebar-toggle"
            onClick={() => setCollapsed((value) => !value)}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
          >
            {collapsed ? "›" : "‹"}
          </button>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `sidebar-link ${isActive ? "active" : ""}`
              }
              title={item.label}
            >
              <span className="sidebar-link-short" aria-hidden="true">
                {item.short}
              </span>
              {!collapsed ? <span className="sidebar-link-label">{item.label}</span> : null}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user" title={user?.username}>
            <div className="sidebar-avatar" aria-hidden="true">
              {(user?.username?.[0] ?? "U").toUpperCase()}
            </div>
            {!collapsed ? (
              <div className="sidebar-user-meta">
                <p className="user-name">{user?.username}</p>
                <p className="muted role-line">
                  {user?.roles.join(" · ") || "no roles"}
                </p>
              </div>
            ) : null}
          </div>
          <Button
            variant="ghost"
            className="sidebar-signout"
            onClick={() => void logout()}
            title="Sign out"
          >
            {collapsed ? "⎋" : "Sign out"}
          </Button>
        </div>
      </aside>

      <div className="app-content">
        <Outlet />
      </div>
    </div>
  );
}
