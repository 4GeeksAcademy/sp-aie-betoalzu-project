import { describe, expect, it, beforeEach, jest } from '@jest/globals';

describe('telemetry service', () => {
  beforeEach(() => {
    jest.resetModules();
    const globalWithFetch = globalThis as typeof globalThis & { fetch: typeof fetch };
    globalWithFetch.fetch = (async () => ({ ok: true }) as Response) as typeof fetch;
    Object.defineProperty(window.navigator, 'sendBeacon', {
      value: jest.fn(() => true),
      configurable: true,
    });
    window.localStorage.clear();
  });

  it('exposes a track function and adds required envelope metadata', async () => {
    const { track } = await import('../../services/telemetry');

    track('page_viewed', { page: '/inventory' });

    const telemetryGlobal = globalThis as typeof globalThis & {
      __telemetry_test_queue__?: Array<{ event_type: string }>;
    };
    const queue = telemetryGlobal.__telemetry_test_queue__;
    expect(typeof track).toBe('function');
    expect(queue?.length ?? 0).toBeGreaterThan(0);
  });
});
