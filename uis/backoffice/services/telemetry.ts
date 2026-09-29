'use client';

export const TELEMETRY_SCHEMA_VERSION = '1.0';
const TELEMETRY_QUEUE_KEY = 'nexova_telemetry_queue';
const MAX_BATCH_SIZE = 20;
const FLUSH_INTERVAL_MS = 10000;
const MAX_RETRIES = 3;
const ENDPOINT = process.env.NEXT_PUBLIC_TELEMETRY_ENDPOINT || 'http://localhost:8000/telemetry/events';

export type TelemetryEventEnvelope = {
  eventId: string;
  timestamp: string;
  sessionId: string;
  userId: string;
  event_type: string;
  schemaVersion: string;
  requestId: string;
  properties: Record<string, unknown>;
};

type QueuedTelemetryEvent = TelemetryEventEnvelope & { _retryCount?: number };

function getOrCreateSessionId(): string {
  const key = 'nexova_session_id';
  const existing = window.sessionStorage.getItem(key);
  if (existing) return existing;
  const newId = crypto.randomUUID();
  window.sessionStorage.setItem(key, newId);
  return newId;
}

function getUserId(): string {
  const storedUserId = window.localStorage.getItem('nexova_user_id');
  if (storedUserId) return storedUserId;

  const token = window.localStorage.getItem('nexova_token');
  if (!token) return 'anonymous';

  try {
    const payload = token.split('.')[1];
    if (!payload) return 'anonymous';
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/');
    const decoded = JSON.parse(atob(normalized));
    const userId = decoded.sub || decoded.userId || decoded.user_id || 'anonymous';
    if (userId !== 'anonymous') {
      window.localStorage.setItem('nexova_user_id', String(userId));
    }
    return String(userId);
  } catch {
    return 'anonymous';
  }
}

function readQueue(): QueuedTelemetryEvent[] {
  const raw = window.localStorage.getItem(TELEMETRY_QUEUE_KEY);
  if (!raw) return [];

  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeQueue(events: QueuedTelemetryEvent[]) {
  window.localStorage.setItem(TELEMETRY_QUEUE_KEY, JSON.stringify(events));
  const telemetryGlobal = globalThis as typeof globalThis & {
    __telemetry_test_queue__?: QueuedTelemetryEvent[];
  };
  telemetryGlobal.__telemetry_test_queue__ = events;
}

function makeRequestId(): string {
  return crypto.randomUUID();
}

function buildEnvelope(eventType: string, properties: Record<string, unknown>): TelemetryEventEnvelope {
  const now = new Date();
  return {
    eventId: crypto.randomUUID(),
    timestamp: now.toISOString(),
    sessionId: getOrCreateSessionId(),
    userId: getUserId(),
    event_type: eventType,
    schemaVersion: TELEMETRY_SCHEMA_VERSION,
    requestId: makeRequestId(),
    properties,
  };
}

function queuePush(event: TelemetryEventEnvelope) {
  const nextQueue = [...readQueue(), event];
  writeQueue(nextQueue);
  if (nextQueue.length >= MAX_BATCH_SIZE) {
    void flushQueue();
  }
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function stripRetryMetadata(event: QueuedTelemetryEvent): TelemetryEventEnvelope {
  return Object.fromEntries(
    Object.entries(event).filter(([key]) => key !== '_retryCount'),
  ) as TelemetryEventEnvelope;
}

async function sendBatch(batch: QueuedTelemetryEvent[]) {
  const payload = { events: batch.map((event) => stripRetryMetadata(event)) };

  const response = await fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    keepalive: true,
  });

  if (!response.ok) {
    throw new Error(`Telemetry batch rejected with status ${response.status}`);
  }
}

export async function flushQueue(): Promise<void> {
  const queue = readQueue();
  if (queue.length === 0) return;

  const batch = [...queue];
  const attempts = batch[0]?._retryCount ?? 0;

  try {
    await sendBatch(batch);
    writeQueue([]);
  } catch (error) {
    const retryCount = Math.max(attempts + 1, 1);
    if (retryCount <= MAX_RETRIES) {
      const nextQueue = batch.map((item) => ({ ...item, _retryCount: retryCount }));
      writeQueue(nextQueue);
      const backoffMs = 500 * 2 ** (retryCount - 1);
      await delay(backoffMs);
      await flushQueue();
      return;
    }

    writeQueue([]);
    console.warn('Telemetry batch discarded after retries:', error);
  }
}

let timer: number | null = null;

function scheduleFlush() {
  if (timer) {
    window.clearTimeout(timer);
  }

  timer = window.setTimeout(() => {
    void flushQueue();
  }, FLUSH_INTERVAL_MS);
}

export function track(eventType: string, properties: Record<string, unknown> = {}): void {
  const envelope = buildEnvelope(eventType, properties);
  queuePush(envelope);
  scheduleFlush();
}

if (typeof window !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') {
      if (navigator.sendBeacon) {
        const queue = readQueue();
        if (!queue.length) return;
        const payload = { events: queue.map((event) => stripRetryMetadata(event)) };
        navigator.sendBeacon(ENDPOINT, JSON.stringify(payload));
      }
      void flushQueue();
    }
  });

  window.addEventListener('beforeunload', () => {
    if (navigator.sendBeacon) {
      const queue = readQueue();
      if (!queue.length) return;
      const payload = { events: queue.map((event) => stripRetryMetadata(event)) };
      navigator.sendBeacon(ENDPOINT, JSON.stringify(payload));
    }
  });
}
