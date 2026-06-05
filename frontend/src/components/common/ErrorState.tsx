import { Button } from "@/components/ui/Button";

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="grid gap-3 rounded-2xl border border-red-200 bg-red-50 p-5 text-sm text-red-900">
      <div>
        <h3 className="font-semibold">{title}</h3>
        <p className="mt-1 text-red-800">{message}</p>
      </div>
      {onRetry ? (
        <div>
          <Button type="button" variant="secondary" onClick={onRetry}>
            Retry
          </Button>
        </div>
      ) : null}
    </div>
  );
}
