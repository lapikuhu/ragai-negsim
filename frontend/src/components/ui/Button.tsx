import clsx from "clsx";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
};

export function Button({ className, variant = "primary", ...props }: ButtonProps) {
  return (
    <button
      className={clsx(
        "inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition",
        {
          "bg-accent text-white hover:bg-teal-800": variant === "primary",
          "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50": variant === "secondary",
          "text-slate-600 hover:bg-slate-100": variant === "ghost",
          "bg-red-700 text-white hover:bg-red-800": variant === "danger"
        },
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      {...props}
    />
  );
}
