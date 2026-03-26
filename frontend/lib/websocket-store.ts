/**
 * WebSocket Zustand store.
 * Connects to /api/v1/ws, auto-reconnects with exponential backoff.
 * Dispatches real-time events to appropriate TanStack Query caches.
 */
import { create } from "zustand";
import { auth } from "./firebase";

type EventType =
  | "WorkflowUpdated"
  | "TaskStatusChanged"
  | "NewHumanTask"
  | "HumanTaskUpdated"
  | "NewAuditEvent"
  | "EscalationTriggered"
  | "Connected"
  | "Heartbeat"
  | "Ping";

interface WebSocketEvent {
  event_type: EventType;
  collection?: string;
  operation?: string;
  data?: Record<string, unknown>;
  timestamp: string;
}

type EventHandler = (event: WebSocketEvent) => void;

interface WebSocketStore {
  isConnected: boolean;
  lastEvent: WebSocketEvent | null;
  reconnectCount: number;
  connect: (queryClient?: unknown) => void;
  disconnect: () => void;
  subscribe: (eventType: EventType, handler: EventHandler) => () => void;
}

let ws: WebSocket | null = null;
let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
const handlers: Map<EventType, Set<EventHandler>> = new Map();

export const useWebSocketStore = create<WebSocketStore>((set, get) => ({
  isConnected: false,
  lastEvent: null,
  reconnectCount: 0,

  connect: async (queryClient?: unknown) => {
    if (ws && ws.readyState === WebSocket.OPEN) return;

    const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

    // Get Firebase token
    let token = "";
    try {
      const user = auth.currentUser;
      if (user) {
        token = await user.getIdToken(false);
      }
    } catch (e) {
      console.warn("WS: Could not get auth token, connecting unauthenticated");
    }

    const url = `${WS_BASE}/api/v1/ws${token ? `?token=${token}` : ""}`;

    try {
      ws = new WebSocket(url);

      ws.onopen = () => {
        console.log("WebSocket connected");
        set({ isConnected: true, reconnectCount: 0 });
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketEvent = JSON.parse(event.data);
          set({ lastEvent: data });

          // Dispatch to registered handlers
          const eventHandlers = handlers.get(data.event_type);
          if (eventHandlers) {
            eventHandlers.forEach((handler) => handler(data));
          }

          // Dispatch to "all" handlers
          const allHandlers = handlers.get("*" as EventType);
          if (allHandlers) {
            allHandlers.forEach((handler) => handler(data));
          }

          // Auto-invalidate TanStack Query caches if queryClient provided
          if (queryClient) {
            const qc = queryClient as {
              invalidateQueries: (opts: { queryKey: string[] }) => void;
            };
            const invalidationMap: Partial<Record<string, string[]>> = {
              WorkflowUpdated: ["workflows"],
              TaskStatusChanged: ["workflows", "tasks"],
              NewHumanTask: ["tasks"],
              HumanTaskUpdated: ["tasks"],
              NewAuditEvent: ["audit"],
              EscalationTriggered: ["escalations", "workflows"],
            };

            const keysToInvalidate = invalidationMap[data.event_type];
            if (keysToInvalidate) {
              keysToInvalidate.forEach((key) => {
                qc.invalidateQueries({ queryKey: [key] });
              });
            }
          }
        } catch (e) {
          console.warn("WS: Could not parse event", e);
        }
      };

      ws.onerror = (error) => {
        console.warn("WebSocket error:", error);
      };

      ws.onclose = () => {
        set({ isConnected: false });
        ws = null;

        // Exponential backoff reconnect
        const reconnectCount = get().reconnectCount;
        const delay = Math.min(1000 * Math.pow(2, reconnectCount), 30000);
        console.log(`WS disconnected, reconnecting in ${delay}ms`);

        set({ reconnectCount: reconnectCount + 1 });

        if (reconnectTimeout) clearTimeout(reconnectTimeout);
        reconnectTimeout = setTimeout(() => {
          get().connect(queryClient);
        }, delay);
      };
    } catch (e) {
      console.error("WS: Connection failed", e);
    }
  },

  disconnect: () => {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
    set({ isConnected: false });
  },

  subscribe: (eventType: EventType, handler: EventHandler) => {
    if (!handlers.has(eventType)) {
      handlers.set(eventType, new Set());
    }
    handlers.get(eventType)!.add(handler);

    // Return unsubscribe function
    return () => {
      handlers.get(eventType)?.delete(handler);
    };
  },
}));
