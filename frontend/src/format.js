// Display formatting only. No business rules.

// "EXCESSIVE_IDLING" -> "Excessive idling", "ZONE_B" -> "Zone B"
export function label(code) {
  if (!code) return "";
  const words = code.split("_").map((word) => (word.length === 1 ? word : word.toLowerCase()));
  const text = words.join(" ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function minutes(value) {
  if (value === null || value === undefined) return "-";
  const total = Math.round(value);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${m}m`;
}

export function dateTime(value) {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

export function number(value, digits = 0) {
  if (value === null || value === undefined) return "-";
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

export function percent(ratio) {
  if (ratio === null || ratio === undefined) return "-";
  return `${Math.round(ratio * 100)}%`;
}
