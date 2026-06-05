import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";

export function QueuedJobNotice({
  title,
  description,
  onAction,
  actionLabel
}: {
  title: string;
  description: string;
  actionLabel: string;
  onAction?: () => void;
}) {
  return (
    <Card className="border-amber-200 bg-amber-50/80">
      <div className="grid gap-3">
        <div>
          <h3 className="font-semibold text-amber-950">{title}</h3>
          <p className="mt-1 text-sm text-amber-800">{description}</p>
        </div>
        {onAction ? (
          <div>
            <Button type="button" variant="secondary" onClick={onAction}>
              {actionLabel}
            </Button>
          </div>
        ) : null}
      </div>
    </Card>
  );
}
