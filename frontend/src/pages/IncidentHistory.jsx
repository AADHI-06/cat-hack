import { Link } from "react-router";
import { PageHeader, Panel, ServiceNotice } from "../components/ui.jsx";
import { useService } from "../SystemStatus.jsx";

export default function IncidentHistory() {
  const incidents = useService("incidents");
  return (
    <>
      <PageHeader title="Incident History" subtitle="Logged incidents and their resolution." />
      <Panel title="Incidents">
        <ServiceNotice service={incidents} />
        <p className="mt-3 text-sm text-slate-500">
          Until then, recorded safety events are available on the{" "}
          <Link to="/safety" className="font-medium text-slate-700 underline">Safety / Alerts</Link> page.
        </p>
      </Panel>
    </>
  );
}
