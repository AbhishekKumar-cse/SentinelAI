import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Toaster } from "sonner";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "AntiGravity — Autonomous Enterprise AI Platform",
  description: "AI-powered multi-agent platform for autonomous enterprise workflow orchestration. Built with the NERVE architecture.",
  openGraph: {
    title: "AntiGravity AI Platform",
    description: "Self-orchestrating multi-agent AI for enterprise workflows",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.variable} font-sans antialiased bg-[#030712] text-white`}>
        {children}
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#0f172a",
              color: "#e2e8f0",
              border: "1px solid #1e293b",
              borderRadius: "12px",
            },
          }}
        />
      </body>
    </html>
  );
}
