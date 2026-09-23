import { useState } from "react";
import { api } from "../api.js";
import { safetyEventColumns } from "../components/columns.jsx";
import { Async, PageHeader, Panel, Select, ServiceNotice, SeverityBadge, Stat, Table } from "../components/ui.jsx";
import { useService } from "../SystemStatus.jsx";
import { useApi } from "../useApi.js";
import { SAFETY_EVENT_TYPES, SEVERITIES } from "../vocab.js";

const PAGE_SIZE = 100;

export default function SafetyAlerts() {
  const [filters, setFilters] = useState({ severity: null, event_type: null, operator_id: null, machine_id: null });
  const [page, setPage] = useState(0);
  const key = JSON.stringify(filters);

  const operators = useApi(() => api.operators(), []);
  const machines = useApi(() => api.machines(), []);
  const summary = useApi(
    () => api.safetySummary({ operator_id: filters.operator_id, machine_id: filters.machine_id }),
    [filters.operator_id, filters.machine_id],
  );
  const events = useApi(
    () => api.safetyEvents({ ...filters, limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    [key, page],
  );
  const live = useService("safety_intelligence");

  const setFilter = (name) => (value) => {
    setFilters((current) => ({ ...current, [name]: value }));
    setPage(0);
  };

  return (
    <>
      <PageHeader title="Safety / Alerts" subtitle="Safety events recorded from observable conditions.">
        <Select placeholder="All severities" value={filters.severity} onChange={setFilter("severity")} options={SEVERITIES} />
        <Select placeholder="All event types" value={filters.event_type} onChange={setFilter("event_type")} options={SAFETY_EVENT_TYPES} />
        <Select
          placeholder="All operators"
          value={filters.operator_id}
          onChange={setFilter("operator_id")}
          options={(operators.data || []).map((o) => [o.operator_id, `${o.operator_id} - ${o.name}`])}
        />
        <Select
          placeholder="All machines"
          value={filters.machine_id}
          onChange={setFilter("machine_id")}
          options={(machines.data || []).map((m) => [m.machine_id, `${m.machine_id} - ${m.model}`])}
        />
      </PageHeader>

      <div className="mb-4 rounded-md border border-slate-200 bg-white px-4 py-2.5 text-sm">
        <span className="font-medium">Live monitoring: </span>
        <ServiceNotice service={live} compact />
        <span className="block text-xs text-slate-500">
          The events below are recorded in the synthetic task history. Severity is assigned by the backend data, not by this page.
        </span>
      </div>

      <Async state={summary}>
        {(s) => (
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Events" value={s.total} />
            {SEVERITIES.map((severity) => (
              <Stat key={severity} label={<SeverityBadge severity={severity} />} value={s.by_severity[severity] || 0} />
            ))}
          </div>
        )}
      </Async>

      <Panel
        title="Events"
        action={
          <div className="flex items-center gap-2 text-sm">
            <button
              type="button"
              disabled={page === 0}
              onClick={() => setPage(page - 1)}
              className="rounded border border-slate-300 px-2 py-0.5 disabled:opacity-40"
            >
              Previous
            </button>
            <span className="text-slate-500">Page {page + 1}</span>
            <button
              type="button"
              disabled={(events.data?.length || 0) < PAGE_SIZE}
              onClick={() => setPage(page + 1)}
              className="rounded border border-slate-300 px-2 py-0.5 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        }
      >
        <Async state={events}>
          {(rows) => <Table columns={safetyEventColumns} rows={rows} rowKey={(e) => e.event_id} empty="No safety events match these filters." />}
        </Async>
      </Panel>
    </>
  );
}
