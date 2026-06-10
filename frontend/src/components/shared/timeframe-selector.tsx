"use client";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { Timeframe } from "@/types";

const TIMEFRAMES: Timeframe[] = ["15m"];

interface TimeframeSelectorProps {
  value: Timeframe;
  onChange: (value: Timeframe) => void;
  options?: Timeframe[];
  className?: string;
}

export function TimeframeSelector({ value, onChange, options = TIMEFRAMES, className }: TimeframeSelectorProps) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as Timeframe)}>
      <SelectTrigger className={className}>
        <SelectValue placeholder="Timeframe" />
      </SelectTrigger>
      <SelectContent>
        {options.map((tf) => (
          <SelectItem key={tf} value={tf}>
            {tf}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
