"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, BarChart3, CandlestickChart, ListTree, Target } from "lucide-react";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/pipeline", label: "Pipeline", icon: Activity },
  { href: "/events", label: "Events", icon: ListTree },
  { href: "/chart", label: "Chart", icon: CandlestickChart },
  { href: "/setups", label: "Setups", icon: Target },
  { href: "/statistics", label: "Statistics", icon: BarChart3 },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col border-r border-border bg-card">
      <div className="border-b border-border px-4 py-4">
        <div className="text-sm font-semibold tracking-tight">trade-rogon</div>
        <div className="text-xs text-muted-foreground">Research Console</div>
      </div>
      <nav className="flex flex-col gap-1 p-2">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
