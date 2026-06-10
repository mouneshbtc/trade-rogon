// Aggregates every detection-pipeline event source into a single, normalized
// row shape for the Event Explorer (/events). No hidden transformations —
// `raw` always carries the untouched API object.

import {
  getDisplacementEvents,
  getExecutionModelEvaluations,
  getFVGEvents,
  getLiquidityPools,
  getLiquidityRaids,
  getSMTEvents,
  getStructuralEvents,
  getTradeSetups,
} from "@/lib/api";
import type { EventExplorerRow, EventExplorerType, Timeframe } from "@/types";

interface FetchParams {
  instrumentId: string;
  timeframe: Timeframe;
  eventType: EventExplorerType | "all";
  start: string;
  end: string;
}

const MARKET_STRUCTURE_TYPES: Record<string, EventExplorerType> = {
  swing_high: "swing_high",
  swing_low: "swing_low",
  bullish_bos: "bos",
  bearish_bos: "bos",
  bullish_counter_structure_break: "counter_structure_break",
  bearish_counter_structure_break: "counter_structure_break",
};

function wants(eventType: FetchParams["eventType"], type: EventExplorerType): boolean {
  return eventType === "all" || eventType === type;
}

export async function fetchEventRows(params: FetchParams): Promise<EventExplorerRow[]> {
  const { instrumentId, timeframe, eventType, start, end } = params;
  const rows: EventExplorerRow[] = [];

  const wantsStructure =
    wants(eventType, "swing_high") ||
    wants(eventType, "swing_low") ||
    wants(eventType, "bos") ||
    wants(eventType, "counter_structure_break");

  const tasks: Promise<void>[] = [];

  if (wantsStructure) {
    tasks.push(
      getStructuralEvents({ instrument_id: instrumentId, timeframe }).then((events) => {
        for (const e of events) {
          const mapped = MARKET_STRUCTURE_TYPES[e.event_type];
          if (!mapped || !wants(eventType, mapped)) continue;
          rows.push({
            id: e.id,
            ts: e.ts,
            event_type: mapped,
            direction: e.event_type.startsWith("bullish")
              ? "bullish"
              : e.event_type.startsWith("bearish")
                ? "bearish"
                : null,
            status: null,
            price: e.price,
            instrument_id: e.instrument_id,
            timeframe: e.timeframe,
            raw: e as unknown as Record<string, unknown>,
          });
        }
      }),
    );
  }

  if (wants(eventType, "liquidity_pool")) {
    tasks.push(
      getLiquidityPools({ instrument_id: instrumentId, timeframe }).then((pools) => {
        for (const p of pools) {
          rows.push({
            id: p.id,
            ts: p.ts,
            event_type: "liquidity_pool",
            direction: null,
            status: p.status,
            price: p.price,
            instrument_id: p.instrument_id,
            timeframe: p.timeframe,
            raw: p as unknown as Record<string, unknown>,
          });
        }
      }),
    );
  }

  if (wants(eventType, "liquidity_raid")) {
    tasks.push(
      getLiquidityRaids({ instrument_id: instrumentId, timeframe }).then((raids) => {
        for (const r of raids) {
          rows.push({
            id: r.id,
            ts: r.ts,
            event_type: "liquidity_raid",
            direction: null,
            status: null,
            price: r.raid_price,
            instrument_id: r.instrument_id,
            timeframe: r.timeframe,
            raw: r as unknown as Record<string, unknown>,
          });
        }
      }),
    );
  }

  // Liquidity outcomes have no list endpoint on the backend yet — skip rather
  // than fail the whole explorer.
  if (wants(eventType, "liquidity_outcome")) {
    // intentionally empty
  }

  if (wants(eventType, "displacement")) {
    tasks.push(
      getDisplacementEvents({ instrument_id: instrumentId, timeframe }).then((events) => {
        for (const d of events) {
          rows.push({
            id: d.id,
            ts: d.ts_start,
            event_type: "displacement",
            direction: d.direction,
            status: null,
            price: d.price_close,
            instrument_id: d.instrument_id,
            timeframe: d.timeframe,
            raw: d as unknown as Record<string, unknown>,
          });
        }
      }),
    );
  }

  if (wants(eventType, "smt")) {
    tasks.push(
      getSMTEvents({ timeframe }).then((events) => {
        for (const s of events) {
          rows.push({
            id: s.id,
            ts: s.ts,
            event_type: "smt",
            direction: s.direction,
            status: null,
            price: s.lead_price,
            instrument_id: s.lead_instrument_id,
            timeframe: s.timeframe,
            raw: s as unknown as Record<string, unknown>,
          });
        }
      }),
    );
  }

  if (wants(eventType, "fvg")) {
    tasks.push(
      getFVGEvents({ instrument_id: instrumentId, timeframe }).then((events) => {
        for (const f of events) {
          rows.push({
            id: f.id,
            ts: f.ts,
            event_type: "fvg",
            direction: f.direction,
            status: f.status,
            price: f.gap_high,
            instrument_id: f.instrument_id,
            timeframe: f.timeframe,
            raw: f as unknown as Record<string, unknown>,
          });
        }
      }),
    );
  }

  if (wants(eventType, "execution_model")) {
    tasks.push(
      getExecutionModelEvaluations({ instrument_id: instrumentId }).then((events) => {
        for (const m of events) {
          rows.push({
            id: m.id,
            ts: m.candidate_ts,
            event_type: "execution_model",
            direction: m.direction,
            status: m.disqualified ? "disqualified" : m.matched ? "matched" : "unmatched",
            price: null,
            instrument_id: m.instrument_id,
            timeframe: m.timeframe,
            raw: m as unknown as Record<string, unknown>,
          });
        }
      }),
    );
  }

  if (wants(eventType, "trade_setup")) {
    tasks.push(
      getTradeSetups({ instrument_id: instrumentId, timeframe }).then((setups) => {
        for (const s of setups) {
          rows.push({
            id: s.id,
            ts: s.created_at,
            event_type: "trade_setup",
            direction: s.direction,
            status: s.status,
            price: s.entry_price,
            instrument_id: s.instrument_id,
            timeframe: s.timeframe,
            raw: s as unknown as Record<string, unknown>,
          });
        }
      }),
    );
  }

  await Promise.all(tasks);

  const startMs = new Date(start).getTime();
  const endMs = new Date(end).getTime();

  return rows
    .filter((r) => {
      const ts = new Date(r.ts).getTime();
      return ts >= startMs && ts <= endMs;
    })
    .sort((a, b) => new Date(b.ts).getTime() - new Date(a.ts).getTime());
}

export const EVENT_TYPE_OPTIONS: { value: EventExplorerType | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "swing_high", label: "Swing High" },
  { value: "swing_low", label: "Swing Low" },
  { value: "bos", label: "BOS" },
  { value: "counter_structure_break", label: "Counter Structure Break" },
  { value: "liquidity_pool", label: "Liquidity Pool" },
  { value: "liquidity_raid", label: "Liquidity Raid" },
  { value: "liquidity_outcome", label: "Liquidity Outcome" },
  { value: "displacement", label: "Displacement" },
  { value: "smt", label: "SMT" },
  { value: "fvg", label: "FVG" },
  { value: "execution_model", label: "Execution Model" },
  { value: "trade_setup", label: "Trade Setup" },
];
