import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Clip Finder 2.0 — Find the moment", template: "%s · Clip Finder 2.0" },
  description: "Find, shape, and export the strongest moments from your long-form video.",
  applicationName: "Clip Finder 2.0",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}