import clsx from "clsx";

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const value = status ?? "unknown";
  return (
    <span
      className={clsx(
        "inline-flex rounded-full px-2.5 py-1 text-xs font-medium capitalize",
        {
          "bg-slate-100 text-slate-700": ["created", "unknown"].includes(value),
          "bg-teal-100 text-teal-800": ["active", "built", "completed", "available", "running"].includes(value),
          "bg-amber-100 text-amber-800": ["paused", "building", "changed", "unverified", "queued"].includes(value),
          "bg-red-100 text-red-800": ["failed", "cancelled", "missing", "error"].includes(value)
        }
      )}
    >
      {value.replaceAll("_", " ")}
    </span>
  );
}
