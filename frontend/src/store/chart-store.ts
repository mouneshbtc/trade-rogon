import { create } from "zustand";

import type { ChartAnnotation, OverlayKind } from "@/types";

export interface OverlayToggles {
  liquidity_pool: boolean;
  liquidity_raid: boolean;
  displacement: boolean;
  smt: boolean;
  fvg: boolean;
  trade_setup: boolean;
}

const DEFAULT_OVERLAYS: OverlayToggles = {
  liquidity_pool: true,
  liquidity_raid: true,
  displacement: true,
  smt: true,
  fvg: true,
  trade_setup: true,
};

interface ChartState {
  overlays: OverlayToggles;
  toggleOverlay: (kind: OverlayKind) => void;
  selectedAnnotation: ChartAnnotation | null;
  setSelectedAnnotation: (annotation: ChartAnnotation | null) => void;
  jumpToTs: string | null;
  requestJumpTo: (ts: string) => void;
  clearJumpTo: () => void;
}

export const useChartStore = create<ChartState>((set) => ({
  overlays: DEFAULT_OVERLAYS,
  toggleOverlay: (kind) =>
    set((state) => ({
      overlays: { ...state.overlays, [kind]: !state.overlays[kind] },
    })),
  selectedAnnotation: null,
  setSelectedAnnotation: (annotation) => set({ selectedAnnotation: annotation }),
  jumpToTs: null,
  requestJumpTo: (ts) => set({ jumpToTs: ts }),
  clearJumpTo: () => set({ jumpToTs: null }),
}));
