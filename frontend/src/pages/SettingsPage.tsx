import { PageHeader } from "@/components/common/PageHeader";
import { Card } from "@/components/ui/Card";

export function SettingsPage() {
  return (
    <div className="grid gap-6">
      <PageHeader
        title="Settings"
        description="Only schema-backed settings are actionable. Unsupported global settings are intentionally documented rather than invented."
      />

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Available today</h2>
        <ul className="mt-4 grid gap-2 text-sm text-slate-700">
          <li>Authentication state and logout.</li>
          <li>Prompt, persona, and scenario configuration via existing routes.</li>
          <li>Vector store and chunking profile inspection via current admin APIs.</li>
        </ul>
      </Card>

      <Card>
        <h2 className="text-lg font-semibold text-slate-950">Disabled until backend support exists</h2>
        <ul className="mt-4 grid gap-2 text-sm text-slate-700">
          <li>Global provider settings UI.</li>
          <li>User preference persistence beyond auth.</li>
          <li>Dedicated evaluation configuration and polling dashboards.</li>
        </ul>
      </Card>
    </div>
  );
}
