import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata={title:"Clip Finder",description:"AI-powered video repurposing for creators."};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}