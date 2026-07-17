import { Route, Routes } from "react-router-dom";

import { CmsDashboardPage } from "../pages/CmsDashboardPage";

export function CmsRoutes() {
  return (
    <Routes>
      <Route index element={<CmsDashboardPage />} />
    </Routes>
  );
}
