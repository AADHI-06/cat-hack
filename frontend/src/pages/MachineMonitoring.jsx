import { Navigate, useNavigate, useParams } from "react-router";
import { api } from "../api.js";
import { safetyEventColumns } from "../components/columns.jsx";
import { Async, EmptyState, Field, PageHeader, Panel, ServiceNotice, Stat, Table } from "../components/ui.jsx";
import { dateTime, label, minutes, number, percent } from "../format.js";
import { useService } from "../SystemStatus.jsx";
import { useApi } from "../useApi.js";

const HISTORY_SIZE = 20;

// Raw telemetry values as recorded. No thresholds or scores are applied here.
const readingColumns = [
  { key: "recorded_at", header: "Recorded", render: (t) => dateTime(t.recorded_at) },
  { key: "operator_id", header: "Operator" },
  { key: "runtime_minutes", header: "Runtime", className: "text-right", render: (t) => minutes(t.runtime_minutes) },
  { key: "idle_ratio", header: "Idle", className: "text-right", render: (t) => percent(t.idle_ratio) },
  { key: "fuel_used_liters", header: "Fuel (L)", className: "text-right", render: (t) => number(t.fuel_used_liters, 1) },
  { key: "load_cycles", header: "Cycles", className: "text-right" },
  { key: "avg_load_pct", header: "Avg load", className: "text-right", render: (t) => `${number(t.avg_load_pct, 1)}%` },
  { key: "engine_temp_c", header: "Temp (°C)", className: "text-right", render: (t) => number(t.engine_temp_c, 1) },
  { key: "max_speed_kph", header: "Max speed", className: "text-right", render: (t) => `${number(t.max_speed_kph, 1)} kph` },
  { key: "seatbelt_fastened_pct", header: "Seatbelt", className: "text-right", render: (t) => `${number(t.seatbelt_fastened_pct, 0)}%` },
  { key: "min_proximity_m", header: "Min prox.", className: "text-right", render: (t) => `${number(t.min_proximity_m, 1)} m` },
];

export default function MachineMonitoring() {
  const { machineId } = useParams();
  const navigate = useNavigate();
  const machines = useApi(() => api.machines(), []);

  if (!machineId && machines.data?.length) {
    return <Navigate to={`/machines/${machines.data[0].machine_id}`} replace />;
  }

  return (
    <>
      <PageHeader title="Machine Monitoring" subtitle="Recorded telemetry per machine." />
      <div className="grid gap-4 lg:grid-cols-4">
        <Panel title="Fleet" className="lg:col-span-1">
          <Async state={machines}>
            {(list) =>
              list.length ? (
                <ul className="-mx-2 max-h-[40rem] overflow-y-auto">
                  {list.map((m) => (
                    <li key={m.machine_id}>
                      <button
                        type="button"
                        onClick={() => navigate(`/machines/${m.machine_id}`)}
                        className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm ${
                          m.machine_id === machineId ? "bg-yellow-50 font-semibold" : "hover:bg-slate-50"
                        }`}
                      >
                        <span>{m.machine_id} <span className="font-normal text-slate-500">{m.model}</span></span>
                        <span className="text-xs text-slate-500">{label(m.machine_type)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No machines loaded." />
              )
            }
          </Async>
        </Panel>
        <div className="lg:col-span-3">{machineId && <MachineView machineId={machineId} />}</div>
      </div>
    </>
  );
}

function MachineView({ machineId }) {
  const machine = useApi(() => api.machine(machineId), [machineId]);
  const readings = useApi(() => api.machineTelemetry(machineId, { limit: HISTORY_SIZE }), [machineId]);
  const events = useApi(() => api.safetyEvents({ machine_id: machineId, limit: 10 }), [machineId]);
  const anomaly = useService("anomaly_detection");

  return (
    <div className="space-y-4">
      <Async state={machine}>
        {(m) => (
          <Panel title={`${m.machine_id} - ${m.model}`}>
            <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <Field label="Type">{label(m.machine_type)}</Field>
              <Field label="Home zone">{label(m.home_zone)}</Field>
              <Field label="Year / age">{m.year_manufactured} / {m.age_years} yrs</Field>
              <Field label="Condition rating">{number(m.condition_rating, 2)}</Field>
              <Field label="Engine hours">{number(m.engine_hours, 1)}</Field>
              <Field label="Capacity">{number(m.capacity_units, 1)} units</Field>
              <Field label="Anomaly status"><ServiceNotice service={anomaly} compact /></Field>
            </dl>
          </Panel>
        )}
      </Async>

      <Async state={readings}>
        {(rows) => {
          const latest = rows[0];
          if (!latest) return <EmptyState title="No telemetry recorded for this machine." />;
          return (
            <>
              <Panel title={`Latest reading - ${dateTime(latest.recorded_at)}`}>
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-5">
                  <Stat label="Engine hours" value={number(latest.engine_hours_reading, 1)} />
                  <Stat label="Runtime" value={minutes(latest.runtime_minutes)} />
                  <Stat label="Idle time" value={minutes(latest.idle_minutes)} hint={`${percent(latest.idle_ratio)} of runtime`} />
                  <Stat label="Fuel used" value={`${number(latest.fuel_used_liters, 1)} L`} hint={`${number(latest.fuel_per_unit, 2)} L per unit`} />
                  <Stat label="Load cycles" value={number(latest.load_cycles)} />
                  <Stat label="Average load" value={`${number(latest.avg_load_pct, 1)}%`} hint={`variance ${number(latest.load_variance, 1)}`} />
                  <Stat label="Engine temp" value={`${number(latest.engine_temp_c, 1)} °C`} />
                  <Stat label="Hydraulic pressure" value={`${number(latest.hydraulic_pressure_psi)} psi`} />
                  <Stat label="Max speed" value={`${number(latest.max_speed_kph, 1)} kph`} />
                  <Stat label="Seatbelt fastened" value={`${number(latest.seatbelt_fastened_pct, 0)}%`} hint="share of runtime" />
                  <Stat label="Min proximity" value={`${number(latest.min_proximity_m, 1)} m`} />
                  <Stat label="Proximity alerts" value={latest.proximity_alerts_count} />
                </div>
              </Panel>
              <Panel title={`Last ${rows.length} readings`}>
                <Table columns={readingColumns} rows={rows} rowKey={(t) => t.telemetry_id} />
              </Panel>
            </>
          );
        }}
      </Async>

      <Panel title="Recorded safety events for this machine">
        <Async state={events}>
          {(rows) => (
            <Table
              columns={safetyEventColumns.filter((c) => c.key !== "machine_id")}
              rows={rows}
              rowKey={(e) => e.event_id}
              empty="No safety events recorded for this machine."
            />
          )}
        </Async>
      </Panel>
    </div>
  );
}
