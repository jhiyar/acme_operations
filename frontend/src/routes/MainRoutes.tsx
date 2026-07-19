import { Navigate, Route, Routes } from "react-router-dom";

import { CmsRoutes } from "../cms/routes/CmsRoutes";
import { AppShell } from "../features/core/AppShell";
import { RequireAdmin } from "../features/core/RequireAdmin";
import { RequireAuth } from "../features/core/RequireAuth";
import { LoginPage } from "../features/feature_auth/LoginPage";
import { ChatPage } from "../features/feature_chat/ChatPage";
import { IssuesPage } from "../features/feature_issues/IssuesPage";
import { ObservabilityPage } from "../features/feature_observability/ObservabilityPage";

export function MainRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth />}>
        <Route element={<AppShell />}>
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/issues" element={<IssuesPage />} />
          <Route element={<RequireAdmin />}>
            <Route path="/observability" element={<ObservabilityPage />} />
          </Route>
          <Route path="/cms/*" element={<CmsRoutes />} />
        </Route>
      </Route>
      <Route path="/" element={<Navigate to="/issues" replace />} />
      <Route path="*" element={<Navigate to="/issues" replace />} />
    </Routes>
  );
}
