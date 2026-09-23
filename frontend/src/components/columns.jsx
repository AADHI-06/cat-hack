// Table column definitions reused across pages.
import { Link } from "react-router";
import { dateTime, label, minutes, number } from "../format.js";
import { SeverityBadge } from "./ui.jsx";

const linkClass = "font-medium text-slate-900 underline decoration-slate-300 underline-offset-2 hover:decoration-slate-600";

export const safetyEventColumns = [
  { key: "timestamp", header: "Time", render: (e) => dateTime(e.timestamp) },
  { key: "severity", header: "Severity", render: (e) => <SeverityBadge severity={e.severity} /> },
  { key: "event_type", header: "Event", render: (e) => label(e.event_type) },
  { key: "description", header: "Observed condition" },
  {
    key: "operator_id",
    header: "Operator",
    render: (e) => (
      <Link className={linkClass} to={`/operator/${e.operator_id}`}>
        {e.operator_id}
      </Link>
    ),
  },
  {
    key: "machine_id",
    header: "Machine",
    render: (e) => (
      <Link className={linkClass} to={`/machines/${e.machine_id}`}>
        {e.machine_id}
      </Link>
    ),
  },
  // Optional in the Safety Event contract: a live event may have no task.
  { key: "task_id", header: "Task", className: "text-slate-500", render: (e) => e.task_id || "-" },
];

export const executionColumns = [
  { key: "shift_date", header: "Date" },
  { key: "shift", header: "Shift", render: (h) => label(h.shift) },
  { key: "task_type", header: "Task type", render: (h) => label(h.task_type) },
  { key: "machine_id", header: "Machine" },
  { key: "quantity", header: "Quantity", className: "text-right", render: (h) => `${number(h.quantity)} ${h.quantity_unit}` },
  { key: "weather", header: "Weather", render: (h) => label(h.weather) },
  { key: "estimated_minutes", header: "Planner est.", className: "text-right", render: (h) => minutes(h.estimated_minutes) },
  { key: "actual_minutes", header: "Actual", className: "text-right", render: (h) => minutes(h.actual_minutes) },
];
