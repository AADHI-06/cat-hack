import { useState } from "react";
import { Link } from "react-router";
import { api } from "../api.js";
import { safetyEventColumns } from "../components/columns.jsx";
import {
  Async, CountList, Field, Loading, PageHeader, Panel, PriorityBadge, ServiceNotice, SeverityBadge, Stat, Table, Tag,
  ErrorMessage,
} from "../components/ui.jsx";
import { dateTime, label, number, percent } from "../format.js";
import { findService } from "../SystemStatus.jsx";
import { useApi } from "../useApi.js";
import { PRIORITIES, SEVERITIES, TASK_STATUSES } from "../vocab.js";

const operatorColumns = [
  { key: "operator_id", header: "ID" },
  { key: "name", header: "Name" },
  { key: "skill_level", header: "Skill", render: (o) => label(o.skill_level) },
  { key: "experience_years", header: "Exp. (yrs)", className: "text-right" },
  { key: "primary_shift", header: "Shift", render: (o) => label(o.primary_shift) },
];

const machineColumns = [
  { key: "machine_id", header: "ID" },
  { key: "machine_type", header: "Type", render: (m) => label(m.machine_type) },
  { key: "model", header: "Model" },
  { key: "home_zone", header: "Zone", render: (m) => label(m.home_zone) },
  { key: "engine_hours", header: "Engine hrs", className: "text-right", render: (m) => number(m.engine_hours) },
];

export default function SupervisorDashboard() {
  const state = useApi(() => api.supervisorDashboard(), []);
  return (
    <>
      <PageHeader title="Supervisor Dashboard" subtitle="Crew and fleet overview for the shift." />
      <Async state={state}>{(data) => <SupervisorView data={data} />}</Async>
    </>
  );
}

function SupervisorView({ data }) {
  const [tab, setTab] = useState("operators");
  const [selected, setSelected] = useState(null); // { kind: "operator" | "machine", id }
  const { task_summary: tasks, safety_summary: safety, services } = data;
  const service = (key) => findService(services, key);

  const select = (kind, id) => setSelected({ kind, id });

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Operators" value={data.operators.length} />
        <Stat label="Machines" value={data.machines.length} />
        <Stat label="Backlog tasks" value={tasks.total} hint={`${tasks.by_status.PENDING || 0} pending`} />
        <Stat label="Safety events" value={safety.total} hint="recorded in task history" />
        <Stat label="High severity" value={safety.by_severity.HIGH || 0} hint="recorded events" />
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <Panel
          className="lg:col-span-3"
          title={
            <span className="flex gap-1">
              {["operators", "machines"].map((name) => (
                <button
                  key={name}
                  type="button"
                  onClick={() => setTab(name)}
                  className={`rounded px-2 py-0.5 uppercase ${tab === name ? "bg-slate-900 text-white" : "hover:bg-slate-100"}`}
                >
                  {name}
                </button>
              ))}
            </span>
          }
        >
          <div className="max-h-[28rem] overflow-y-auto">
            {tab === "operators" ? (
              <Table
                columns={operatorColumns}
                rows={data.operators}
                rowKey={(o) => o.operator_id}
                selectedKey={selected?.kind === "operator" ? selected.id : null}
                onRowClick={(o) => select("operator", o.operator_id)}
                empty="No operators loaded."
              />
            ) : (
              <Table
                columns={machineColumns}
                rows={data.machines}
                rowKey={(m) => m.machine_id}
                selectedKey={selected?.kind === "machine" ? selected.id : null}
                onRowClick={(m) => select("machine", m.machine_id)}
                empty="No machines loaded."
              />
            )}
          </div>
        </Panel>

        <Panel className="lg:col-span-2" title="Selection">
          {!selected && <p className="text-sm text-slate-500">Select an operator or machine to see its details.</p>}
          {selected?.kind === "operator" && <OperatorDetail operatorId={selected.id} />}
          {selected?.kind === "machine" && (
            <MachineDetail machine={data.machines.find((m) => m.machine_id === selected.id)} />
          )}
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-4">
        <Panel title="Tasks by status">
          <CountList counts={tasks.by_status} order={TASK_STATUSES} />
        </Panel>
        <Panel title="Tasks by priority">
          <CountList counts={tasks.by_priority} order={PRIORITIES} render={(p) => <PriorityBadge priority={p} />} />
        </Panel>
        <Panel title="Safety events by type">
          <CountList counts={safety.by_event_type} />
        </Panel>
        <Panel title="Safety events by severity">
          <CountList counts={safety.by_severity} order={SEVERITIES} render={(s) => <SeverityBadge severity={s} />} />
        </Panel>
      </div>

      <Panel title="Most recent safety events" action={<Link to="/safety" className="text-sm text-slate-600 underline">All events</Link>}>
        <Table columns={safetyEventColumns} rows={data.recent_safety_events} rowKey={(e) => e.event_id} empty="No safety events recorded." />
      </Panel>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Shift plan and utilization">
          <ServiceNotice service={service("optimization")} />
        </Panel>
        <Panel title="Machine anomalies">
          <ServiceNotice service={service("anomaly_detection")} />
        </Panel>
        <Panel title="Open incidents">
          <ServiceNotice service={service("incidents")} />
        </Panel>
      </div>
    </div>
  );
}

