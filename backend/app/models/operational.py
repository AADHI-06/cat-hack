"""
Response models for the Module 1 operational tables.

Field names and vocabularies follow docs/synthetic_data.md section 3 exactly.
Every model carries data_source so the marker reaches the UI unchanged. Module 1
records are always "synthetic"; the field is a plain string so records created
by later modules can carry their own source.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, field_validator

DataSource = str

SkillLevel = Literal["BEGINNER", "INTERMEDIATE", "EXPERT"]
Shift = Literal["DAY", "NIGHT"]
MachineType = Literal["EXCAVATOR", "DOZER", "LOADER", "HAUL_TRUCK", "GRADER"]
TaskType = Literal["EXCAVATION", "TRENCHING", "LOADING", "HAULING", "GRADING", "BACKFILL", "SITE_CLEARING"]
QuantityUnit = Literal["m3", "m", "m2", "loads", "trips"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
TaskStatus = Literal["PENDING", "IN_PROGRESS", "COMPLETED", "BLOCKED"]
Terrain = Literal["FLAT", "SLOPED", "ROUGH"]
Weather = Literal["CLEAR", "CLOUDY", "RAIN", "HEAVY_RAIN", "FOG"]
Zone = Literal["ZONE_A", "ZONE_B", "ZONE_C", "ZONE_D"]
SafetyEventType = Literal["SEATBELT", "PROXIMITY", "EXCESSIVE_IDLING", "OVERSPEED", "UNCERTIFIED_OPERATION"]
Severity = Literal["LOW", "MEDIUM", "HIGH"]


class Operator(BaseModel):
    operator_id: str
    name: str
    skill_level: SkillLevel
    experience_years: int
    certifications: list[str]
    primary_shift: Shift
    data_source: DataSource

    @field_validator("certifications", mode="before")
    @classmethod
    def split_certifications(cls, value):
        # Stored as "EXCAVATOR_OP|DOZER_OP" (docs/synthetic_data.md 3.1).
        if isinstance(value, str):
            return [cert for cert in value.split("|") if cert]
        return value


class Machine(BaseModel):
    machine_id: str
    machine_type: MachineType
    model: str
    year_manufactured: int
    age_years: int
    engine_hours: float
    condition_rating: float
    capacity_units: float
    home_zone: Zone
    data_source: DataSource


class Task(BaseModel):
    """A pending backlog task. estimated_minutes is the planner's estimate, not an ML prediction."""

    task_id: str
    task_type: TaskType
    difficulty: int
    quantity: int
    quantity_unit: QuantityUnit
    required_machine_type: MachineType
    required_certification: str
    priority: Priority
    business_value: int
    depends_on_task_id: str | None
    site_zone: Zone
    terrain: Terrain
    estimated_minutes: int
    status: TaskStatus
    shift_date: date
    data_source: DataSource


class TaskHistory(BaseModel):
    """One completed execution."""

    history_id: str
    task_id: str
    operator_id: str
    machine_id: str
    task_type: TaskType
    difficulty: int
    quantity: int
    quantity_unit: QuantityUnit
    required_machine_type: MachineType
    terrain: Terrain
    priority: Priority
    business_value: int
    shift: Shift
    shift_date: date
    started_at: datetime
    completed_at: datetime
    temperature: float
    rainfall: float
    humidity: float
    wind_speed: float
    visibility: float
    weather: Weather
    estimated_minutes: int
    actual_minutes: float
    data_source: DataSource


class Telemetry(BaseModel):
    """
    Machine telemetry for one execution.

    injected_anomaly_type is deliberately NOT exposed: it is synthetic ground
    truth for validating Module 5, not a detected anomaly
    (docs/synthetic_data.md section 7).
    """

    telemetry_id: str
    history_id: str
    task_id: str
    machine_id: str
    operator_id: str
    recorded_at: datetime
    engine_hours_reading: float
    runtime_minutes: float
    idle_minutes: float
    idle_ratio: float
    fuel_used_liters: float
    fuel_per_unit: float
    load_cycles: int
    avg_load_pct: float
    load_variance: float
    engine_temp_c: float
    hydraulic_pressure_psi: float
    max_speed_kph: float
    seatbelt_fastened_pct: float
    min_proximity_m: float
    proximity_alerts_count: int
    data_source: DataSource


class SafetyEvent(BaseModel):
    """
    Safety event contract (docs/contracts.md 3) plus optional task_id/history_id.

    The contract does not require task_id/history_id; Module 1 events always
    have them, but a future live event may not.
    """

    event_id: str
    timestamp: datetime
    operator_id: str
    machine_id: str
    task_id: str | None = None
    history_id: str | None = None
    event_type: SafetyEventType
    severity: Severity
    description: str
    data_source: DataSource
