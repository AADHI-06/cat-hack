"""Platform API: routes respond, validate input, and never fabricate intelligence."""

import pytest

from app.main import app


def test_foundation_routes_still_work(client):
    assert client.get("/").json()["data_source"] == "synthetic"
    assert client.get("/health").json() == {"status": "healthy"}


def test_api_routes_registered():
    paths = {route.path for route in app.routes}
    for path in [
        "/api/system/status",
        "/api/operators", "/api/operators/{operator_id}",
        "/api/machines", "/api/machines/{machine_id}", "/api/machines/{machine_id}/telemetry",
        "/api/tasks", "/api/tasks/{task_id}",
        "/api/safety/events", "/api/safety/summary",
        "/api/dashboard/operator/{operator_id}", "/api/dashboard/supervisor",
    ]:
        assert path in paths


# --- system -----------------------------------------------------------------

def test_system_status_loaded(client):
    body = client.get("/api/system/status").json()
    assert body["database_loaded"] is True
    assert body["table_counts"]["operators"] == 3
    assert body["data_source"] == "synthetic"
    assert "not real Caterpillar data" in body["disclaimer"]


def test_system_status_empty_database(empty_client):
    body = empty_client.get("/api/system/status").json()
    assert body["database_loaded"] is False
    assert set(body["table_counts"].values()) == {0}


def test_no_intelligence_service_claims_availability(client):
    services = client.get("/api/system/status").json()["services"]
    assert {s["key"] for s in services} >= {
        "task_prediction", "optimization", "safety_intelligence", "anomaly_detection",
    }
    assert all(s["available"] is False for s in services)


# --- operators --------------------------------------------------------------

def test_list_operators(client):
    body = client.get("/api/operators").json()
    assert [o["operator_id"] for o in body] == ["OP001", "OP002", "OP003"]
    assert body[0]["certifications"] == ["EXCAVATOR_OP", "DOZER_OP"]
    assert all(o["data_source"] == "synthetic" for o in body)


def test_filter_operators(client):
    body = client.get("/api/operators", params={"skill_level": "BEGINNER"}).json()
    assert [o["operator_id"] for o in body] == ["OP002"]


def test_get_operator_and_404(client):
    assert client.get("/api/operators/OP003").json()["skill_level"] == "INTERMEDIATE"
    assert client.get("/api/operators/OP999").status_code == 404


# --- machines ---------------------------------------------------------------

def test_list_and_get_machines(client):
    assert len(client.get("/api/machines").json()) == 2
    machine = client.get("/api/machines/M001").json()
    assert machine["machine_type"] == "EXCAVATOR"
    assert machine["data_source"] == "synthetic"
    assert client.get("/api/machines/M999").status_code == 404


def test_machine_telemetry_hides_injected_anomaly_label(client):
    readings = client.get("/api/machines/M002/telemetry").json()
    assert len(readings) == 1
    assert readings[0]["idle_ratio"] == 0.5
    assert "injected_anomaly_type" not in readings[0]
    assert readings[0]["data_source"] == "synthetic"


def test_machine_telemetry_404_and_limits(client):
    assert client.get("/api/machines/M999/telemetry").status_code == 404
    assert client.get("/api/machines/M001/telemetry", params={"limit": 0}).status_code == 422
    assert client.get("/api/machines/M001/telemetry", params={"limit": 501}).status_code == 422


# --- tasks ------------------------------------------------------------------

def test_list_tasks(client):
    body = client.get("/api/tasks").json()
    assert [t["task_id"] for t in body] == ["T001", "T002", "T003"]
    assert body[0]["depends_on_task_id"] is None
    assert body[1]["depends_on_task_id"] == "T001"
    assert body[0]["shift_date"] == "2026-09-24"


def test_tasks_carry_no_fabricated_prediction(client):
    task = client.get("/api/tasks/T001").json()
    assert "predicted_minutes" not in task
    assert task["estimated_minutes"] == 190


def test_filter_tasks(client):
    ids = lambda params: [t["task_id"] for t in client.get("/api/tasks", params=params).json()]
    assert ids({"status": "BLOCKED"}) == ["T002"]
    assert ids({"site_zone": "ZONE_B"}) == ["T003"]
    assert ids({"shift_date": "2026-09-25"}) == ["T003"]
    assert ids({"priority": "CRITICAL"}) == []


