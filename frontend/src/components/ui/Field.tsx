import clsx from "clsx";

type FieldProps = {
  label: string;
  hint?: string;
  error?: string;
  className?: string;
  children: React.ReactNode;
};

export function Field({ label, hint, error, className, children }: FieldProps) {
  return (
    <label className={clsx("grid gap-1 text-sm text-slate-700", className)}>
      <span className="font-medium">{label}</span>
      {children}
      {hint ? <span className="text-xs text-slate-500">{hint}</span> : null}
      {error ? <span className="text-xs text-red-700">{error}</span> : null}
    </label>
  );
}

const inputBase =
  "w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm outline-none transition focus:border-accent focus:ring-2 focus:ring-teal-100";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input className={clsx(inputBase, className)} {...props} />;
}

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={clsx(inputBase, "min-h-28", className)} {...props} />;
}

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={clsx(inputBase, className)} {...props} />;
}
