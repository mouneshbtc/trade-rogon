"use client";

import { useState } from "react";
import { Check, Loader2, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { DateRangePicker, dateToEndOfDayIso, dateToStartOfDayIso } from "@/components/shared/date-range-picker";
import { InstrumentSelector, type InstrumentSymbol } from "@/components/shared/instrument-selector";
import { TimeframeSelector } from "@/components/shared/timeframe-selector";
import { cn } from "@/lib/utils";
import {
  detectDisplacement,
  detectFVG,
  detectLiquidity,
  detectMarketStructure,
  detectSMT,
  evaluateExecutionModel,
  getInstrument,
  getTradeSetups,
} from "@/lib/api";
import { PIPELINE_STAGES, usePipelineStore } from "@/store/pipeline-store";
import type { PipelineStageKey, Timeframe } from "@/types";

function defaultDates() {
  const end = new Date();
  const start = new Date();
  start.setDate(start.getDate() - 30);
  const fmt = (d: Date) => d.toISOString().slice(0, 10);
  return { start: fmt(start), end: fmt(end) };
}

export default function PipelinePage() {
  const [symbol, setSymbol] = useState<InstrumentSymbol>("NQ.c.0");
  const [timeframe, setTimeframe] = useState<Timeframe>("15m");
  const initialDates = defaultDates();
  const [startDate, setStartDate] = useState(initialDates.start);
  const [endDate, setEndDate] = useState(initialDates.end);

  const stages = usePipelineStore((s) => s.stages);
  const isRunning = usePipelineStore((s) => s.isRunning);
  const lastRun = usePipelineStore((s) => s.lastRun);
  const resetStages = usePipelineStore((s) => s.resetStages);
  const setStage = usePipelineStore((s) => s.setStage);
  const setRunning = usePipelineStore((s) => s.setRunning);
  const saveLastRun = usePipelineStore((s) => s.saveLastRun);

  async function runPipeline() {
    resetStages();
    setRunning(true);

    const start = dateToStartOfDayIso(startDate);
    const end = dateToEndOfDayIso(endDate);

    const run = async (key: PipelineStageKey, fn: () => Promise<{ count: number; label: string }>) => {
      setStage(key, { status: "running" });
      try {
        const { count, label } = await fn();
        setStage(key, { status: "done", count, countLabel: label });
        return true;
      } catch (err) {
        setStage(key, { status: "error", error: err instanceof Error ? err.message : String(err) });
        return false;
      }
    };

    try {
      const instrument = await getInstrument(symbol);
      const instrumentId = instrument.id;

      let ok = await run("market_structure", async () => {
        const res = await detectMarketStructure({ instrument_id: instrumentId, timeframe, start, end });
        return { count: res.events_detected, label: `${res.events_detected} events` };
      });
      if (!ok) return;

      ok = await run("liquidity", async () => {
        const res = await detectLiquidity({ instrument_id: instrumentId, timeframe, start, end });
        return { count: res.raids_detected, label: `${res.raids_detected} raids` };
      });
      if (!ok) return;

      ok = await run("displacement", async () => {
        const res = await detectDisplacement({ instrument_id: instrumentId, timeframe, start, end });
        const total = Object.values(res.events_created).reduce((a, b) => a + b, 0);
        return { count: total, label: `${total} events` };
      });
      if (!ok) return;

      ok = await run("smt", async () => {
        const res = await detectSMT({ timeframe, start, end });
        const total = Object.values(res.events_created).reduce((a, b) => a + b, 0);
        return { count: total, label: `${total} divergences` };
      });
      if (!ok) return;

      ok = await run("fvg", async () => {
        const res = await detectFVG({ instrument_id: instrumentId, timeframe, start, end });
        const total = Object.values(res.events_created).reduce((a, b) => a + b, 0);
        return { count: total, label: `${total} gaps` };
      });
      if (!ok) return;

      ok = await run("execution_model", async () => {
        const res = await evaluateExecutionModel({ instrument_id: instrumentId, start, end });
        return { count: res.total_matched, label: `${res.total_matched} qualified` };
      });
      if (!ok) return;

      await run("trade_setup", async () => {
        const setups = await getTradeSetups({ instrument_id: instrumentId, timeframe });
        return { count: setups.length, label: `${setups.length} generated` };
      });
    } finally {
      setRunning(false);
      saveLastRun({
        symbol,
        timeframe,
        start,
        end,
        finishedAt: new Date().toISOString(),
        stages: usePipelineStore.getState().stages,
      });
    }
  }

  return (
    <div className="mx-auto max-w-4xl p-6">
      <h1 className="text-xl font-semibold">Pipeline Runner</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Run the full detection pipeline for a single instrument over a date range, stage by stage.
      </p>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Run Configuration</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Instrument</label>
              <InstrumentSelector value={symbol} onChange={setSymbol} />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Timeframe</label>
              <TimeframeSelector value={timeframe} onChange={setTimeframe} />
            </div>
            <div className="col-span-2">
              <DateRangePicker start={startDate} end={endDate} onStartChange={setStartDate} onEndChange={setEndDate} />
            </div>
          </div>
          <div>
            <Button onClick={runPipeline} disabled={isRunning}>
              {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Run Pipeline
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="mt-4">
        <CardHeader>
          <CardTitle>Stage Progress</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {PIPELINE_STAGES.map((meta, i) => {
            const stage = stages.find((s) => s.key === meta.key);
            return (
              <div key={meta.key}>
                {i > 0 ? <Separator className="my-2" /> : null}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <StageIcon status={stage?.status ?? "idle"} />
                    <span className="text-sm font-medium">{meta.label}</span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {stage?.status === "done" && stage.countLabel}
                    {stage?.status === "error" && (
                      <span className="text-bearish">{stage.error}</span>
                    )}
                    {stage?.status === "running" && "running…"}
                    {stage?.status === "idle" && "—"}
                  </div>
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>

      {lastRun ? (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>Last Run</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">
            <div>
              {lastRun.symbol} · {lastRun.timeframe} · {lastRun.start.slice(0, 10)} → {lastRun.end.slice(0, 10)}
            </div>
            <div className="mt-1">Finished: {new Date(lastRun.finishedAt).toLocaleString()}</div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function StageIcon({ status }: { status: "idle" | "running" | "done" | "error" }) {
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
  if (status === "done") return <Check className="h-4 w-4 text-bullish" />;
  if (status === "error") return <X className="h-4 w-4 text-bearish" />;
  return <div className={cn("h-4 w-4 rounded-full border border-muted-foreground/40")} />;
}
