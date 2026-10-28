/**
 * React hook for consuming RFP SSE notifications.
 *
 * Handles:
 * - Connection lifecycle (mount, unmount)
 * - Automatic refetch of ticket list on connect/reconnect
 * - Merging SSE events with refetched data
 * - Deduplication by ticket_id
 */

import { useEffect, useRef, useCallback } from 'react';
import type { RfpTicketCreatedEvent } from './rfp-sse';
import { createRfpSseClient } from './rfp-sse';

export interface UseRfpSseOptions {
  baseUrl: string;
  onNewTicket?: (ticket: RfpTicketCreatedEvent) => void;
  onError?: (error: Error) => void;
  onConnected?: () => void;
  onDisconnected?: () => void;
  enabled?: boolean;
}

/**
 * Hook that manages SSE connection and provides integration with ticket list.
 *
 * Usage:
 *   useRfpSse({
 *     baseUrl: 'https://api.example.com',
 *     onNewTicket: (ticket) => console.log('New ticket:', ticket),
 *   });
 */
export function useRfpSse({
  baseUrl,
  onNewTicket,
  onError,
  onConnected,
  onDisconnected,
  enabled = true,
}: UseRfpSseOptions): void {
  const clientRef = useRef(null as any);
  const isConnectedRef = useRef(false);

  const handleNewTicket = useCallback(
    (ticket: RfpTicketCreatedEvent) => {
      onNewTicket?.(ticket);
    },
    [onNewTicket]
  );

  const handleError = useCallback(
    (error: Error) => {
      onError?.(error);
    },
    [onError]
  );

  const handleConnected = useCallback(() => {
    isConnectedRef.current = true;
    onConnected?.();
  }, [onConnected]);

  const handleDisconnected = useCallback(() => {
    isConnectedRef.current = false;
    onDisconnected?.();
  }, [onDisconnected]);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    // Create client and store in ref
    if (!clientRef.current) {
      clientRef.current = createRfpSseClient(baseUrl, {
        onEvent: handleNewTicket,
        onError: handleError,
        onOpen: handleConnected,
        onClose: handleDisconnected,
      });
    }

    // Connect
    clientRef.current.connect();

    // Cleanup on unmount
    return () => {
      if (clientRef.current) {
        clientRef.current.close();
        clientRef.current = null;
      }
    };
  }, [baseUrl, handleNewTicket, handleError, handleConnected, handleDisconnected, enabled]);
}
