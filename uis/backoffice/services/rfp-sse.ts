/**
 * SSE (Server-Sent Events) client for real-time RFP ticket notifications.
 *
 * Handles:
 * - Connection with JWT authentication
 * - Incremental SSE frame parsing supporting partial chunks
 * - Automatic reconnection with exponential backoff + jitter
 * - JSON validation
 * - Deduplication by ticket_id
 */

export interface RfpTicketCreatedEvent {
  ticket_id: string;
  rfp_id: string;
  client_name: string | null;
  client_hq: string | null;
  services_requested: string[];
  status: string;
  created_at: string;
}

export type RfpSseEventHandler = (event: RfpTicketCreatedEvent) => void;

interface SseStreamConfig {
  onEvent: RfpSseEventHandler;
  onError?: (error: Error) => void;
  onOpen?: () => void;
  onClose?: () => void;
  maxReconnectAttempts?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
}

/**
 * SSE client that parses incremental frames and handles reconnection.
 * Deduplicates events by ticket_id using a Set.
 */
export class RfpSseClient {
  private url: string;
  private config: Required<SseStreamConfig>;
  private reader: ReadableStreamDefaultReader<Uint8Array> | null = null;
  private response: Response | null = null;
  private reconnectAttempts = 0;
  private isConnecting = false;
  private isClosing = false;
  private reconnectTimeout: NodeJS.Timeout | null = null;
  private recentTicketIds = new Set<string>();
  private recentTicketIdTimeout: NodeJS.Timeout | null = null;
  private deduplicationWindowMs = 5000; // 5 seconds

  constructor(url: string, config: SseStreamConfig) {
    this.url = url;
    this.config = {
      maxReconnectAttempts: config.maxReconnectAttempts ?? 10,
      initialBackoffMs: config.initialBackoffMs ?? 1000,
      maxBackoffMs: config.maxBackoffMs ?? 30000,
      ...config,
    };
  }

  /**
   * Connect to the SSE stream.
   */
  async connect(): Promise<void> {
    if (this.isConnecting || this.reader) {
      return;
    }

    this.isConnecting = true;

    try {
      const token = this.getAuthToken();
      if (!token) {
        throw new Error("No authentication token found");
      }

      this.response = await fetch(this.url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!this.response.ok) {
        throw new Error(
          `HTTP ${this.response.status}: ${this.response.statusText}`
        );
      }

      this.reader = this.response.body?.getReader();
      if (!this.reader) {
        throw new Error("Response body is not readable");
      }

      this.reconnectAttempts = 0;
      this.config.onOpen?.();
      this.isConnecting = false;

      await this.readStream();
    } catch (error) {
      this.isConnecting = false;
      const err = error instanceof Error ? error : new Error(String(error));
      this.config.onError?.(err);

      if (!this.isClosing) {
        this.scheduleReconnect();
      }
    }
  }

  /**
   * Close the connection gracefully.
   */
  close(): void {
    this.isClosing = true;

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }

    if (this.recentTicketIdTimeout) {
      clearTimeout(this.recentTicketIdTimeout);
      this.recentTicketIdTimeout = null;
    }

    if (this.reader) {
      this.reader.cancel();
      this.reader = null;
    }

    if (this.response) {
      this.response = null;
    }

    this.config.onClose?.();
  }

  /**
   * Schedule a reconnection attempt with exponential backoff + jitter.
   */
  private scheduleReconnect(): void {
    if (this.isClosing || this.reconnectAttempts >= this.config.maxReconnectAttempts) {
      if (this.reconnectAttempts >= this.config.maxReconnectAttempts) {
        const err = new Error("Max reconnection attempts reached");
        this.config.onError?.(err);
      }
      return;
    }

    this.reconnectAttempts++;
    const backoff = Math.min(
      this.config.initialBackoffMs * Math.pow(2, this.reconnectAttempts - 1),
      this.config.maxBackoffMs
    );
    const jitter = Math.random() * 0.1 * backoff;
    const delay = backoff + jitter;

    this.reconnectTimeout = setTimeout(() => {
      if (!this.isClosing) {
        this.connect();
      }
    }, delay);
  }

  /**
   * Read and parse frames from the SSE stream.
   * Handles partial chunks and multi-line data fields.
   */
  private async readStream(): Promise<void> {
    if (!this.reader) return;

    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (!this.isClosing) {
        const { done, value } = await this.reader.read();

        if (done) {
          if (buffer.trim()) {
            this.parseFrame(buffer);
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        // Process complete frames (end with double newline)
        const frames = buffer.split("\n\n");
        buffer = frames.pop() || "";

        for (const frame of frames) {
          if (frame.trim()) {
            this.parseFrame(frame);
          }
        }
      }
    } catch (error) {
      if (!this.isClosing) {
        const err = error instanceof Error ? error : new Error(String(error));
        this.config.onError?.(err);
        this.scheduleReconnect();
      }
    }
  }

  /**
   * Parse a single SSE frame.
   * Format:
   *   event: rfp_ticket_created
   *   data: {...json...}
   *
   * or:
   *   : keep-alive comment
   */
  private parseFrame(frame: string): void {
    const lines = frame.split("\n");
    let eventType = "";
    let dataLines: string[] = [];

    for (const line of lines) {
      if (line.startsWith(":")) {
        // Comment/keep-alive, ignore
        continue;
      }

      if (line.startsWith("event:")) {
        eventType = line.slice(6).trim();
      } else if (line.startsWith("data:")) {
        dataLines.push(line.slice(5).trim());
      }
    }

    // Ignore keep-alive events
    if (eventType === "keep-alive") {
      return;
    }

    if (eventType === "rfp_ticket_created" && dataLines.length > 0) {
      const dataString = dataLines.join("\n");
      try {
        const data = JSON.parse(dataString) as RfpTicketCreatedEvent;

        // Deduplication by ticket_id
        if (this.recentTicketIds.has(data.ticket_id)) {
          return;
        }

        this.recentTicketIds.add(data.ticket_id);
        if (this.recentTicketIdTimeout) {
          clearTimeout(this.recentTicketIdTimeout);
        }
        this.recentTicketIdTimeout = setTimeout(() => {
          this.recentTicketIds.clear();
        }, this.deduplicationWindowMs);

        this.config.onEvent(data);
      } catch (error) {
        const err = error instanceof Error ? error : new Error(String(error));
        this.config.onError?.(new Error(`Failed to parse SSE data: ${err.message}`));
      }
    }
  }

  /**
   * Get the authentication token from localStorage or session.
   */
  private getAuthToken(): string | null {
    try {
      return localStorage.getItem("token") || sessionStorage.getItem("token");
    } catch {
      return null;
    }
  }
}

/**
 * Create an SSE client and return the instance.
 */
export function createRfpSseClient(
  baseUrl: string,
  config: SseStreamConfig
): RfpSseClient {
  const url = `${baseUrl}/rfp-intake/stream`;
  return new RfpSseClient(url, config);
}
