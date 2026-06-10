import { Badge, type BadgeProps } from "@/components/ui/badge";

const VARIANT_MAP: Record<string, BadgeProps["variant"]> = {
  // Trade setup statuses
  pending: "muted",
  triggered: "success",
  expired: "outline",
  invalidated: "danger",
  // FVG statuses
  ACTIVE: "success",
  PARTIALLY_MITIGATED: "secondary",
  FULLY_MITIGATED: "muted",
  INVALIDATED: "danger",
  // Liquidity pool statuses
  active: "success",
  raided: "secondary",
  resolved: "muted",
  // Direction
  bullish: "success",
  bearish: "danger",
  // Execution model
  matched: "success",
  disqualified: "danger",
};

interface StatusBadgeProps {
  status: string | null | undefined;
  className?: string;
}

export function StatusBadge({ status, className }: StatusBadgeProps) {
  if (!status) return <Badge variant="outline" className={className}>—</Badge>;
  const variant = VARIANT_MAP[status] ?? "outline";
  return (
    <Badge variant={variant} className={className}>
      {status}
    </Badge>
  );
}
