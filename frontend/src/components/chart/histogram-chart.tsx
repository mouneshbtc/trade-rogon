"use client";

import { useEffect, useRef } from "react";
import { ColorType, createChart, type HistogramData, type IChartApi, type Time } from "lightweight-charts";

export interface HistogramPoint {
  time: string; // YYYY-MM-DD
  value: number;
}

interface HistogramChartProps {
  data: HistogramPoint[];
  color?: string;
}

export function HistogramChart({ data, color = "#38bdf8" }: HistogramChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#cbd5e1",
      },
      grid: {
        vertLines: { color: "#1e293b" },
        horzLines: { color: "#1e293b" },
      },
      rightPriceScale: { borderColor: "#1e293b" },
      timeScale: { borderColor: "#1e293b", timeVisible: false },
    });
    chartRef.current = chart;

    const series = chart.addHistogramSeries({ color });
    const points: HistogramData[] = data.map((d) => ({ time: d.time as Time, value: d.value }));
    series.setData(points);
    chart.timeScale().fitContent();

    const handleResize = () => {
      chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [data, color]);

  return <div ref={containerRef} className="h-full w-full" />;
}
