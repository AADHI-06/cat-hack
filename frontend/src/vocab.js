// Value lists from docs/synthetic_data.md, used for filter dropdowns.
// The backend validates these too and rejects anything else.

export const TASK_STATUSES = ["PENDING", "IN_PROGRESS", "COMPLETED", "BLOCKED"];
export const PRIORITIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];
export const ZONES = ["ZONE_A", "ZONE_B", "ZONE_C", "ZONE_D"];
export const MACHINE_TYPES = ["EXCAVATOR", "DOZER", "LOADER", "HAUL_TRUCK", "GRADER"];
export const SEVERITIES = ["HIGH", "MEDIUM", "LOW"];
export const SAFETY_EVENT_TYPES = ["SEATBELT", "PROXIMITY", "EXCESSIVE_IDLING", "OVERSPEED", "UNCERTIFIED_OPERATION"];
