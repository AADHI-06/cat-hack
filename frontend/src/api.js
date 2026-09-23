// Thin client for the FastAPI backend. The UI only renders what these return:
// no predictions, severities or anomaly scores are computed in the browser.

async function get(path, params = {}) {
  const query = new URLSearchParams(
    Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== ""),
  ).toString();
  const response = await fetch(`/api${path}${query ? `?${query}` : ""}`);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = typeof body.detail === "string" ? body.detail : response.statusText;
    throw new Error(`${response.status} ${detail}`);
  }
  return response.json();
}

export const api = {
  systemStatus: () => get("/system/status"),
  operators: (params) => get("/operators", params),
  machines: (params) => get("/machines", params),
  machine: (id) => get(`/machines/${id}`),
  machineTelemetry: (id, params) => get(`/machines/${id}/telemetry`, params),
  tasks: (params) => get("/tasks", params),
  safetyEvents: (params) => get("/safety/events", params),
  safetySummary: (params) => get("/safety/summary", params),
  operatorDashboard: (id) => get(`/dashboard/operator/${id}`),
  supervisorDashboard: () => get("/dashboard/supervisor"),
};
