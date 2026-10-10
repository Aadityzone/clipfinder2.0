import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Clip Finder — Find the moments", template: "%s · Clip Finder" },
  description: "Turn real long-form videos into standout short-form clips. Analyze, refine, and export from one creator workspace.",
  applicationName: "Clip Finder",
  robots: { index: true, follow: true },
};
export const viewport: Viewport = {
  themeColor: "#080a0e",
  colorScheme: "dark",
};
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
