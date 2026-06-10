"use client";

import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { StatusBadge } from "@/components/shared/status-badge";
import type { EventExplorerRow } from "@/types";
import { formatTimestamp } from "@/lib/utils";

interface EventDrawerProps {
  row: EventExplorerRow | null;
  onOpenChange: (open: boolean) => void;
}

export function EventDrawer({ row, onOpenChange }: EventDrawerProps) {
  return (
    <Sheet open={row !== null} onOpenChange={onOpenChange}>
      <SheetContent side="right">
        {row ? (
          <>
            <SheetHeader>
              <SheetTitle className="flex items-center gap-2">
                {row.event_type}
                <StatusBadge status={row.status} />
              </SheetTitle>
              <SheetDescription>{formatTimestamp(row.ts)}</SheetDescription>
            </SheetHeader>
            <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
              <div className="text-muted-foreground">Direction</div>
              <div>{row.direction ?? "—"}</div>
              <div className="text-muted-foreground">Price</div>
              <div className="tabular-nums">{row.price ?? "—"}</div>
              <div className="text-muted-foreground">Timeframe</div>
              <div>{row.timeframe}</div>
              <div className="text-muted-foreground">Instrument</div>
              <div className="font-mono text-xs">{row.instrument_id ?? "—"}</div>
            </div>
            <div className="mt-4">
              <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Raw Payload
              </div>
              <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-3 text-xs leading-relaxed">
                {JSON.stringify(row.raw, null, 2)}
              </pre>
            </div>
          </>
        ) : null}
      </SheetContent>
    </Sheet>
  );
}
