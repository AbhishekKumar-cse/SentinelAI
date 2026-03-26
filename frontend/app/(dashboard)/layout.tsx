"use client";

export const dynamic = "force-dynamic";

import { useEffect } from "react";
import { onAuthStateChanged } from "firebase/auth";
import { useQueryClient } from "@tanstack/react-query";
import { auth } from "@/lib/firebase";
import { api } from "@/lib/api-client";
import { useAuthStore } from "@/store/auth-store";
import { useWebSocketStore } from "@/lib/websocket-store";
import Sidebar from "@/components/layout/Sidebar";
import Header from "@/components/layout/Header";
import ActivityFeed from "@/components/layout/ActivityFeed";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30000,
      refetchOnWindowFocus: true,
      retry: 3,
    },
  },
});

function DashboardLayoutInner({ children }: { children: React.ReactNode }) {
  const { setUser, setProfile, setInitialized, user } = useAuthStore();
  const { connect, disconnect } = useWebSocketStore();
  const qc = useQueryClient();

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      setUser(firebaseUser);
      setInitialized();

      if (firebaseUser) {
        try {
          const profile = await api.get<{
            tenantId: string;
            role: string;
            permissions: string[];
          }>("/auth/me");
          setProfile(profile);
        } catch (e) {
          // Dev mode: set default profile
          setProfile({
            tenantId: "dev_tenant_001",
            role: "TENANT_ADMIN",
            permissions: ["*"],
          });
        }

        // Connect WebSocket
        connect(qc);
      } else {
        disconnect();
      }
    });

    // In development, connect immediately with dev profile
    if (process.env.NODE_ENV === "development") {
      setProfile({
        tenantId: "dev_tenant_001",
        role: "TENANT_ADMIN",
        permissions: ["*"],
      });
      connect(qc);
    }

    return () => {
      unsubscribe();
    };
  }, []);

  return (
    <div className="flex h-screen bg-[#030712] text-white overflow-hidden">
      {/* Sidebar */}
      <Sidebar />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>

      {/* Real-time Activity Feed (right panel) */}
      <ActivityFeed />
    </div>
  );
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <DashboardLayoutInner>{children}</DashboardLayoutInner>
    </QueryClientProvider>
  );
}
