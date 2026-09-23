import { Navigate, Route, Routes } from "react-router";
import Layout from "./components/Layout.jsx";
import { SystemStatusProvider } from "./SystemStatus.jsx";
import IncidentHistory from "./pages/IncidentHistory.jsx";
import MachineMonitoring from "./pages/MachineMonitoring.jsx";
import OperatorDashboard from "./pages/OperatorDashboard.jsx";
import SafetyAlerts from "./pages/SafetyAlerts.jsx";
import SupervisorDashboard from "./pages/SupervisorDashboard.jsx";
import TaskManagement from "./pages/TaskManagement.jsx";
import TrainingHub from "./pages/TrainingHub.jsx";

export default function App() {
  return (
    <SystemStatusProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Navigate to="/supervisor" replace />} />
          <Route path="/operator/:operatorId?" element={<OperatorDashboard />} />
          <Route path="/supervisor" element={<SupervisorDashboard />} />
          <Route path="/tasks" element={<TaskManagement />} />
          <Route path="/safety" element={<SafetyAlerts />} />
          <Route path="/machines/:machineId?" element={<MachineMonitoring />} />
          <Route path="/training" element={<TrainingHub />} />
          <Route path="/incidents" element={<IncidentHistory />} />
          <Route path="*" element={<Navigate to="/supervisor" replace />} />
        </Routes>
      </Layout>
    </SystemStatusProvider>
  );
}
