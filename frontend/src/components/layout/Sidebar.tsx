import clsx from "clsx";
import { NavLink } from "react-router-dom";
import { navigationItems } from "@/components/layout/nav";
import { useAuth } from "@/app/AuthProvider";

export function Sidebar() {
  const auth = useAuth();

  return (
    <aside className="flex h-full flex-col gap-6 rounded-3xl bg-slate-950 px-4 py-5 text-slate-100">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Negotiation Simulator</p>
        <h1 className="mt-2 text-lg font-semibold">Operational Console</h1>
      </div>

      <nav className="grid gap-1">
        {navigationItems.map((item) => {
          const isAllowed = !item.roles?.length || auth.hasRole(...item.roles);
          const disabled = item.disabled || !isAllowed;

          if (disabled) {
            return (
              <div key={item.to} className="rounded-2xl border border-slate-800 px-3 py-2 text-slate-500">
                <div className="text-sm font-medium">{item.label}</div>
                <div className="mt-1 text-xs">{isAllowed ? item.description : "Role restricted"}</div>
              </div>
            );
          }

          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx("rounded-2xl px-3 py-2 transition", {
                  "bg-white text-slate-950": isActive,
                  "text-slate-300 hover:bg-slate-900 hover:text-white": !isActive
                })
              }
            >
              <div className="text-sm font-medium">{item.label}</div>
              <div className="mt-1 text-xs opacity-80">{item.description}</div>
            </NavLink>
          );
        })}
      </nav>
    </aside>
  );
}
