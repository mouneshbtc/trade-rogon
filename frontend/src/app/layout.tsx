import type { Metadata } from "next";

import { Sidebar } from "@/components/layout/sidebar";
import { Providers } from "@/app/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "trade-rogon — Research Console",
  description: "Research frontend for the trade-rogon ICT concept detection pipeline.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">
        <Providers>
          <div className="flex h-screen overflow-hidden">
            <Sidebar />
            <main className="flex-1 overflow-y-auto">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
