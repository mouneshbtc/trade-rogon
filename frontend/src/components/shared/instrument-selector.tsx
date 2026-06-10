"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export const INSTRUMENT_SYMBOLS = ["NQ", "ES"] as const;
export type InstrumentSymbol = (typeof INSTRUMENT_SYMBOLS)[number];

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
            {symbol}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
