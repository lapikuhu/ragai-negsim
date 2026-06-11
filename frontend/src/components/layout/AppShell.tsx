import { Outlet } from "react-router-dom";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";

export function AppShell() {
  return (
    <div className="min-h-screen p-4 md:p-6">
      <div className="mx-auto grid max-w-[1600px] gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
        <Sidebar />
        <div className="grid content-start gap-4">
          <Topbar />
          <main className="grid gap-6 rounded-3xl border border-white/70 bg-white/35 p-4 backdrop-blur md:p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  );
}
