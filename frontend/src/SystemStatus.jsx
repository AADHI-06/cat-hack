import { createContext, useContext } from "react";
import { api } from "./api.js";
import { useApi } from "./useApi.js";

// /api/system/status, fetched once and shared: database state plus which
// intelligence services are connected.
const SystemStatusContext = createContext({ data: null, error: null, loading: true });

export function SystemStatusProvider({ children }) {
  const state = useApi(() => api.systemStatus(), []);
  return <SystemStatusContext.Provider value={state}>{children}</SystemStatusContext.Provider>;
}

export function useSystemStatus() {
  return useContext(SystemStatusContext);
}

// Look up one service (e.g. "task_prediction") from a services list.
export function findService(services, key) {
  return services?.find((service) => service.key === key);
}

export function useService(key) {
  return findService(useSystemStatus().data?.services, key);
}
