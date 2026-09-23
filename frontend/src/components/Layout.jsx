import { NavLink } from "react-router";
import { useSystemStatus } from "../SystemStatus.jsx";

const NAV = [
  { to: "/operator", label: "Operator Dashboard" },
  { to: "/supervisor", label: "Supervisor Dashboard" },
  { to: "/tasks", label: "Task Management" },
  { to: "/safety", label: "Safety / Alerts" },
  { to: "/machines", label: "Machine Monitoring" },
  { to: "/training", label: "Training Hub" },
  { to: "/incidents", label: "Incident History" },
];

function SyntheticBanner() {
  return (
    <div className="border-b border-amber-300 bg-amber-50 px-4 py-1.5 text-xs text-amber-900">
      <span className="font-semibold">SYNTHETIC DATA</span> - generated for a hackathon prototype. Not real
      Caterpillar operational data. Decision support only; does not replace certified safety systems or human
      supervision.
    </div>
  );
}

function DatabaseNotice() {
  const { data, error } = useSystemStatus();
  if (error) {
    return (
      <div className="border-b border-red-200 bg-red-50 px-4 py-2 text-sm text-red-800">
        Backend not reachable. Start it with <code>uvicorn app.main:app --reload --app-dir backend</code>.
      </div>
    );
  }
  if (data && !data.database_loaded) {
    return (
      <div className="border-b border-slate-300 bg-slate-200 px-4 py-2 text-sm text-slate-800">
        The database is empty. Generate the synthetic data (<code>python -m scripts.data_generation.generate</code>)
        and load it (<code>python -m app.services.database.loader</code> from <code>backend/</code>).
      </div>
    );
  }
  return null;
}

export default function Layout({ children }) {
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="shrink-0 bg-slate-900 text-slate-200 md:w-60">
        <div className="flex items-center gap-2 border-b border-slate-700 px-4 py-4">
          <span className="h-6 w-1.5 rounded-sm bg-brand" aria-hidden="true" />
          <div className="leading-tight">
            <div className="text-sm font-semibold text-white">Smart Operator Assistant</div>
            <div className="text-xs text-slate-400">Hackathon prototype</div>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-2 py-2 md:flex-col md:overflow-visible">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `whitespace-nowrap rounded px-3 py-2 text-sm ${
                  isActive
                    ? "bg-slate-800 font-semibold text-white md:border-l-2 md:border-brand"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <SyntheticBanner />
        <DatabaseNotice />
        <main className="flex-1 px-4 py-5 md:px-6">{children}</main>
      </div>
    </div>
  );
}
