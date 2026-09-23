import { Navigate, useNavigate, useParams } from "react-router";
import { api } from "../api.js";
import { executionColumns, safetyEventColumns } from "../components/columns.jsx";
import {
  Async, CountList, EmptyState, Field, PageHeader, Panel, Select, ServiceNotice, SeverityBadge, Table, Tag,
} from "../components/ui.jsx";
import { label } from "../format.js";
import { findService } from "../SystemStatus.jsx";
import { useApi } from "../useApi.js";
import { SEVERITIES } from "../vocab.js";

export default function OperatorDashboard() {
  const { operatorId } = useParams();
  const navigate = useNavigate();
  const operators = useApi(() => api.operators(), []);
  const dashboard = useApi(
    () => (operatorId ? api.operatorDashboard(operatorId) : Promise.resolve(null)),
    [operatorId],
  );

  // No operator chosen yet: open the first one rather than assuming a fixed id.
  if (!operatorId && operators.data?.length) {
    return <Navigate to={`/operator/${operators.data[0].operator_id}`} replace />;
  }

  const selector = (
    <Select
      ariaLabel="Operator"
      value={operatorId}
      onChange={(id) => id && navigate(`/operator/${id}`)}
      options={(operators.data || []).map((o) => [o.operator_id, `${o.operator_id} - ${o.name}`])}
    />
  );

  return (
    <>
      <PageHeader title="Operator Dashboard" subtitle="What to do next, how long it takes, and whether it is safe.">
        {selector}
      </PageHeader>

      {!operatorId && !operators.loading && !operators.error ? (
        <EmptyState title="No operators in the database." />
      ) : (
        <Async state={operators.error ? operators : dashboard}>
          {(data) => data && <OperatorView data={data} />}
        </Async>
      )}
    </>
  );
}

function OperatorView({ data }) {
  const { operator, safety_summary: safety, services } = data;
  const service = (key) => findService(services, key);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Operator">
          <dl className="grid grid-cols-2 gap-3">
            <Field label="Name">{operator.name}</Field>
            <Field label="ID">{operator.operator_id}</Field>
            <Field label="Skill level">{label(operator.skill_level)}</Field>
            <Field label="Experience">{operator.experience_years} years</Field>
            <Field label="Primary shift">{label(operator.primary_shift)}</Field>
          </dl>
          <div className="mt-3">
            <div className="text-xs uppercase tracking-wide text-slate-500">Certifications</div>
            <div className="mt-1 flex flex-wrap gap-1">
              {operator.certifications.map((cert) => <Tag key={cert}>{label(cert)}</Tag>)}
            </div>
          </div>
        </Panel>

        <Panel title="Assigned machine">
          <ServiceNotice service={service("optimization")} />
        </Panel>

        <Panel title="Live safety status">
          <ServiceNotice service={service("safety_intelligence")} />
        </Panel>
      </div>

      <Panel title="Today's tasks">
        <div className="space-y-2">
          <ServiceNotice service={service("optimization")} />
          <p className="text-sm text-slate-500">
            Predicted durations: <ServiceNotice service={service("task_prediction")} compact />
          </p>
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Recorded safety events">
          <div className="mb-3 text-3xl font-semibold tabular-nums">{safety.total}</div>
          <CountList counts={safety.by_severity} order={SEVERITIES} render={(s) => <SeverityBadge severity={s} />} />
        </Panel>
        <Panel title="Most recent safety events" className="lg:col-span-2">
          <Table
            columns={safetyEventColumns.filter((c) => c.key !== "operator_id")}
            rows={data.recent_safety_events}
            rowKey={(e) => e.event_id}
            empty="No recorded safety events for this operator."
          />
        </Panel>
      </div>

      <Panel title="Recent completed work">
        <Table
          columns={executionColumns}
          rows={data.recent_executions}
          rowKey={(h) => h.history_id}
          empty="No completed work recorded for this operator."
        />
      </Panel>

      <Panel title="Training recommendations">
        <ServiceNotice service={service("training")} />
      </Panel>
    </div>
  );
}
