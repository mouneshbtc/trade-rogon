"use client";

import { Button } from "@/components/ui/button";
import { useChartStore } from "@/store/chart-store";
import { cn } from "@/lib/utils";
import type { OverlayKind } from "@/types";

const TOGGLES: { key: OverlayKind; label: string }[] = [
  { key: "liquidity_pool", label: "Liquidity Pools" },
  { key: "liquidity_raid", label: "Liquidity Raids" },
  { key: "displacement", label: "Displacement" },
  { key: "smt", label: "SMT" },
  { key: "fvg", label: "FVG" },
  { key: "trade_setup", label: "Trade Setups" },
];

export function OverlayToggles() {
  const overlays = useChartStore((s) => s.overlays);
  const toggleOverlay = useChartStore((s) => s.toggleOverlay);

  return (
    <div className="flex flex-wrap gap-2">
      {TOGGLES.map((t) => (
        <Button
          key={t.key}
          size="sm"
          variant={overlays[t.key] ? "secondary" : "outline"}
          onClick={() => toggleOverlay(t.key)}
          className={cn(!overlays[t.key] && "text-muted-foreground")}
        >
          {t.label}
        </Button>
      ))}
    </div>
  );
}
