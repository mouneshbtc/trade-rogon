// Typed mirrors of backend Pydantic schemas (trade-rogon backend, app/schemas/*.py).
// Keep these in sync with the backend — no `any` types.

export type Timeframe = "1m" | "5m" | "15m" | "1h" | "4h" | "1d" | "1w";

export type Direction = "bullish" | "bearish";

// ── Market Data ────────────────────────────────────────────────────────────

export interface Instrument {
  id: string;
  symbol: string;
}

export interface Bar {
  instrument_id: string;
  symbol: string;
  timeframe: Timeframe;
  ts: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface BarListOut {
  symbol: string;
  timeframe: Timeframe;
  items: Bar[];
}

// ── Market Structure ──────────────────────────────────────────────────────

export type StructuralEventType =
  | "swing_high"
  | "swing_low"
  | "bullish_bos"
  | "bearish_bos"
  | "bullish_counter_structure_break"
  | "bearish_counter_structure_break";

export interface StructuralEvent {
  id: string;
  instrument_id: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  event_type: StructuralEventType;
  ts: string;
  price: string;
  reference_swing_event_id: string | null;
  created_at: string;
}

export interface MarketStructureDetectResponse {
  instrument_id: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  events_detected: number;
  events: StructuralEvent[];
}

// ── Liquidity ──────────────────────────────────────────────────────────────

export type PoolType = "pdh" | "pdl" | "eqh" | "eql";
export type PoolStatus = "active" | "raided" | "resolved";
export type OutcomeType = "sweep" | "run" | "unresolved";

export interface LiquidityPool {
  id: string;
  instrument_id: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  pool_type: PoolType;
  price: string;
  ts: string;
  status: PoolStatus;
  source_bar_ts: string | null;
  source_swing_event_ids: string[] | null;
  created_at: string;
}

export interface LiquidityRaid {
  id: string;
  pool_id: string;
  instrument_id: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  ts: string;
  raid_price: string;
  created_at: string;
}

export interface LiquidityOutcome {
  id: string;
  raid_id: string;
  pool_id: string;
  instrument_id: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  outcome_type: OutcomeType;
  ts: string;
  close_price: string;
  outcome_model: string;
  confirmation_delay_bars: number;
  created_at: string;
}

export interface LiquidityDetectResponse {
  instrument_id: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  pools_created: Record<string, number>;
  raids_detected: number;
  outcomes: Record<string, number>;
}

// ── Displacement ───────────────────────────────────────────────────────────

export interface DisplacementEvent {
  id: string;
  instrument_id: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  direction: Direction;
  ts_start: string;
  ts_end: string;
  price_open: string;
  price_close: string;
  body_magnitude: string;
  body_ratio: string;
  bar_count: number;
  created_at: string;
}

export interface DisplacementDetectResponse {
  instrument_id: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  events_created: Record<string, number>;
}

// ── SMT ────────────────────────────────────────────────────────────────────

export interface SMTDivergenceEvent {
  id: string;
  instrument_a_id: string;
  instrument_b_id: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  direction: Direction;
  ts: string;
  lead_instrument_id: string;
  lead_price: string;
  lead_reference_price: string;
  lead_swing_event_id: string | null;
  lag_instrument_id: string;
  lag_price: string;
  lag_reference_price: string;
  lag_swing_event_id: string | null;
  divergence_magnitude_ticks: string;
  created_at: string;
}

export interface SMTDetectResponse {
  instrument_a_symbol: string;
  instrument_b_symbol: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  events_created: Record<string, number>;
}

// ── FVG ────────────────────────────────────────────────────────────────────

export type FVGStatus = "ACTIVE" | "PARTIALLY_MITIGATED" | "FULLY_MITIGATED" | "INVALIDATED";

export interface FVGEvent {
  id: string;
  instrument_id: string;
  timeframe: string;
  concept_definition_version: number;
  direction: Direction;
  ts: string;
  gap_high: string;
  gap_low: string;
  ce: string;
  gap_size_ticks: string;
  displacement_event_id: string | null;
  status: FVGStatus;
  mitigation_pct: string;
  max_mitigation_pct: string;
  created_at: string;
}

export interface FVGDetectResponse {
  instrument_id: string;
  timeframe: Timeframe;
  concept_definition_version: number;
  events_created: Record<string, number>;
}

// ── Execution Model ────────────────────────────────────────────────────────

export interface ExecutionModelEvaluation {
  id: string;
  execution_model_id: string;
  instrument_id: string;
  timeframe: string;
  concept_definition_version: number;
  candidate_ts: string;
  direction: string;
  matched: boolean;
  match_score: string;
  disqualified: boolean;
  disqualification_reason: string | null;
  liquidity_raid_id: string | null;
  smt_divergence_id: string | null;
  displacement_event_id: string | null;
  fvg_event_id: string | null;
  fvg_status_at_entry: string | null;
  fvg_mitigation_pct_at_entry: string | null;
  evaluated_at: string;
  created_at: string;
}

export interface ExecutionModelEvaluateResponse {
  instrument_id: string;
  timeframe: string;
  concept_definition_version: number;
  total_evaluated: number;
  total_matched: number;
}

// ── Trade Setup ────────────────────────────────────────────────────────────

export type TradeSetupStatus = "pending" | "triggered" | "expired" | "invalidated";

export interface TradeSetup {
  id: string;
  instrument_id: string;
  timeframe: string;
  execution_model_evaluation_id: string | null;
  direction: string;
  entry_price: string;
  stop_price: string;
  target_price: string;
  risk_points: string;
  reward_points: string;
  rr_ratio: string;
  status: TradeSetupStatus;
  created_at: string;
  updated_at: string;
}

export interface TradeSetupCreate {
  instrument_id: string;
  timeframe: string;
  execution_model_evaluation_id?: string | null;
  direction: string;
  entry_price: string;
  stop_price: string;
  target_price: string;
}

// ── Pipeline / Event Explorer (frontend-only) ─────────────────────────────

export type PipelineStageKey =
  | "market_structure"
  | "liquidity"
  | "displacement"
  | "smt"
  | "fvg"
  | "execution_model"
  | "trade_setup";

export interface PipelineStage {
  key: PipelineStageKey;
  label: string;
  status: "idle" | "running" | "done" | "error";
  count: number | null;
  countLabel: string;
  error?: string;
}

export type EventExplorerType =
  | "swing_high"
  | "swing_low"
  | "bos"
  | "counter_structure_break"
  | "liquidity_pool"
  | "liquidity_raid"
  | "liquidity_outcome"
  | "displacement"
  | "smt"
  | "fvg"
  | "execution_model"
  | "trade_setup";

export interface EventExplorerRow {
  id: string;
  ts: string;
  event_type: EventExplorerType;
  direction: string | null;
  status: string | null;
  price: string | null;
  instrument_id: string | null;
  timeframe: string;
  raw: Record<string, unknown>;
}

export type SetupFeedbackVerdict = "yes" | "no" | "unsure";

// ── Chart overlays (frontend-only) ────────────────────────────────────────

export type OverlayKind = "liquidity_pool" | "liquidity_raid" | "displacement" | "smt" | "fvg" | "trade_setup";

export interface ChartAnnotation {
  kind: OverlayKind;
  id: string;
  ts: string;
  eventType: string;
  direction: string | null;
  status: string | null;
  referencedIds: Record<string, string | null>;
  reasoningFields: Record<string, string | number | boolean | null>;
  raw: Record<string, unknown>;
}
