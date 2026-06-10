// Builds chart-ready overlay annotations from the detection-pipeline endpoints.

import {
  getDisplacementEvents,
  getFVGEvents,
  getLiquidityPools,
  getLiquidityRaids,
  getSMTEvents,
  getTradeSetups,
} from "@/lib/api";
import type { ChartAnnotation, Timeframe } from "@/types";

interface FetchParams {
  instrumentId: string;
  timeframe: Timeframe;
}

export async function fetchChartAnnotations({ instrumentId, timeframe }: FetchParams): Promise<ChartAnnotation[]> {
  const [pools, raids, displacements, smtEvents, fvgs, setups] = await Promise.all([
    getLiquidityPools({ instrument_id: instrumentId, timeframe }),
    getLiquidityRaids({ instrument_id: instrumentId, timeframe }),
    getDisplacementEvents({ instrument_id: instrumentId, timeframe }),
    getSMTEvents({ timeframe }),
    getFVGEvents({ instrument_id: instrumentId, timeframe }),
    getTradeSetups({ instrument_id: instrumentId, timeframe }),
  ]);

  const annotations: ChartAnnotation[] = [];

  for (const p of pools) {
    annotations.push({
      kind: "liquidity_pool",
      id: p.id,
      ts: p.ts,
      eventType: `liquidity_pool:${p.pool_type}`,
      direction: null,
      status: p.status,
      referencedIds: {},
      reasoningFields: { pool_type: p.pool_type, price: p.price, status: p.status },
      raw: p as unknown as Record<string, unknown>,
    });
  }

  for (const r of raids) {
    annotations.push({
      kind: "liquidity_raid",
      id: r.id,
      ts: r.ts,
      eventType: "liquidity_raid",
      direction: null,
      status: null,
      referencedIds: { pool_id: r.pool_id },
      reasoningFields: { raid_price: r.raid_price },
      raw: r as unknown as Record<string, unknown>,
    });
  }

  for (const d of displacements) {
    annotations.push({
      kind: "displacement",
      id: d.id,
      ts: d.ts_start,
      eventType: "displacement",
      direction: d.direction,
      status: null,
      referencedIds: {},
      reasoningFields: {
        body_magnitude: d.body_magnitude,
        body_ratio: d.body_ratio,
        bar_count: d.bar_count,
        ts_end: d.ts_end,
      },
      raw: d as unknown as Record<string, unknown>,
    });
  }

  for (const s of smtEvents) {
    if (s.lead_instrument_id !== instrumentId && s.lag_instrument_id !== instrumentId) continue;
    annotations.push({
      kind: "smt",
      id: s.id,
      ts: s.ts,
      eventType: "smt",
      direction: s.direction,
      status: null,
      referencedIds: { lead_swing_event_id: s.lead_swing_event_id, lag_swing_event_id: s.lag_swing_event_id },
      reasoningFields: {
        lead_price: s.lead_price,
        lead_reference_price: s.lead_reference_price,
        lag_price: s.lag_price,
        lag_reference_price: s.lag_reference_price,
        divergence_magnitude_ticks: s.divergence_magnitude_ticks,
      },
      raw: s as unknown as Record<string, unknown>,
    });
  }

  for (const f of fvgs) {
    annotations.push({
      kind: "fvg",
      id: f.id,
      ts: f.ts,
      eventType: "fvg",
      direction: f.direction,
      status: f.status,
      referencedIds: { displacement_event_id: f.displacement_event_id },
      reasoningFields: {
        gap_high: f.gap_high,
        gap_low: f.gap_low,
        ce: f.ce,
        gap_size_ticks: f.gap_size_ticks,
        mitigation_pct: f.mitigation_pct,
        max_mitigation_pct: f.max_mitigation_pct,
      },
      raw: f as unknown as Record<string, unknown>,
    });
  }

  for (const s of setups) {
    annotations.push({
      kind: "trade_setup",
      id: s.id,
      ts: s.created_at,
      eventType: "trade_setup",
      direction: s.direction,
      status: s.status,
      referencedIds: { execution_model_evaluation_id: s.execution_model_evaluation_id },
      reasoningFields: {
        entry_price: s.entry_price,
        stop_price: s.stop_price,
        target_price: s.target_price,
        rr_ratio: s.rr_ratio,
      },
      raw: s as unknown as Record<string, unknown>,
    });
  }

  return annotations;
}
