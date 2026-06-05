export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "Not available";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value));
}

export function stringifyJson(value: unknown) {
  return JSON.stringify(value ?? {}, null, 2);
}

export function parseJsonInput<T>(value: string, fallback: T) {
  const trimmed = value.trim();
  if (!trimmed) {
    return fallback;
  }
  return JSON.parse(trimmed) as T;
}

export function toSentenceCase(value: string) {
  return value.replaceAll("-", " ").replaceAll("_", " ");
}
