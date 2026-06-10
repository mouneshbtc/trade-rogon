"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const INSTRUMENT_SYMBOLS = ["NQ.c.0", "ES.c.0"] as const;
export type InstrumentSymbol = (typeof INSTRUMENT_SYMBOLS)[number];

// Databento continuous-contract symbols (DB-canonical) -> short display labels.
const INSTRUMENT_LABELS: Record<InstrumentSymbol, string> = {
  "NQ.c.0": "NQ",
  "ES.c.0": "ES",
};

interface InstrumentSelectorProps {
  value: InstrumentSymbol;
  onChange: (value: InstrumentSymbol) => void;
  className?: string;
}

export function InstrumentSelector({ value, onChange, className }: InstrumentSelectorProps) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as InstrumentSymbol)}>
      <SelectTrigger className={className}>
        <SelectValue placeholder="Instrument" />
      </SelectTrigger>
      <SelectContent>
        {INSTRUMENT_SYMBOLS.map((symbol) => (
          <SelectItem key={symbol} value={symbol}>
            {INSTRUMENT_LABELS[symbol]}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
