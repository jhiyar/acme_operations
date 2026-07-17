import { PageHeader } from "../../widgets/PageHeader";

export function CmsDashboardPage() {
  return (
    <section>
      <PageHeader
        title="CMS"
        subtitle="Admin area for managing the application."
      />
      <p className="muted">CMS routes live in cms/routes/CmsRoutes.tsx.</p>
    </section>
  );
}
