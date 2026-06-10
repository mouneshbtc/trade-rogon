"use client";

import { useState } from "react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DateRangePicker, dateToEndOfDayIso, dateToStartOfDayIso } from "@/components/shared/date-range-picker";
import { InstrumentSelector, type InstrumentSymbol } from "@/components/shared/instrument-selector";
import { MetricCard } from "@/components/shared/metric-card";
import { TimeframeSelector } from "@/components/shared/timeframe-selector";
import {
  getDisplacementEvents,
  getExecutionModelEvaluations,
  getFVGEvents,
  getInstrument,
  getLiquidityPools,
  getLiquidityRaids,
  getSMTEvents,
  getStructuralEvents,
  getTradeSetups,
} from "@/lib/api";
import type { HistogramPoint } from "@/components/chart/histogram-chart";
import type { Timeframe } from "@/types";

const HistogramChart = dynamic(() => import("@/components/chart/histogram-chart").then((m) => m.HistogramChart), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
    </div>
  ),
});

function defaultDates() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { start: fmt(start), end: fmt(end) };
}

function toDay(iso: string): string {
  return iso.slice(0, 10);
}

function groupByDay(timestamps: string[]): HistogramPoint[] {
  const counts = new Map<string, number>();
  for (const ts of timestamps) {
    const day = toDay(ts);
    counts.set(day, (counts.get(day) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([time, value]) => ({ time, value }));
}

export default function StatisticsPage() {
  const [symbol, setSymbol] = useState<InstrumentSymbol>("NQ");
  const [timeframe, setTimeframe] = useState<Timeframe>("15m");
  const initialDates = defaultDates();
  const [startDate, setStartDate] = useState(initialDates.start);
  const [endDate, setEndDate] = useState(initialDates.end);

  const start = dateToStartOfDayIso(startDate);
  const end = dateToEndOfDayIso(endDate);
  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();
  const inRange = (iso: string) => {
    const ms = new Date(iso).getTime();
    return ms >= startMs && ms <= endMs;
  };

  const { data: instrument } = useQuery({
    queryKey: ["instrument", symbol],
    queryFn: () => getInstrument(symbol),
  });

  const { data, isLoading } = useQuery({
    queryKey: ["statistics", instrument?.id, timeframe],
    queryFn: async () => {
      const [structural, pools, raids, displacements, smt, fvgs, evaluations, setups] = await Promise.all([
        getStructuralEvents({ instrument_id: instrument!.id, timeframe }),
        getLiquidityPools({ instrument_id: instrument!.id, timeframe }),
        getLiquidityRaids({ instrument_id: instrument!.id, timeframe }),
        getDisplacementEvents({ instrument_id: instrument!.id, timeframe }),
        getSMTEvents({ timeframe }),
        getFVGEvents({ instrument_id: instrument!.id, timeframe }),
        getExecutionModelEvaluations({ instrument_id: instrument!.id }),
        getTradeSetups({ instrument_id: instrument!.id, timeframe }),
      ]);
      return { structural, pools, raids, displacements, smt, fvgs, evaluations, setups };
    },
    enabled: !!instrument,
  });

  const filtered = data
    ? {
        structural: data.structural.filter((e) => inRange(e.ts)),
        pools: data.pools.filter((e) => inRange(e.ts)),
        raids: data.raids.filter((e) => inRange(e.ts)),
        displacements: data.displacements.filter((e) => inRange(e.ts_start)),
        smt: data.smt.filter(
          (e) => inRange(e.ts) && (e.lead_instrument_id === instrument?.id || e.lag_instrument_id === instrument?.id),
        ),
        fvgs: data.fvgs.filter((e) => inRange(e.ts)),
        evaluations: data.evaluations.filter((e) => inRange(e.candidate_ts)),
        setups: data.setups.filter((e) => inRange(e.created_at)),
      }
    : null;

  const totalMatched = filtered?.evaluations.filter((e) => e.matched).length ?? 0;
  const totalEvaluated = filtered?.evaluations.length ?? 0;
  const qualificationRate = totalEvaluated > 0 ? `${((totalMatched / totalEvaluated) * 100).toFixed(1)}%` : "—";

  const eventsPerDay = filtered
    ? groupByDay([
        ...filtered.structural.map((e) => e.ts),
        ...filtered.pools.map((e) => e.ts),
        ...filtered.raids.map((e) => e.ts),
        ...filtered.displacements.map((e) => e.ts_start),
        ...filtered.smt.map((e) => e.ts),
        ...filtered.fvgs.map((e) => e.ts),
      ])
    : [];

  const setupsPerDay = filtered ? groupByDay(filtered.setups.map((s) => s.created_at)) : [];

  const distribution = filtered
    ? [
        { label: "Structural Events", count: filtered.structural.length },
        { label: "Liquidity Pools", count: filtered.pools.length },
        { label: "Liquidity Raids", count: filtered.raids.length },
        { label: "Displacements", count: filtered.displacements.length },
        { label: "SMT Events", count: filtered.smt.length },
        { label: "FVGs", count: filtered.fvgs.length },
        { label: "Execution Model Evaluations", count: filtered.evaluations.length },
        { label: "Trade Setups", count: filtered.setups.length },
      ]
    : [];

  const maxDistribution = Math.max(1, ...distribution.map((d) => d.count));

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="text-xl font-semibold">Statistics Dashboard</h1>
      <p className="mt-1 text-sm text-muted-foreground">Aggregate counts across the detection pipeline.</p>

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
        </CardContent>
      </Card>

      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <MetricCard label="Structural Events" value={filtered?.structural.length ?? "—"} />
        <MetricCard label="Liquidity Pools" value={filtered?.pools.length ?? "—"} />
        <MetricCard label="Liquidity Raids" value={filtered?.raids.length ?? "—"} />
        <MetricCard label="Displacements" value={filtered?.displacements.length ?? "—"} />
        <MetricCard label="SMT Events" value={filtered?.smt.length ?? "—"} />
        <MetricCard label="FVGs" value={filtered?.fvgs.length ?? "—"} />
        <MetricCard label="Qualified Execution Models" value={totalMatched} />
        <MetricCard label="Generated Trade Setups" value={filtered?.setups.length ?? "—"} />
        <MetricCard label="Qualification Rate" value={qualificationRate} hint={`${totalMatched} / ${totalEvaluated} evaluated`} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Events Per Day</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <HistogramChart data={eventsPerDay} color="#38bdf8" />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Qualified Setups Per Day</CardTitle>
          </CardHeader>
          <CardContent className="h-64">
            <HistogramChart data={setupsPerDay} color="#34d399" />
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Event Distribution</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {distribution.map((d) => (
            <div key={d.label} className="flex items-center gap-3 text-sm">
              <div className="w-48 shrink-0 text-muted-foreground">{d.label}</div>
              <div className="h-2 flex-1 rounded bg-muted">
                <div
                  className="h-2 rounded bg-primary"
                  style={{ width: `${(d.count / maxDistribution) * 100}%` }}
                />
              </div>
              <div className="w-12 shrink-0 text-right tabular-nums">{d.count}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
