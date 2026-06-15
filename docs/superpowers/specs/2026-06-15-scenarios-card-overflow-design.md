# Scenarios Card Overflow Design

## Goal

Prevent the scenarios dashboard from introducing horizontal page scrolling when scenario cards contain long or dense context JSON.

## Current Problem

The scenario list in `frontend/src/pages/ScenariosPage.tsx` renders the public context preview in a `pre` block with horizontal overflow enabled. Long JSON lines or unbroken values can expand the visible card content and force the dashboard into awkward sideways scrolling.

## Chosen Approach

Use fixed-height, internally scrollable context preview regions inside each scenario card.

This keeps every card within the available dashboard width while preserving direct access to the context JSON. Users can still inspect the content, but scrolling happens inside the card rather than across the full page.

## UI Design

### Card containment

- Scenario cards must remain within the width of the page container.
- No scenario card should trigger page-level horizontal scrolling.
- The main card content column must be allowed to shrink safely within the existing flex layout.

### Context preview behavior

- The JSON preview area should use a fixed maximum height equivalent to about 12 lines of text.
- Overflow should scroll vertically inside the preview region.
- Horizontal overflow should be suppressed by wrapping long tokens rather than preserving wide unbroken lines.
- The preview should keep the existing monospace, panel-like visual treatment so it still reads as raw JSON.

### Scope

- Apply this behavior to the scenario card preview content shown in the dashboard list.
- Do not change the create or edit form textareas as part of this fix.
- Do not introduce expand/collapse controls or summary rendering in this change.

## Implementation Notes

- Extracting a small reusable preview helper inside `ScenariosPage.tsx` is acceptable if it keeps the layout rules clear.
- Tailwind classes should express:
  - width containment
  - fixed preview height
  - vertical scrolling
  - line wrapping for long JSON content

## Testing

- Add or update a page test for `ScenariosPage` that renders a scenario with long context content.
- Assert that the scenario still renders correctly and that the context preview uses the new contained preview region.
- Keep the test focused on structure and applied behavior markers rather than browser-specific scroll measurements.

## Risks

- Wrapping raw JSON can make some lines visually taller than before, but this is acceptable because the fixed-height scroll region preserves access to the full content.
- If the preview area is too short, readability could suffer; the 12-line target is the intended balance for this change.
