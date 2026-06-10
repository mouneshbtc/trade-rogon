"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { DateRangePicker, dateToEndOfDayIso, dateToStartOfDayIso } from "@/components/shared/date-range-picker";
import { EventDrawer } from "@/components/shared/event-drawer";
import { InstrumentSelector, type InstrumentSymbol } from "@/components/shared/instrument-selector";
import { StatusBadge } from "@/components/shared/status-badge";
import { TimeframeSelector } from "@/components/shared/timeframe-selector";
import { EVENT_TYPE_OPTIONS, fetchEventRows } from "@/lib/event-explorer";
import { getInstrument } from "@/lib/api";
import { formatPrice, formatTimestamp } from "@/lib/utils";
import type { EventExplorerRow, EventExplorerType, Timeframe } from "@/types";

function defaultDates() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { start: fmt(start), end: fmt(end) };
}

export default function EventsPage() {
  const [symbol, setSymbol] = useState<InstrumentSymbol>("NQ.c.0");
  const [timeframe, setTimeframe] = useState<Timeframe>("15m");
  const [eventType, setEventType] = useState<EventExplorerType | "all">("all");
  const initialDates = defaultDates();
  const [startDate, setStartDate] = useState(initialDates.start);
  const [endDate, setEndDate] = useState(initialDates.end);
  const [selectedRow, setSelectedRow] = useState<EventExplorerRow | null>(null);

  const start = dateToStartOfDayIso(startDate);
  const end = dateToEndOfDayIso(endDate);

  const { data: instrument } = useQuery({
    queryKey: ["instrument", symbol],
    queryFn: () => getInstrument(symbol),
  });

  const {
    data: rows,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["event-explorer", instrument?.id, timeframe, eventType, start, end],
    queryFn: () =>
      fetchEventRows({
        instrumentId: instrument!.id,
        timeframe,
        eventType,
        start,
        end,
      }),
    enabled: !!instrument,
  });

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-xl font-semibold">Event Explorer</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Query every detected event across the pipeline. Click View for the full raw payload.
      </p>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Instrument</label>
            <InstrumentSelector value={symbol} onChange={setSymbol} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Timeframe</label>
            <TimeframeSelector value={timeframe} onChange={setTimeframe} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Event Type</label>
            <Select value={eventType} onValueChange={(v) => setEventType(v as EventExplorerType | "all")}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EVENT_TYPE_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-2">
            <DateRangePicker start={startDate} end={endDate} onStartChange={setStartDate} onEndChange={setEndDate} />
          </div>
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Results {rows ? `(${rows.length})` : ""}</CardTitle>
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /> : null}
        </CardHeader>
        <CardContent>
          {error ? <div className="text-sm text-bearish">{(error as Error).message}</div> : null}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Timestamp</TableHead>
                <TableHead>Event Type</TableHead>
                <TableHead>Direction</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Price</TableHead>
                <TableHead>Instrument</TableHead>
                <TableHead>Timeframe</TableHead>
                <TableHead />
              </TableRow>
            </TableHeader>
            <TableBody>
              {(rows ?? []).map((row) => (
                <TableRow key={`${row.event_type}-${row.id}`}>
                  <TableCell className="whitespace-nowrap">{formatTimestamp(row.ts)}</TableCell>
                  <TableCell className="whitespace-nowrap">{row.event_type}</TableCell>
                  <TableCell>
                    <StatusBadge status={row.direction} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={row.status} />
                  </TableCell>
                  <TableCell className="tabular-nums">{row.price ? formatPrice(row.price) : "—"}</TableCell>
                  <TableCell className="font-mono text-xs">{symbol}</TableCell>
                  <TableCell>{row.timeframe}</TableCell>
                  <TableCell>
                    <Button size="sm" variant="outline" onClick={() => setSelectedRow(row)}>
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {!isLoading && (rows ?? []).length === 0 ? (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-sm text-muted-foreground">
                    No events found for this filter combination.
                  </TableCell>
                </TableRow>
              ) : null}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <EventDrawer row={selectedRow} onOpenChange={(open) => !open && setSelectedRow(null)} />
    </div>
  );
}
