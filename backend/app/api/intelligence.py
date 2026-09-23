"""
Availability of capabilities the platform consumes but does not own.

This is the single integration seam for Claude A's services. Everything is
unavailable until the owning module is approved and wired in during
integration; the platform never substitutes its own estimate.
"""

from app.models.dashboard import ServiceStatus

_SERVICES = [
    ("task_prediction", "Task duration prediction", 2, "Prediction unavailable - waiting for prediction service"),
    ("optimization", "Shift task optimization", 3, "No shift plan yet - waiting for optimization service"),
    ("safety_intelligence", "Live safety monitoring", 4, "Live safety status unavailable - waiting for safety service"),
    ("anomaly_detection", "Machine anomaly detection", 5, "Anomaly status unavailable - waiting for anomaly service"),
    ("incidents", "Incident management", 6, "Incident records are defined in Module 6"),
    ("training", "Operator training hub", 7, "Training content is added in Module 7"),
]


def service_statuses() -> list[ServiceStatus]:
    return [
        ServiceStatus(key=key, name=name, module=module, available=False, message=message)
        for key, name, module, message in _SERVICES
    ]
