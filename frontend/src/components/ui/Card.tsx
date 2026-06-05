import clsx from "clsx";

export function Card({
  className,
  children
}: {
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={clsx("rounded-2xl border border-white/70 bg-white/90 p-5 shadow-panel", className)}>
      {children}
    </section>
  );
}
