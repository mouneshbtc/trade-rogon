"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { Loader2, ThumbsDown, ThumbsUp, HelpCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { StatusBadge } from "@/components/shared/status-badge";
import { OverlayToggles } from "@/components/chart/overlay-toggles";
import { fetchChartAnnotations } from "@/lib/chart-data";
import { fetchSetupLinkedEvents } from "@/lib/setup-detail";
import { getBars, getInstrument, getTradeSetup } from "@/lib/api";
import { cn, formatPrice, formatTimestamp } from "@/lib/utils";
import { useChartStore } from "@/store/chart-store";
import type { SetupFeedbackVerdict } from "@/types";

const TradingChart = dynamic(() => import("@/components/chart/trading-chart").then((m) => m.TradingChart), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center text-sm text-muted-foreground">
      <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading chart…
    </div>
  ),
});

const FEEDBACK_KEY_PREFIX = "trade-rogon:setup-feedback:";

function readFeedback(setupId: string): SetupFeedbackVerdict | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(`${FEEDBACK_KEY_PREFIX}${setupId}`);
  return raw === "yes" || raw === "no" || raw === "unsure" ? raw : null;
}

function writeFeedback(setupId: string, verdict: SetupFeedbackVerdict) {
  window.localStorage.setItem(`${FEEDBACK_KEY_PREFIX}${setupId}`, verdict);
}

