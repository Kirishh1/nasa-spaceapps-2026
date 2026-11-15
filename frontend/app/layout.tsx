import type { Metadata } from "next";
import { Archivo, JetBrains_Mono } from "next/font/google";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

const sans = Archivo({ variable: "--font-sans", subsets: ["latin"], axes: ["wdth"] });
const mono = JetBrains_Mono({ variable: "--font-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "SAR-Pulse · NISAR change interpretation",
  description: "Compare real NISAR L-band radar observations, detect backscatter change, and inspect the evidence and uncertainty behind it.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${sans.variable} ${mono.variable}`}>{children}</body>
    </html>
  );
}
