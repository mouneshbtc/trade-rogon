"use client";

import { useEffect, useRef } from "react";
import {
  ColorType,
  CrosshairMode,
  LineStyle,
  createChart,
  type CandlestickData,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type SeriesMarker,
  type Time,
} from "lightweight-charts";

import type { Bar, ChartAnnotation } from "@/types";
import type { OverlayToggles } from "@/store/chart-store";
import { toUnixSeconds } from "@/lib/utils";

const OVERLAY_COLORS: Record<ChartAnnotation["kind"], string> = {
  liquidity_pool: "#eab308",
  liquidity_raid: "#f97316",
  displacement: "#38bdf8",
  smt: "#a78bfa",
  fvg: "#22d3ee",
  trade_setup: "#34d399",
};

interface TradingChartProps {
  bars: Bar[];
  annotations: ChartAnnotation[];
  overlays: OverlayToggles;
  onAnnotationClick: (annotation: ChartAnnotation) => void;
  jumpToTs: string | null;
  onJumpHandled: () => void;
  barWidthSeconds: number;
}

export function TradingChart({
  bars,
  annotations,
  overlays,
  onAnnotationClick,
  jumpToTs,
  onJumpHandled,
  barWidthSeconds,
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const priceLinesRef = useRef<IPriceLine[]>([]);
  const annotationsRef = useRef<ChartAnnotation[]>([]);

  // Create chart once.
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChartInstance(container);
    const series = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    chart.subscribeClick((param) => {
      if (!param.time) return;
      const clickedTs = Number(param.time);
      const tolerance = barWidthSeconds * 1.5;
      let best: ChartAnnotation | null = null;
      let bestDelta = Infinity;
      for (const annotation of annotationsRef.current) {
        const annoTs = toUnixSeconds(annotation.ts);
        const delta = Math.abs(annoTs - clickedTs);
        if (delta <= tolerance && delta < bestDelta) {
          best = annotation;
          bestDelta = delta;
        }
      }
      if (best) onAnnotationClick(best);
    });

    const handleResize = () => {
      if (!container) return;
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      priceLinesRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Push bar data.
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;
    const data: CandlestickData[] = bars.map((bar) => ({
      time: toUnixSeconds(bar.ts) as Time,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    }));
    series.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [bars]);

  // Apply overlays (price lines + markers).
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    for (const line of priceLinesRef.current) {
      series.removePriceLine(line);
    }
    priceLinesRef.current = [];

    const visible = annotations.filter((a) => overlays[a.kind]);
    annotationsRef.current = visible;

    const markers: SeriesMarker<Time>[] = [];

    for (const annotation of visible) {
      const color = OVERLAY_COLORS[annotation.kind];
      const time = toUnixSeconds(annotation.ts) as Time;

      switch (annotation.kind) {
        case "liquidity_pool": {
          const price = Number(annotation.raw.price);
          priceLinesRef.current.push(
            series.createPriceLine({
              price,
              color,
              lineWidth: 1,
              lineStyle: LineStyle.Dashed,
              axisLabelVisible: true,
              title: `${annotation.raw.pool_type ?? "pool"}`,
            }),
          );
          break;
        }
        case "fvg": {
          const high = Number(annotation.raw.gap_high);
          const low = Number(annotation.raw.gap_low);
          priceLinesRef.current.push(
            series.createPriceLine({
              price: high,
              color,
              lineWidth: 1,
              lineStyle: LineStyle.Dotted,
              axisLabelVisible: true,
              title: "FVG high",
            }),
            series.createPriceLine({
              price: low,
              color,
              lineWidth: 1,
              lineStyle: LineStyle.Dotted,
              axisLabelVisible: true,
              title: "FVG low",
            }),
          );
          break;
        }
        case "trade_setup": {
          const entry = Number(annotation.raw.entry_price);
          const stop = Number(annotation.raw.stop_price);
          const target = Number(annotation.raw.target_price);
          priceLinesRef.current.push(
            series.createPriceLine({ price: entry, color: "#34d399", lineWidth: 2, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: "Entry" }),
            series.createPriceLine({ price: stop, color: "#ef4444", lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "Stop" }),
            series.createPriceLine({ price: target, color: "#22c55e", lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: "Target" }),
          );
          markers.push({
            time,
            position: "inBar",
            color,
            shape: "circle",
            text: "Setup",
          });
          break;
        }
        case "liquidity_raid": {
          markers.push({
            time,
            position: "aboveBar",
            color,
            shape: "arrowDown",
            text: "Raid",
          });
          break;
        }
        case "displacement": {
          const isBullish = annotation.direction === "bullish";
          markers.push({
            time,
            position: isBullish ? "belowBar" : "aboveBar",
            color,
            shape: isBullish ? "arrowUp" : "arrowDown",
            text: "Disp",
          });
          break;
        }
        case "smt": {
          markers.push({
            time,
            position: "aboveBar",
            color,
            shape: "circle",
            text: "SMT",
          });
          break;
        }
      }
    }

    markers.sort((a, b) => Number(a.time) - Number(b.time));
    series.setMarkers(markers);
  }, [annotations, overlays]);

  // Jump-to-event.
  useEffect(() => {
    if (!jumpToTs) return;
    const chart = chartRef.current;
    if (!chart) return;
    const center = toUnixSeconds(jumpToTs);
    const span = barWidthSeconds * 60;
    chart.timeScale().setVisibleRange({
      from: (center - span) as Time,
      to: (center + span) as Time,
    });
    onJumpHandled();
  }, [jumpToTs, barWidthSeconds, onJumpHandled]);

  return <div ref={containerRef} className="h-full w-full" />;
}

function createChartInstance(container: HTMLDivElement): IChartApi {
  return createChart(container, {
    width: container.clientWidth,
    height: container.clientHeight,
    layout: {
      background: { type: ColorType.Solid, color: "#0b0e14" },
      textColor: "#cbd5e1",
    },
    grid: {
      vertLines: { color: "#1e293b" },
      horzLines: { color: "#1e293b" },
    },
    crosshair: { mode: CrosshairMode.Normal },
    rightPriceScale: { borderColor: "#1e293b" },
    timeScale: { borderColor: "#1e293b", timeVisible: true, secondsVisible: false },
  });
}
