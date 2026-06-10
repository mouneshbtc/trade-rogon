"use client";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

interface DateRangePickerProps {
  start: string;
  end: string;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
  className?: string;
}

export function DateRangePicker({ start, end, onStartChange, onEndChange, className }: DateRangePickerProps) {
  return (
    <div className={className}>
      <div className="grid grid-cols-2 gap-2">
        <div className="flex flex-col gap-1">
          <Label htmlFor="start-date">Start Date</Label>
          <Input id="start-date" type="date" value={start} onChange={(e) => onStartChange(e.target.value)} />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="end-date">End Date</Label>
          <Input id="end-date" type="date" value={end} onChange={(e) => onEndChange(e.target.value)} />
        </div>
      </div>
    </div>
  );
}

export function dateToStartOfDayIso(date: string): string {
  return new Date(`${date}T00:00:00Z`).toISOString();
}

export function dateToEndOfDayIso(date: string): string {
  return new Date(`${date}T23:59:59Z`).toISOString();
}