export default function SetupDetailPage() {
  const params = useParams<{ id: string }>();
  const setupId = params.id;

  const overlays = useChartStore((s) => s.overlays);
  const selectedAnnotation = useChartStore((s) => s.selectedAnnotation);
  const setSelectedAnnotation = useChartStore((s) => s.setSelectedAnnotation);
  const jumpToTs = useChartStore((s) => s.jumpToTs);
  const requestJumpTo = useChartStore((s) => s.requestJumpTo);
  const clearJumpTo = useChartStore((s) => s.clearJumpTo);

  const [feedback, setFeedback] = useState<SetupFeedbackVerdict | null>(null);

  const { data: setup, isLoading } = useQuery({
    queryKey: ["trade-setup", setupId],
    queryFn: () => getTradeSetup(setupId),
  });

  const { data: nq } = useQuery({ queryKey: ["instrument", "NQ.c.0"], queryFn: () => getInstrument("NQ.c.0") });
  const { data: es } = useQuery({ queryKey: ["instrument", "ES.c.0"], queryFn: () => getInstrument("ES.c.0") });

  const symbol = setup ? (nq?.id === setup.instrument_id ? "NQ.c.0" : es?.id === setup.instrument_id ? "ES.c.0" : null) : null;
  const timeframe = (setup?.timeframe ?? "15m") as import("@/types").Timeframe;

  const window_ = setup
    ? (() => {
        const center = new Date(setup.created_at);
        const start = new Date(center);
        start.setDate(start.getDate() - 5);
        const end = new Date(center);
        end.setDate(end.getDate() + 5);
        return { start: start.toISOString(), end: end.toISOString() };
      })()
    : null;

  const { data: barData } = useQuery({
    queryKey: ["setup-bars", symbol, timeframe, window_?.start, window_?.end],
    queryFn: () => getBars(symbol!, { timeframe, start: window_!.start, end: window_!.end }),
    enabled: !!symbol && !!window_,
  });

  const { data: annotations } = useQuery({
    queryKey: ["chart-annotations", setup?.instrument_id, timeframe],
    queryFn: () => fetchChartAnnotations({ instrumentId: setup!.instrument_id, timeframe }),
    enabled: !!setup,
  });

  const { data: linked, isLoading: linkedLoading } = useQuery({
    queryKey: ["setup-linked", setup?.id],
    queryFn: () => fetchSetupLinkedEvents(setup!, timeframe),
    enabled: !!setup,
  });

  useEffect(() => {
    if (setup) {
      setFeedback(readFeedback(setup.id));
      requestJumpTo(setup.created_at);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [setup?.id]);

  function submitFeedback(verdict: SetupFeedbackVerdict) {
    if (!setup) return;
    writeFeedback(setup.id, verdict);
    setFeedback(verdict);
  }

  if (isLoading || !setup) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading setup…
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col p-6">
      <div className="flex items-center gap-2">
        <h1 className="text-xl font-semibold">Setup {setup.id.slice(0, 8)}</h1>
        <StatusBadge status={setup.direction} />
        <StatusBadge status={setup.status} />
      </div>
      <p className="mt-1 text-sm text-muted-foreground">{formatTimestamp(setup.created_at)}</p>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Setup Details</CardTitle>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
            <Field label="Entry" value={formatPrice(setup.entry_price)} />
            <Field label="Stop" value={formatPrice(setup.stop_price)} />
            <Field label="Target" value={formatPrice(setup.target_price)} />
            <Field label="Risk (pts)" value={formatPrice(setup.risk_points)} />
            <Field label="Reward (pts)" value={formatPrice(setup.reward_points)} />
            <Field label="R:R" value={formatPrice(setup.rr_ratio)} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Linked Events</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-1 text-sm">
            {linkedLoading ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /> : null}
            <LinkedRow label="Liquidity Raid" id={linked?.raid?.id} ts={linked?.raid?.ts} />
            <LinkedRow label="SMT Divergence" id={linked?.smt?.id} ts={linked?.smt?.ts} />
            <LinkedRow label="Displacement" id={linked?.displacement?.id} ts={linked?.displacement?.ts_start} />
            <LinkedRow label="FVG" id={linked?.fvg?.id} ts={linked?.fvg?.ts} />
            <LinkedRow label="Execution Model Eval" id={linked?.evaluation?.id} ts={linked?.evaluation?.candidate_ts} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Research Controls</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-2 text-sm text-muted-foreground">Would you take this trade?</div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant={feedback === "yes" ? "default" : "outline"}
                onClick={() => submitFeedback("yes")}
              >
                <ThumbsUp className="h-4 w-4" /> Yes
              </Button>
              <Button
                size="sm"
                variant={feedback === "no" ? "default" : "outline"}
                onClick={() => submitFeedback("no")}
              >
                <ThumbsDown className="h-4 w-4" /> No
              </Button>
              <Button
                size="sm"
                variant={feedback === "unsure" ? "default" : "outline"}
                onClick={() => submitFeedback("unsure")}
              >
                <HelpCircle className="h-4 w-4" /> Unsure
              </Button>
            </div>
            {feedback ? <div className="mt-2 text-xs text-muted-foreground">Stored locally as: {feedback}</div> : null}
          </CardContent>
        </Card>
      </div>

      <Card className="mt-4 min-h-0 flex-1">
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Chart</CardTitle>
          <OverlayToggles />
        </CardHeader>
        <CardContent className="h-full p-2">
          <div className="h-full min-h-[420px] w-full">
            {symbol ? (
              <TradingChart
                bars={barData?.items ?? []}
                annotations={annotations ?? []}
                overlays={overlays}
                onAnnotationClick={setSelectedAnnotation}
                jumpToTs={jumpToTs}
                onJumpHandled={clearJumpTo}
                barWidthSeconds={900}
              />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Resolving instrument…
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {selectedAnnotation ? (
        <Card className="mt-4">
          <CardHeader>
            <CardTitle>{selectedAnnotation.eventType}</CardTitle>
          </CardHeader>
          <CardContent>
            <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-3 text-xs leading-relaxed">
              {JSON.stringify(selectedAnnotation.raw, null, 2)}
            </pre>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <>
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right tabular-nums">{value}</span>
    </>
  );
}

function LinkedRow({ label, id, ts }: { label: string; id?: string | null; ts?: string }) {
  return (
    <div className="flex items-center justify-between border-b border-border/50 py-1 last:border-0">
      <span className="text-muted-foreground">{label}</span>
      {id ? (
        <span className="flex items-center gap-2">
          <span className="font-mono text-xs">{id.slice(0, 8)}</span>
          {ts ? <span className="text-xs text-muted-foreground">{formatTimestamp(ts)}</span> : null}
        </span>
      ) : (
        <span className={cn("text-xs text-muted-foreground")}>—</span>
      )}
    </div>
  );
}