def test_get_task_404(client):
    assert client.get("/api/tasks/T999").status_code == 404


@pytest.mark.parametrize("url, params", [
    ("/api/tasks", {"status": "DONE"}),
    ("/api/tasks", {"shift_date": "not-a-date"}),
    ("/api/operators", {"skill_level": "GURU"}),
    ("/api/machines", {"machine_type": "CRANE"}),
    ("/api/safety/events", {"severity": "CRITICAL"}),
    ("/api/safety/events", {"event_type": "SPEEDING"}),
    ("/api/safety/events", {"limit": -1}),
])
def test_invalid_query_values_rejected(client, url, params):
    assert client.get(url, params=params).status_code == 422


# --- safety -----------------------------------------------------------------

def test_list_safety_events(client):
    body = client.get("/api/safety/events").json()
    assert len(body) == 3
    assert body[0]["event_id"] == "SE0003"  # newest first, then by id desc
    assert {e["severity"] for e in body} == {"HIGH", "LOW"}
    assert all(e["data_source"] == "synthetic" for e in body)


def test_filter_safety_events(client):
    body = client.get("/api/safety/events", params={"severity": "HIGH"}).json()
    assert {e["event_id"] for e in body} == {"SE0001", "SE0002"}
    assert client.get("/api/safety/events", params={"operator_id": "OP001"}).json() == []


def test_safety_event_without_task_is_served(client, loaded_db):
    """A contract-shaped live event (no task_id/history_id) passes through the API unchanged."""
    from app.services.database import connect

    conn = connect(loaded_db)
    with conn:
        conn.execute(
            "INSERT INTO safety_events VALUES ('SE9001', '2026-09-23T09:00:00', 'OP001', 'M001', NULL, NULL, "
            "'PROXIMITY', 'MEDIUM', 'Potential proximity hazard detected', 'live')"
        )
    conn.close()

    event = client.get("/api/safety/events", params={"operator_id": "OP001"}).json()[0]
    assert event["task_id"] is None and event["history_id"] is None
    assert event["data_source"] == "live"
    assert client.get("/api/dashboard/operator/OP001").status_code == 200


def test_safety_summary(client):
    body = client.get("/api/safety/summary").json()
    assert body == {
        "total": 3,
        "by_severity": {"HIGH": 2, "LOW": 1},
        "by_event_type": {"EXCESSIVE_IDLING": 1, "PROXIMITY": 1, "SEATBELT": 1},
    }


# --- dashboards -------------------------------------------------------------

def test_operator_dashboard(client):
    body = client.get("/api/dashboard/operator/OP002").json()
    assert body["operator"]["operator_id"] == "OP002"
    assert body["safety_summary"]["total"] == 3
    assert len(body["recent_safety_events"]) == 3
    assert [h["history_id"] for h in body["recent_executions"]] == ["TH00002"]
    assert body["data_source"] == "synthetic"
    # Nothing that Claude A's services would produce is invented here.
    assert not {"predicted_minutes", "shift_plan", "assigned_machine", "anomalies"} & body.keys()


def test_operator_dashboard_without_events(client):
    body = client.get("/api/dashboard/operator/OP003").json()
    assert body["safety_summary"] == {"total": 0, "by_severity": {}, "by_event_type": {}}
    assert body["recent_executions"] == []


def test_operator_dashboard_404(client):
    assert client.get("/api/dashboard/operator/OP999").status_code == 404


def test_supervisor_dashboard_covers_all_operators_and_machines(client):
    body = client.get("/api/dashboard/supervisor").json()
    assert len(body["operators"]) == 3
    assert len(body["machines"]) == 2
    assert body["task_summary"] == {
        "total": 3,
        "by_status": {"BLOCKED": 1, "PENDING": 2},
        "by_priority": {"HIGH": 1, "LOW": 1, "MEDIUM": 1},
    }
    assert body["safety_summary"]["total"] == 3
    assert body["data_source"] == "synthetic"


def test_supervisor_dashboard_on_empty_database(empty_client):
    body = empty_client.get("/api/dashboard/supervisor").json()
    assert body["operators"] == [] and body["machines"] == []
    assert body["task_summary"]["total"] == 0
