// Central, typed API client for the trade-rogon backend.
// All requests go through the Next.js rewrite at /api/v1/* (see next.config.ts).

import type {
  Bar,
  BarListOut,
  DisplacementDetectResponse,
  DisplacementEvent,
  Direction,
  ExecutionModelEvaluateResponse,
  ExecutionModelEvaluation,
  FVGDetectResponse,
  FVGEvent,
  FVGStatus,
  Instrument,
  LiquidityDetectResponse,
  LiquidityPool,
  LiquidityRaid,
  MarketStructureDetectResponse,
  OutcomeType,
  PoolStatus,
  PoolType,
  SMTDetectResponse,
  SMTDivergenceEvent,
  StructuralEvent,
  Timeframe,
  TradeSetup,
  TradeSetupCreate,
  TradeSetupStatus,
} from "@/types";

const BASE = "/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ? JSON.stringify(body.detail) : detail;
    } catch {
      // ignore non-JSON error bodies
    }
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

// ── Market Data ────────────────────────────────────────────────────────────

export function getInstrument(symbol: string): Promise<Instrument> {
  return request<Instrument>(`/market-data/instruments/${symbol}`);
}

export function getBars(
  symbol: string,
  params: { timeframe: Timeframe; start: string; end: string },
): Promise<BarListOut> {
  return request<BarListOut>(`/market-data/${symbol}/bars${buildQuery(params)}`);
}

export type { Bar };

// ── Market Structure ──────────────────────────────────────────────────────

export function detectMarketStructure(body: {
  instrument_id: string;
  timeframe: Timeframe;
  start: string;
  end: string;
}): Promise<MarketStructureDetectResponse> {
  return request<MarketStructureDetectResponse>("/market-structure/detect", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getStructuralEvents(params: {
  instrument_id: string;
  timeframe: Timeframe;
}): Promise<StructuralEvent[]> {
  return request<StructuralEvent[]>(`/market-structure/events${buildQuery(params)}`);
}

// ── Liquidity ──────────────────────────────────────────────────────────────

export function detectLiquidity(body: {
  instrument_id: string;
  timeframe: Timeframe;
  start: string;
  end: string;
}): Promise<LiquidityDetectResponse> {
  return request<LiquidityDetectResponse>("/liquidity/detect", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getLiquidityPools(params: {
  instrument_id: string;
  timeframe: Timeframe;
  pool_type?: PoolType;
  status?: PoolStatus;
}): Promise<LiquidityPool[]> {
  return request<LiquidityPool[]>(`/liquidity/pools${buildQuery(params)}`);
}

export function getLiquidityRaids(params: {
  instrument_id: string;
  timeframe: Timeframe;
  pool_type?: PoolType;
  outcome_type?: OutcomeType;
}): Promise<LiquidityRaid[]> {
  return request<LiquidityRaid[]>(`/liquidity/raids${buildQuery(params)}`);
}

// ── Displacement ───────────────────────────────────────────────────────────

export function detectDisplacement(body: {
  instrument_id: string;
  timeframe: Timeframe;
  start: string;
  end: string;
}): Promise<DisplacementDetectResponse> {
  return request<DisplacementDetectResponse>("/displacement/detect", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getDisplacementEvents(params: {
  instrument_id: string;
  timeframe: Timeframe;
  direction?: Direction;
}): Promise<DisplacementEvent[]> {
  return request<DisplacementEvent[]>(`/displacement/events${buildQuery(params)}`);
}

// ── SMT ────────────────────────────────────────────────────────────────────

export function detectSMT(body: { timeframe: Timeframe; start: string; end: string }): Promise<SMTDetectResponse> {
  return request<SMTDetectResponse>("/smt/detect", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getSMTEvents(params: { timeframe: Timeframe; direction?: Direction }): Promise<SMTDivergenceEvent[]> {
  return request<SMTDivergenceEvent[]>(`/smt/events${buildQuery(params)}`);
}

// ── FVG ────────────────────────────────────────────────────────────────────

export function detectFVG(body: {
  instrument_id: string;
  timeframe: Timeframe;
  start: string;
  end: string;
}): Promise<FVGDetectResponse> {
  return request<FVGDetectResponse>("/fvg/detect", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getFVGEvents(params: {
  instrument_id: string;
  timeframe: Timeframe;
  direction?: Direction;
  status?: FVGStatus;
}): Promise<FVGEvent[]> {
  return request<FVGEvent[]>(`/fvg/events${buildQuery(params)}`);
}

// ── Execution Model ────────────────────────────────────────────────────────

export function evaluateExecutionModel(body: {
  instrument_id: string;
  start: string;
  end: string;
}): Promise<ExecutionModelEvaluateResponse> {
  return request<ExecutionModelEvaluateResponse>("/execution-model/evaluate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getExecutionModelEvaluations(params: {
  instrument_id: string;
  matched?: boolean;
  start?: string;
  end?: string;
}): Promise<ExecutionModelEvaluation[]> {
  return request<ExecutionModelEvaluation[]>(`/execution-model/evaluations${buildQuery(params)}`);
}

// ── Trade Setups ───────────────────────────────────────────────────────────

export function createTradeSetup(body: TradeSetupCreate): Promise<TradeSetup> {
  return request<TradeSetup>("/trade-setups", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function getTradeSetups(params: {
  instrument_id: string;
  timeframe: Timeframe;
  direction?: Direction;
  status?: TradeSetupStatus;
}): Promise<TradeSetup[]> {
  return request<TradeSetup[]>(`/trade-setups${buildQuery(params)}`);
}

export function getTradeSetup(setupId: string): Promise<TradeSetup> {
  return request<TradeSetup>(`/trade-setups/${setupId}`);
}

export function updateTradeSetupStatus(setupId: string, status: TradeSetupStatus): Promise<TradeSetup> {
  return request<TradeSetup>(`/trade-setups/${setupId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}
