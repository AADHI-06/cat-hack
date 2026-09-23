// Small shared building blocks. Presentation only.
import { label } from "../format.js";

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </div>
  );
}

export function Panel({ title, action, children, className = "" }) {
  return (
    <section className={`min-w-0 rounded-md border border-slate-200 bg-white ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-2.5">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-600">{title}</h2>
          {action}
        </div>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

export function Stat({ label: text, value, hint }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-500">{text}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

export function Field({ label: text, children }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">{text}</dt>
      <dd className="mt-0.5 text-sm font-medium text-slate-900">{children}</dd>
    </div>
  );
}

// Severity comes from the backend. This only chooses a colour for it.
const SEVERITY_STYLES = {
  HIGH: "bg-red-100 text-red-800 ring-red-300",
  MEDIUM: "bg-amber-100 text-amber-900 ring-amber-300",
  LOW: "bg-sky-100 text-sky-800 ring-sky-300",
};

export function SeverityBadge({ severity }) {
  const style = SEVERITY_STYLES[severity] || "bg-slate-100 text-slate-700 ring-slate-300";
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${style}`}>
      {severity}
    </span>
  );
}

const PRIORITY_STYLES = {
  CRITICAL: "bg-red-600 text-white",
  HIGH: "bg-orange-100 text-orange-900",
  MEDIUM: "bg-slate-200 text-slate-800",
  LOW: "bg-slate-100 text-slate-600",
};

export function PriorityBadge({ priority }) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${PRIORITY_STYLES[priority] || ""}`}>
      {priority}
    </span>
  );
}

export function Tag({ children }) {
  return (
    <span className="inline-block rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
      {children}
    </span>
  );
}

export function Loading({ text = "Loading..." }) {
  return <p className="py-6 text-center text-sm text-slate-500">{text}</p>;
}

export function ErrorMessage({ error }) {
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      <p className="font-semibold">Could not load data from the backend.</p>
      <p className="mt-1">{error?.message}</p>
      <p className="mt-1 text-red-700">
        Check that the API is running: <code>uvicorn app.main:app --reload --app-dir backend</code>
      </p>
    </div>
  );
}

export function EmptyState({ title, children }) {
  return (
    <div className="rounded-md border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-center">
      <p className="text-sm font-medium text-slate-700">{title}</p>
      {children && <div className="mt-1 text-sm text-slate-500">{children}</div>}
    </div>
  );
}

// An honest placeholder for a capability that is not built or connected yet.
export function ServiceNotice({ service, compact = false }) {
  if (!service) return null;
  if (compact) {
    return <span className="text-sm italic text-slate-500">{service.message}</span>;
  }
  return (
    <EmptyState title={service.message}>
      {service.name} is provided by Module {service.module} and is not connected yet.
    </EmptyState>
  );
}

// Renders whichever of loading / error / content applies.
export function Async({ state, children }) {
  if (state.error) return <ErrorMessage error={state.error} />;
  if (state.loading && !state.data) return <Loading />;
  return children(state.data);
}

export function Table({ columns, rows, rowKey, onRowClick, selectedKey, empty = "No records." }) {
  if (!rows.length) return <EmptyState title={empty} />;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500">
            {columns.map((column) => (
              <th key={column.key} className={`whitespace-nowrap px-3 py-2 font-medium ${column.className || ""}`}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const key = rowKey(row);
            const selected = key === selectedKey;
            return (
              <tr
                key={key}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={`border-b border-slate-100 last:border-0 ${
                  onRowClick ? "cursor-pointer hover:bg-slate-50" : ""
                } ${selected ? "bg-yellow-50" : ""}`}
              >
                {columns.map((column) => (
                  <td key={column.key} className={`whitespace-nowrap px-3 py-2 ${column.className || ""}`}>
                    {column.render ? column.render(row) : row[column.key]}
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function Select({ value, onChange, options, placeholder, ariaLabel }) {
  return (
    <select
      aria-label={ariaLabel || placeholder}
      value={value ?? ""}
      onChange={(event) => onChange(event.target.value || null)}
      className="rounded-md border border-slate-300 bg-white px-2.5 py-1.5 text-sm text-slate-800 focus:border-slate-500 focus:outline-none"
    >
      {placeholder && <option value="">{placeholder}</option>}
      {options.map((option) => {
        const [optionValue, optionLabel] = Array.isArray(option) ? option : [option, label(option)];
        return (
          <option key={optionValue} value={optionValue}>
            {optionLabel}
          </option>
        );
      })}
    </select>
  );
}

// `order` lists keys in display order (e.g. HIGH, MEDIUM, LOW); others follow.
export function CountList({ counts, render, order = [] }) {
  const rank = (key) => (order.includes(key) ? order.indexOf(key) : order.length);
  const entries = Object.entries(counts || {}).sort(([a], [b]) => rank(a) - rank(b));
  if (!entries.length) return <p className="text-sm text-slate-500">None recorded.</p>;
  return (
    <ul className="space-y-1.5">
      {entries.map(([key, count]) => (
        <li key={key} className="flex items-center justify-between text-sm">
          <span>{render ? render(key) : label(key)}</span>
          <span className="font-semibold tabular-nums">{count}</span>
        </li>
      ))}
    </ul>
  );
}
