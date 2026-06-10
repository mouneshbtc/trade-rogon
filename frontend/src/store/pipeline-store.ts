import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { PipelineStage, PipelineStageKey, Timeframe } from "@/types";

export const PIPELINE_STAGES: { key: PipelineStageKey; label: string }[] = [
  { key: "market_structure", label: "Market Structure" },
  { key: "liquidity", label: "Liquidity" },
  { key: "displacement", label: "Displacement" },
  { key: "smt", label: "SMT" },
  { key: "fvg", label: "FVG" },
  { key: "execution_model", label: "Execution Models" },
  { key: "trade_setup", label: "Trade Setups" },
];

function freshStages(): PipelineStage[] {
  return PIPELINE_STAGES.map((s) => ({
    key: s.key,
    label: s.label,
    status: "idle",
    count: null,
    countLabel: "",
  }));
}

export interface LastRun {
  symbol: string;
  timeframe: Timeframe;
  start: string;
  end: string;
  finishedAt: string;
  stages: PipelineStage[];
}

interface PipelineState {
  stages: PipelineStage[];
  isRunning: boolean;
  lastRun: LastRun | null;
  resetStages: () => void;
  setStage: (key: PipelineStageKey, patch: Partial<PipelineStage>) => void;
  setRunning: (running: boolean) => void;
  saveLastRun: (run: LastRun) => void;
}

export const usePipelineStore = create<PipelineState>()(
  persist(
    (set) => ({
      stages: freshStages(),
      isRunning: false,
      lastRun: null,
      resetStages: () => set({ stages: freshStages() }),
      setStage: (key, patch) =>
        set((state) => ({
          stages: state.stages.map((stage) => (stage.key === key ? { ...stage, ...patch } : stage)),
        })),
      setRunning: (running) => set({ isRunning: running }),
      saveLastRun: (run) => set({ lastRun: run }),
    }),
    {
      name: "trade-rogon-pipeline",
      partialize: (state) => ({ lastRun: state.lastRun }),
    },
  ),
);
