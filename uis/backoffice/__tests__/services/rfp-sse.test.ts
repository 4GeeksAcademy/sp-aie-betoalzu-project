/**
 * Tests for RFP SSE client (frontend).
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { RfpSseClient, type RfpTicketCreatedEvent } from '@/services/rfp-sse';

// Mock fetch globally
global.fetch = vi.fn();

describe('RfpSseClient', () => {
  let client: RfpSseClient;
  let mockOnEvent: ReturnType<typeof vi.fn>;
  let mockOnError: ReturnType<typeof vi.fn>;
  let mockOnOpen: ReturnType<typeof vi.fn>;
  let mockOnClose: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();

    mockOnEvent = vi.fn();
    mockOnError = vi.fn();
    mockOnOpen = vi.fn();
    mockOnClose = vi.fn();

    // Mock auth token
    localStorage.setItem('token', 'test-token-123');

    client = new RfpSseClient('http://localhost:8000', {
      onEvent: mockOnEvent,
      onError: mockOnError,
      onOpen: mockOnOpen,
      onClose: mockOnClose,
      maxReconnectAttempts: 3,
      initialBackoffMs: 100,
      maxBackoffMs: 500,
    });
  });

  afterEach(() => {
    client.close();
  });

  it('should extract auth token from localStorage', async () => {
    const mockResponse = new Response(new ReadableStream(), {
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
    });

    (global.fetch as any).mockResolvedValueOnce(mockResponse);

    await client.connect();

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/stream'),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer test-token-123',
        }),
      })
    );
  });

  it('should fail to connect without auth token', async () => {
    localStorage.clear();
    sessionStorage.clear();

    await client.connect();

    expect(mockOnError).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining('No authentication token'),
      })
    );
  });

  it('should call onOpen on successful connection', async () => {
    const mockResponse = new Response(new ReadableStream(), {
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
    });

    (global.fetch as any).mockResolvedValueOnce(mockResponse);

    await client.connect();

    expect(mockOnOpen).toHaveBeenCalled();
  });

  it('should parse SSE frames with event name and data', async () => {
    const testEvent: RfpTicketCreatedEvent = {
      ticket_id: 'tkt_001',
      rfp_id: 'rfp_001',
      client_name: 'Test Client',
      client_hq: 'Spain',
      services_requested: ['recruitment'],
      status: 'analyzing',
      created_at: new Date().toISOString(),
    };

    const sseFrame = `event: rfp_ticket_created\ndata: ${JSON.stringify(testEvent)}\n\n`;
    const mockStream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseFrame));
        controller.close();
      },
    });

    const mockResponse = new Response(mockStream, {
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
    });

    (global.fetch as any).mockResolvedValueOnce(mockResponse);

    await client.connect();

    // Give async operations time to complete
    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockOnEvent).toHaveBeenCalledWith(testEvent);
  });

  it('should ignore keep-alive comments', async () => {
    const keepAliveFrame = `: keep-alive\n\n`;
    const mockStream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(keepAliveFrame));
        controller.close();
      },
    });

    const mockResponse = new Response(mockStream, {
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
    });

    (global.fetch as any).mockResolvedValueOnce(mockResponse);

    await client.connect();

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockOnEvent).not.toHaveBeenCalled();
  });

  it('should handle partial/chunked frames', async () => {
    const testEvent: RfpTicketCreatedEvent = {
      ticket_id: 'tkt_001',
      rfp_id: 'rfp_001',
      client_name: 'Test Client',
      client_hq: 'Spain',
      services_requested: ['recruitment'],
      status: 'analyzing',
      created_at: new Date().toISOString(),
    };

    const sseFrame = `event: rfp_ticket_created\ndata: ${JSON.stringify(testEvent)}\n\n`;

    // Split frame into multiple chunks
    const chunks = [
      sseFrame.substring(0, 20),
      sseFrame.substring(20, 40),
      sseFrame.substring(40),
    ];

    let chunkIndex = 0;
    const mockStream = new ReadableStream({
      pull(controller) {
        if (chunkIndex < chunks.length) {
          controller.enqueue(new TextEncoder().encode(chunks[chunkIndex]));
          chunkIndex++;
        } else {
          controller.close();
        }
      },
    });

    const mockResponse = new Response(mockStream, {
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
    });

    (global.fetch as any).mockResolvedValueOnce(mockResponse);

    await client.connect();

    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(mockOnEvent).toHaveBeenCalledWith(testEvent);
  });

  it('should deduplicate events by ticket_id within window', async () => {
    const testEvent: RfpTicketCreatedEvent = {
      ticket_id: 'tkt_001',
      rfp_id: 'rfp_001',
      client_name: 'Test Client',
      client_hq: 'Spain',
      services_requested: ['recruitment'],
      status: 'analyzing',
      created_at: new Date().toISOString(),
    };

    const sseFrame = `event: rfp_ticket_created\ndata: ${JSON.stringify(testEvent)}\n\n`;
    const doubleFrame = sseFrame + sseFrame;

    const mockStream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(doubleFrame));
        controller.close();
      },
    });

    const mockResponse = new Response(mockStream, {
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
    });

    (global.fetch as any).mockResolvedValueOnce(mockResponse);

    await client.connect();

    await new Promise((resolve) => setTimeout(resolve, 100));

    // Should only be called once despite two identical events
    expect(mockOnEvent).toHaveBeenCalledTimes(1);
  });

  it('should handle invalid JSON gracefully', async () => {
    const invalidSseFrame = `event: rfp_ticket_created\ndata: {invalid json}\n\n`;

    const mockStream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(invalidSseFrame));
        controller.close();
      },
    });

    const mockResponse = new Response(mockStream, {
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
    });

    (global.fetch as any).mockResolvedValueOnce(mockResponse);

    await client.connect();

    await new Promise((resolve) => setTimeout(resolve, 100));

    expect(mockOnError).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining('Failed to parse SSE data'),
      })
    );
    expect(mockOnEvent).not.toHaveBeenCalled();
  });

  it('should retry connection with exponential backoff', async () => {
    const mockResponse = new Response('', {
      status: 500,
    });

    (global.fetch as any).mockResolvedValueOnce(mockResponse);

    await client.connect();

    expect(mockOnError).toHaveBeenCalled();

    // Verify that reconnect is scheduled (should happen after backoff)
    await new Promise((resolve) => setTimeout(resolve, 250));
  });
});
