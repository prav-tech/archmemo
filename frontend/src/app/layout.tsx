import type { Metadata } from "next";
import { IBM_Plex_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { Navigation } from "@/components/navigation";
import { AuthGate, AuthProvider } from "@/components/auth-provider";

const sans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
  display: "swap",
});

// Used for decision IDs and other identifiers only.
const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "ArchMemory",
  description: "Architecture decision and outcome memory agent",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${mono.variable}`}>
      <body className="font-sans antialiased">
        <AuthProvider>
          <div className="min-h-screen bg-background">
            <Navigation />
            <main className="mx-auto max-w-6xl px-4 py-8">
              <AuthGate>{children}</AuthGate>
            </main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
