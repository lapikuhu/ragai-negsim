export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="flex min-h-40 items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/70 p-6 text-sm text-slate-600">
      {label}
    </div>
  );
}
