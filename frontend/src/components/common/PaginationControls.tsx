import { Button } from "@/components/ui/Button";
import { buildPaginationItems, clampPage } from "@/utils/pagination";

type PaginationControlsProps = {
  page: number;
  limit: number;
  total: number;
  isBusy?: boolean;
  onPageChange: (page: number) => void;
};

export function PaginationControls({
  page,
  limit,
  total,
  isBusy = false,
  onPageChange
}: PaginationControlsProps) {
  const totalPages = Math.max(1, Math.ceil(total / Math.max(1, limit)));
  const currentPage = clampPage(page, totalPages);
  const items = buildPaginationItems(currentPage, totalPages);

  return (
    <nav className="mt-4 flex flex-wrap items-center justify-center gap-2" aria-label="Pagination">
      <Button
        type="button"
        variant="secondary"
        disabled={currentPage === 1 || isBusy}
        aria-label="Previous page"
        onClick={() => onPageChange(currentPage - 1)}
      >
        {"<"}
      </Button>
      {items.map((item) =>
        typeof item === "number" ? (
          <Button
            key={item}
            type="button"
            variant={item === currentPage ? "primary" : "secondary"}
            disabled={item === currentPage || isBusy}
            aria-label={`Go to page ${item}`}
            aria-current={item === currentPage ? "page" : undefined}
            onClick={() => onPageChange(item)}
          >
            {item}
          </Button>
        ) : (
          <span key={item} className="px-2 text-sm text-slate-500" aria-hidden="true">
            ...
          </span>
        )
      )}
      <Button
        type="button"
        variant="secondary"
        disabled={currentPage === totalPages || isBusy}
        aria-label="Next page"
        onClick={() => onPageChange(currentPage + 1)}
      >
        {">"}
      </Button>
    </nav>
  );
}
