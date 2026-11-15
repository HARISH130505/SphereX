import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SPHEREx Explorer",
  description: "Explore NASA SPHEREx all-sky infrared spectrophotometry, inspect cross-epoch difference imaging, vet moving solar system candidates, and analyze 102-band calibrated SED spectra.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#030712] text-slate-100 antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        {children}
      </body>
    </html>
  );
}