function OperatorDetail({ operatorId }) {
  const state = useApi(() => api.operatorDashboard(operatorId), [operatorId]);
  if (state.error) return <ErrorMessage error={state.error} />;
  if (!state.data || state.data.operator.operator_id !== operatorId) return <Loading />;
  const { operator, safety_summary: safety, recent_safety_events: events } = state.data;
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-2 gap-3">
        <Field label="Operator">{operator.operator_id} - {operator.name}</Field>
        <Field label="Skill">{label(operator.skill_level)}, {operator.experience_years} yrs</Field>
      </dl>
      <div className="flex flex-wrap gap-1">
        {operator.certifications.map((cert) => <Tag key={cert}>{label(cert)}</Tag>)}
      </div>
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-500">Recorded safety events ({safety.total})</div>
        <ul className="mt-1 space-y-1">
          {events.slice(0, 5).map((e) => (
            <li key={e.event_id} className="flex items-center gap-2 text-sm">
              <SeverityBadge severity={e.severity} />
              <span>{e.description}</span>
              <span className="ml-auto text-xs text-slate-500">{dateTime(e.timestamp)}</span>
            </li>
          ))}
          {!events.length && <li className="text-sm text-slate-500">None recorded.</li>}
        </ul>
      </div>
      <Link to={`/operator/${operator.operator_id}`} className="inline-block text-sm font-medium text-slate-700 underline">
        Open operator dashboard
      </Link>
    </div>
  );
}

function MachineDetail({ machine }) {
  const telemetry = useApi(() => api.machineTelemetry(machine.machine_id, { limit: 1 }), [machine.machine_id]);
  const latest = telemetry.data?.[0];
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-2 gap-3">
        <Field label="Machine">{machine.machine_id} - {machine.model}</Field>
        <Field label="Type">{label(machine.machine_type)}</Field>
        <Field label="Age">{machine.age_years} years</Field>
        <Field label="Condition rating">{number(machine.condition_rating, 2)}</Field>
      </dl>
      <div className="text-xs uppercase tracking-wide text-slate-500">Latest telemetry</div>
      {telemetry.error && <ErrorMessage error={telemetry.error} />}
      {telemetry.loading && <Loading />}
      {!telemetry.loading && !latest && <p className="text-sm text-slate-500">No telemetry recorded.</p>}
      {latest && (
        <dl className="grid grid-cols-2 gap-3">
          <Field label="Recorded">{dateTime(latest.recorded_at)}</Field>
          <Field label="Idle ratio">{percent(latest.idle_ratio)}</Field>
          <Field label="Fuel used">{number(latest.fuel_used_liters, 1)} L</Field>
          <Field label="Engine temp">{number(latest.engine_temp_c, 1)} °C</Field>
        </dl>
      )}
      <Link to={`/machines/${machine.machine_id}`} className="inline-block text-sm font-medium text-slate-700 underline">
        Open machine monitoring
      </Link>
    </div>
  );
}
