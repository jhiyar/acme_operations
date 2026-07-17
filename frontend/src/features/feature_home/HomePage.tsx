import { PageHeader } from "../../widgets/PageHeader";
import { useHealth } from "./hooks/useHealth";

export function HomePage() {
  const { data, isLoading, isError } = useHealth();

  return (
    <section>
      <PageHeader
        title="Home"
        subtitle="Operations dashboard — clean, minimal, ready to extend."
      />
      <div className="status-block">
        {isLoading && <p className="muted">Checking API…</p>}
        {isError && <p className="error">API unreachable. Start the Django server.</p>}
        {data && (
          <p>
            API <strong>{data.status}</strong> · {data.service}
          </p>
        )}
      </div>
    </section>
  );
}
