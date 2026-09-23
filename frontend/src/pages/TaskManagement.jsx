import { useState } from "react";
import { api } from "../api.js";
import { Async, PageHeader, Panel, PriorityBadge, Select, ServiceNotice, Table, Tag } from "../components/ui.jsx";
import { label, minutes, number } from "../format.js";
import { useService } from "../SystemStatus.jsx";
import { useApi } from "../useApi.js";
import { MACHINE_TYPES, PRIORITIES, TASK_STATUSES, ZONES } from "../vocab.js";

const EMPTY_FILTERS = { status: null, priority: null, site_zone: null, required_machine_type: null };

export default function TaskManagement() {
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const state = useApi(() => api.tasks(filters), [JSON.stringify(filters)]);
  const prediction = useService("task_prediction");
  const optimization = useService("optimization");
  const setFilter = (key) => (value) => setFilters((current) => ({ ...current, [key]: value }));

  const columns = [
    { key: "task_id", header: "Task", className: "font-medium" },
    { key: "status", header: "Status", render: (t) => <Tag>{label(t.status)}</Tag> },
    { key: "priority", header: "Priority", render: (t) => <PriorityBadge priority={t.priority} /> },
    { key: "shift_date", header: "Shift date" },
    { key: "task_type", header: "Type", render: (t) => label(t.task_type) },
    { key: "difficulty", header: "Diff.", className: "text-right" },
    { key: "quantity", header: "Quantity", className: "text-right", render: (t) => `${number(t.quantity)} ${t.quantity_unit}` },
    { key: "required_machine_type", header: "Machine", render: (t) => label(t.required_machine_type) },
    { key: "site_zone", header: "Zone", render: (t) => label(t.site_zone) },
    { key: "terrain", header: "Terrain", render: (t) => label(t.terrain) },
    { key: "business_value", header: "Value", className: "text-right", render: (t) => number(t.business_value) },
    { key: "depends_on_task_id", header: "Depends on", render: (t) => t.depends_on_task_id || <span className="text-slate-400">-</span> },
    { key: "estimated_minutes", header: "Planner est.", className: "text-right", render: (t) => minutes(t.estimated_minutes) },
    { key: "predicted", header: "Predicted", render: () => <span className="text-slate-400">Unavailable</span> },
    { key: "optimizer", header: "Optimizer", render: () => <span className="text-slate-400">Not run</span> },
    { key: "required_certification", header: "Certification", render: (t) => label(t.required_certification) },
  ];

  return (
    <>
      <PageHeader title="Task Management" subtitle="Scheduled task backlog for the coming shifts.">
        <Select placeholder="All statuses" value={filters.status} onChange={setFilter("status")} options={TASK_STATUSES} />
        <Select placeholder="All priorities" value={filters.priority} onChange={setFilter("priority")} options={PRIORITIES} />
        <Select placeholder="All zones" value={filters.site_zone} onChange={setFilter("site_zone")} options={ZONES} />
        <Select
          placeholder="All machine types"
          value={filters.required_machine_type}
          onChange={setFilter("required_machine_type")}
          options={MACHINE_TYPES}
        />
      </PageHeader>

      <div className="mb-4 grid gap-3 md:grid-cols-2">
        <div className="rounded-md border border-slate-200 bg-white px-4 py-2.5 text-sm">
          <span className="font-medium">Predicted duration: </span>
          <ServiceNotice service={prediction} compact />
          <span className="block text-xs text-slate-500">"Planner est." is the planner's pre-task estimate, not an ML prediction.</span>
        </div>
        <div className="rounded-md border border-slate-200 bg-white px-4 py-2.5 text-sm">
          <span className="font-medium">Task selection: </span>
          <ServiceNotice service={optimization} compact />
        </div>
      </div>

      <Panel title={state.data ? `${state.data.length} tasks` : "Tasks"}>
        <Async state={state}>
          {(tasks) => <Table columns={columns} rows={tasks} rowKey={(t) => t.task_id} empty="No tasks match these filters." />}
        </Async>
      </Panel>
    </>
  );
}
