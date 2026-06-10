"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker, dateToEndOfDayIso, dateToStartOfDayIso } from "@/components/shared/date-range-picker";
import { InstrumentSelector, type InstrumentSymbol } from "@/components/shared/instrument-selector";
import { StatusBadge } from "@/components/shared/status-badge";
import { TimeframeSelector } from "@/components/shared/timeframe-selector";
import { OverlayToggles } from "@/components/chart/overlay-toggles";
import { fetchChartAnnotations } from "@/lib/chart-data";
import { getBars, getInstrument } from "@/lib/api";
import { formatTimestamp } from "@/lib/utils";
import { useChartStore } from "@/store/chart-store";
import type { Timeframe } from "@/types";

const TradingChart = dynamic(() => import("@/components/chart/trading-chart").then((m) => m.TradingChart), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading chart…
    </div>
  ),
});

const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  "1m": 60,
  "5m": 300,
  "15m": 900,
  "1h": 3600,
  "4h": 14400,
  "1d": 86400,
  "1w": 604800,
};

function defaultDates() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 14);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { start: fmt(start), end: fmt(end) };
}

export default function ChartPage() {
  const [symbol, setSymbol] = useState<InstrumentSymbol>("NQ");
  const [timeframe, setTimeframe] = useState<Timeframe>("15m");
  const initialDates = defaultDates();
  const [startDate, setStartDate] = useState(initialDates.start);
  const [endDate, setEndDate] = useState(initialDates.end);

  const overlays = useChartStore((s) => s.overlays);
  const selectedAnnotation = useChartStore((s) => s.selectedAnnotation);
  const setSelectedAnnotation = useChartStore((s) => s.setSelectedAnnotation);
  const jumpToTs = useChartStore((s) => s.jumpToTs);
  const requestJumpTo = useChartStore((s) => s.requestJumpTo);
  const clearJumpTo = useChartStore((s) => s.clearJumpTo);

  const start = dateToStartOfDayIso(startDate);
  const end = dateToEndOfDayIso(endDate);

  const { data: instrument } = useQuery({
    queryKey: ["instrument", symbol],
    queryFn: () => getInstrument(symbol),
  });

  const { data: barData, isLoading: barsLoading } = useQuery({
    queryKey: ["bars", symbol, timeframe, start, end],
    queryFn: () => getBars(symbol, { timeframe, start, end }),
  });

  const { data: annotations, isLoading: annotationsLoading } = useQuery({
    queryKey: ["chart-annotations", instrument?.id, timeframe],
    queryFn: () => fetchChartAnnotations({ instrumentId: instrument!.id, timeframe }),
    enabled: !!instrument,
  });

  const bars = barData?.items ?? [];
  const isLoading = barsLoading || annotationsLoading;

  return (
    <div className="flex h-full flex-col p-6">
      <h1 className="text-xl font-semibold">Chart Review</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Candlesticks with toggleable detection overlays. Click a marker to inspect its reasoning.
      </p>

      <Card className="mt-4">
        <CardContent className="flex flex-wrap items-end gap-4 pt-4">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Instrument</label>
            <InstrumentSelector value={symbol} onChange={setSymbol} className="w-24" />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Timeframe</label>
            <TimeframeSelector value={timeframe} onChange={setTimeframe} className="w-24" />
          </div>
          <DateRangePicker start={startDate} end={endDate} onStartChange={setStartDate} onEndChange={setEndDate} />
          {isLoading ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /> : null}
          <div className="ml-auto">
            <OverlayToggles />
          </div>
        </CardContent>
      </Card>

      <div className="mt-4 flex min-h-0 flex-1 gap-4">
        <Card className="min-h-0 flex-1">
          <CardContent className="h-full p-2">
            <div className="h-full min-h-[480px] w-full">
              <TradingChart
                bars={bars}
                annotations={annotations ?? []}
                overlays={overlays}
                onAnnotationClick={setSelectedAnnotation}
                jumpToTs={jumpToTs}
                onJumpHandled={clearJumpTo}
                barWidthSeconds={TIMEFRAME_SECONDS[timeframe]}
              />
            </div>
          </CardContent>
        </Card>

        <Card className="w-80 shrink-0 overflow-y-auto">
          <CardHeader>
            <CardTitle>Inspector</CardTitle>
          </CardHeader>
          <CardContent>
            {selectedAnnotation ? (
              <AnnotationDetail
                annotation={selectedAnnotation}
                onCenter={() => requestJumpTo(selectedAnnotation.ts)}
              />
            ) : (
              <EventJumpList annotations={annotations ?? []} onJump={requestJumpTo} onSelect={setSelectedAnnotation} />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function AnnotationDetail({
  annotation,
  onCenter,
}: {
  annotation: import("@/types").ChartAnnotation;
  onCenter: () => void;
}) {
  return (
    <div className="flex flex-col gap-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-medium">{annotation.eventType}</span>
        <StatusBadge status={annotation.status} />
      </div>
      <div className="text-xs text-muted-foreground">{formatTimestamp(annotation.ts)}</div>
      {annotation.direction ? (
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">Direction</span>
          <StatusBadge status={annotation.direction} />
        </div>
      ) : null}

      <Button size="sm" variant="secondary" onClick={onCenter}>
        Center On Event
      </Button>

      <Separator />

      <div>
        <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Reasoning Fields</div>
        <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
          {Object.entries(annotation.reasoningFields).map(([key, value]) => (
            <FragmentRow key={key} label={key} value={value} />
          ))}
        </div>
      </div>

      {Object.values(annotation.referencedIds).some(Boolean) ? (
        <div>
          <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Referenced IDs</div>
          <div className="grid grid-cols-1 gap-1 text-xs">
            {Object.entries(annotation.referencedIds)
              .filter(([, v]) => v)
              .map(([key, value]) => (
                <div key={key} className="flex justify-between gap-2">
                  <span className="text-muted-foreground">{key}</span>
                  <span className="truncate font-mono">{value}</span>
                </div>
              ))}
          </div>
        </div>
      ) : null}

      <div>
        <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Raw Data</div>
        <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-2 text-xs leading-relaxed">
          {JSON.stringify(annotation.raw, null, 2)}
        </pre>
      </div>
    </div>
  );
}

function FragmentRow({ label, value }: { label: string; value: string | number | boolean | null }) {
  return (
    <>
      <span className="text-muted-foreground">{label}</span>
      <span className="truncate text-right tabular-nums">{value === null ? "—" : String(value)}</span>
    </>
  );
}

function EventJumpList({
  annotations,
  onJump,
  onSelect,
}: {
  annotations: import("@/types").ChartAnnotation[];
  onJump: (ts: string) => void;
  onSelect: (a: import("@/types").ChartAnnotation) => void;
}) {
  const sorted = [...annotations].sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime()).slice(0, 50);

  return (
    <div className="flex flex-col gap-2">
      <div className="text-xs text-muted-foreground">
        Click a marker on the chart, or pick a recent event to jump to.
      </div>
      <Select onValueChange={(id) => {
        const a = sorted.find((x) => x.id === id);
        if (a) {
          onSelect(a);
          onJump(a.ts);
        }
      }}>
        <SelectTrigger>
          <SelectValue placeholder="Jump to event…" />
        </SelectTrigger>
        <SelectContent>
          {sorted.map((a) => (
            <SelectItem key={a.id} value={a.id}>
              {a.eventType} · {formatTimestamp(a.ts)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
