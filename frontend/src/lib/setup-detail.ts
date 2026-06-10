import {
  getDisplacementEvents,
  getExecutionModelEvaluations,
  getFVGEvents,
  getLiquidityRaids,
  getSMTEvents,
} from "@/lib/api";
import type {
  DisplacementEvent,
  ExecutionModelEvaluation,
  FVGEvent,
  LiquidityRaid,
  SMTDivergenceEvent,
  Timeframe,
  TradeSetup,
} from "@/types";

export interface SetupLinkedEvents {
  evaluation: ExecutionModelEvaluation | null;
  raid: LiquidityRaid | null;
  smt: SMTDivergenceEvent | null;
  displacement: DisplacementEvent | null;
  fvg: FVGEvent | null;
}

export async function fetchSetupLinkedEvents(setup: TradeSetup, timeframe: Timeframe): Promise<SetupLinkedEvents> {
  const empty: SetupLinkedEvents = { evaluation: null, raid: null, smt: null, displacement: null, fvg: null };
  if (!setup.execution_model_evaluation_id) return empty;

  const evaluations = await getExecutionModelEvaluations({ instrument_id: setup.instrument_id });
  const evaluation = evaluations.find((e) => e.id === setup.execution_model_evaluation_id) ?? null;
  if (!evaluation) return empty;

  const [raids, smtEvents, displacements, fvgs] = await Promise.all([
    evaluation.liquidity_raid_id
      ? getLiquidityRaids({ instrument_id: setup.instrument_id, timeframe })
      : Promise.resolve([]),
    evaluation.smt_divergence_id ? getSMTEvents({ timeframe }) : Promise.resolve([]),
    evaluation.displacement_event_id
      ? getDisplacementEvents({ instrument_id: setup.instrument_id, timeframe })
      : Promise.resolve([]),
    evaluation.fvg_event_id ? getFVGEvents({ instrument_id: setup.instrument_id, timeframe }) : Promise.resolve([]),
  ]);

  return {
    evaluation,
    raid: raids.find((r) => r.id === evaluation.liquidity_raid_id) ?? null,
    smt: smtEvents.find((s) => s.id === evaluation.smt_divergence_id) ?? null,
    displacement: displacements.find((d) => d.id === evaluation.displacement_event_id) ?? null,
    fvg: fvgs.find((f) => f.id === evaluation.fvg_event_id) ?? null,
  };
}
