/**
 * WebSocket client for real-time chat streaming with token-by-token rendering.
 * 
 * Conecta a /ws/chat/{sessionId} y maneja:
 * - Streaming de tokens
 * - Interrupción de generación
 * - Reconexión automática con backoff exponencial
 * - Session snapshot tras reconexión
 */

import { JWT_TOKEN_KEY } from '@/lib/auth-context'

export interface ChatMessage {
  message_id: string
  sender: 'user' | 'assistant'
  text: string
  status: 'pending' | 'completed' | 'interrupted'
  tokens_shown?: number
  created_at?: string
}

export interface ChatSessionSnapshot {
  session_id: string
  checkpoint_id: string | null
  messages: ChatMessage[]
}

export type WebSocketEvent =
  | { event: 'session_snapshot'; data: ChatSessionSnapshot }
  | { event: 'token_chunk'; data: { session_id: string; message_id: string; token: string; sequence: number } }
  | { event: 'generation_completed'; data: { session_id: string; message_id: string; status: string; total_tokens: number } }
  | { event: 'generation_interrupted'; data: { session_id: string; message_id: string; status: string; tokens_shown: number } }
  | { event: 'user_message'; data: { session_id: string; message_id: string; text: string } }
  | { event: 'error'; data: { code: number; message: string } }

export class ChatWebSocketClient {
  private ws: WebSocket | null = null
  private sessionId: string
  private jwtToken: string | null
  private messageQueue: Map<string, string> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 10
  private initialReconnectDelay = 1000 // 1s
  private maxReconnectDelay = 30000 // 30s
  private reconnectDelay = this.initialReconnectDelay
  private reconnectJitter = 0.1 // 10% jitter
  private abortControllers: Map<string, AbortController> = new Map()
  
  private onSessionSnapshot: ((snapshot: ChatSessionSnapshot) => void) | null = null
  private onTokenChunk: ((data: { message_id: string; token: string; sequence: number }) => void) | null = null
  private onGenerationCompleted: ((data: { message_id: string; total_tokens: number }) => void) | null = null
  private onGenerationInterrupted: ((data: { message_id: string; tokens_shown: number }) => void) | null = null
  private onUserMessage: ((data: { message_id: string; text: string }) => void) | null = null
  private onError: ((error: { code: number; message: string }) => void) | null = null
  private onConnectionChange: ((connected: boolean) => void) | null = null

  constructor(sessionId: string, jwtToken?: string) {
    this.sessionId = sessionId
    this.jwtToken = jwtToken || this._getStoredJWT()
  }

  private _getStoredJWT(): string | null {
    if (typeof localStorage === 'undefined') return null
    return localStorage.getItem(JWT_TOKEN_KEY)
  }

  /**
   * Conectar al WebSocket.
   * Si ya existe una conexión, la reutiliza.
   */
  async connect(): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) {
      return // Ya conectado
    }

    return new Promise((resolve, reject) => {
      try {
        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
        const host = window.location.host
        const url = `${protocol}://${host}/ws/chat/${this.sessionId}?token=${encodeURIComponent(this.jwtToken || '')}`

        this.ws = new WebSocket(url)
        this.ws.onopen = () => {
          this.reconnectAttempts = 0
          this.reconnectDelay = this.initialReconnectDelay
          this._notifyConnectionChange(true)
          resolve()
        }
        this.ws.onmessage = (event) => {
          this._handleMessage(event.data)
        }
        this.ws.onerror = (event) => {
          console.error('WebSocket error:', event)
          reject(new Error('WebSocket connection failed'))
        }
        this.ws.onclose = () => {
          this._notifyConnectionChange(false)
          this._scheduleReconnect()
        }
      } catch (error) {
        reject(error)
      }
    })
  }

  /**
   * Desconectar del WebSocket.
   */
  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  /**
   * Enviar un mensaje de usuario.
   * Retorna el message_id que se asignará al mensaje.
   */
  async sendUserMessage(text: string): Promise<string> {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected')
    }

    const messageId = `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    
    this.ws.send(
      JSON.stringify({
        event: 'user_message',
        data: {
          session_id: this.sessionId,
          text: text,
        },
      })
    )

    return messageId
  }

  /**
   * Interrumpir la generación actual y enviar un nuevo input.
   */
  async interruptAndAsk(newInput: string): Promise<void> {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected')
    }

    // Cancelar cualquier tarea en curso
    this._cancelAllGenerations()

    this.ws.send(
      JSON.stringify({
        event: 'interrupt_requested',
        data: {
          session_id: this.sessionId,
          new_input: newInput,
        },
      })
    )
  }

  /**
   * Registrar callback para session snapshot.
   */
  onSnapshot(callback: (snapshot: ChatSessionSnapshot) => void): void {
    this.onSessionSnapshot = callback
  }

  /**
   * Registrar callback para token chunks.
   */
  onToken(callback: (data: { message_id: string; token: string; sequence: number }) => void): void {
    this.onTokenChunk = callback
  }

  /**
   * Registrar callback para generación completada.
   */
  onComplete(callback: (data: { message_id: string; total_tokens: number }) => void): void {
    this.onGenerationCompleted = callback
  }

  /**
   * Registrar callback para generación interrumpida.
   */
  onInterrupted(callback: (data: { message_id: string; tokens_shown: number }) => void): void {
    this.onGenerationInterrupted = callback
  }

  /**
   * Registrar callback para usuario_message.
   */
  onUserMsg(callback: (data: { message_id: string; text: string }) => void): void {
    this.onUserMessage = callback
  }

  /**
   * Registrar callback para errores.
   */
  onErrorEvent(callback: (error: { code: number; message: string }) => void): void {
    this.onError = callback
  }

  /**
   * Registrar callback para cambios de conexión.
   */
  onConnectionStatusChange(callback: (connected: boolean) => void): void {
    this.onConnectionChange = callback
  }

  // ========================================================================
  // Private methods
  // ========================================================================

  private _handleMessage(data: string): void {
    try {
      const event: WebSocketEvent = JSON.parse(data)

      switch (event.event) {
        case 'session_snapshot':
          this.onSessionSnapshot?.(event.data)
          break
        case 'token_chunk':
          this.onTokenChunk?.(event.data)
          break
        case 'generation_completed':
          this.onGenerationCompleted?.(event.data)
          break
        case 'generation_interrupted':
          this.onGenerationInterrupted?.(event.data)
          break
        case 'user_message':
          this.onUserMessage?.(event.data)
          break
        case 'error':
          this.onError?.(event.data)
          break
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error)
    }
  }

  private _cancelAllGenerations(): void {
    this.abortControllers.forEach((controller) => {
      controller.abort()
    })
    this.abortControllers.clear()
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached')
      this.onError?.({ code: 1000, message: 'Connection lost after max retries' })
      return
    }

    this.reconnectAttempts++

    // Exponential backoff with jitter
    const jitterFactor = 1 + (Math.random() * this.reconnectJitter - this.reconnectJitter / 2)
    const delay = Math.min(this.reconnectDelay * jitterFactor, this.maxReconnectDelay)

    console.log(`Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`)

    setTimeout(() => {
      this.connect().catch((error) => {
        console.error('Reconnection failed:', error)
        this._scheduleReconnect()
      })
    }, delay)

    // Increase delay for next attempt
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay)
  }

  private _notifyConnectionChange(connected: boolean): void {
    this.onConnectionChange?.(connected)
  }
}

/**
 * Hook de React para usar el cliente de chat WebSocket.
 * 
 * Uso:
 * ```
 * const { client, connected, messages, error } = useChatWebSocket(sessionId);
 * 
 * const handleSendMessage = async (text) => {
 *   await client.sendUserMessage(text);
 * };
 * ```
 */
import { useEffect, useRef, useState, useCallback } from 'react'

export interface ChatMessageState extends ChatMessage {
  displayText?: string // Texto acumulado de tokens para renderizado
}

export function useChatWebSocket(sessionId: string) {
  const clientRef = useRef<ChatWebSocketClient | null>(null)
  const [connected, setConnected] = useState(false)
  const [messages, setMessages] = useState<ChatMessageState[]>([])
  const [error, setError] = useState<string | null>(null)
  const [isGenerating, setIsGenerating] = useState(false)
  const currentGeneratingMessageIdRef = useRef<string | null>(null)

  // Inicializar cliente
  useEffect(() => {
    const client = new ChatWebSocketClient(sessionId)
    clientRef.current = client

    client.onConnectionStatusChange((isConnected) => {
      setConnected(isConnected)
    })

    client.onSnapshot((snapshot) => {
      setMessages(
        snapshot.messages.map((msg) => ({
          ...msg,
          displayText: msg.text,
        }))
      )
    })

    client.onToken(({ message_id, token }) => {
      setMessages((prev) => {
        return prev.map((msg) => {
          if (msg.message_id === message_id) {
            return {
              ...msg,
              displayText: (msg.displayText || '') + token,
            }
          }
          return msg
        })
      })
    })

    client.onComplete(({ message_id }) => {
      setIsGenerating(false)
      currentGeneratingMessageIdRef.current = null
      
      setMessages((prev) => {
        return prev.map((msg) => {
          if (msg.message_id === message_id) {
            return { ...msg, status: 'completed', text: msg.displayText || msg.text }
          }
          return msg
        })
      })
    })

    client.onInterrupted(({ message_id, tokens_shown }) => {
      setIsGenerating(false)
      currentGeneratingMessageIdRef.current = null
      
      setMessages((prev) => {
        return prev.map((msg) => {
          if (msg.message_id === message_id) {
            return {
              ...msg,
              status: 'interrupted',
              text: msg.displayText || msg.text,
              tokens_shown,
            }
          }
          return msg
        })
      })
    })

    client.onUserMsg(({ message_id, text }) => {
      // El servidor siempre confirma el mensaje del usuario
      // Aquí podemos actualizar si es necesario
    })

    client.onErrorEvent(({ code, message }) => {
      setError(message)
    })

    // Conectar
    client.connect().catch((err) => {
      setError(err.message)
    })

    return () => {
      client.disconnect()
    }
  }, [sessionId])

  const sendMessage = useCallback(
    async (text: string) => {
      if (!clientRef.current?.['ws'] || !connected) {
        setError('Not connected')
        return
      }

      try {
        const messageId = await clientRef.current.sendUserMessage(text)
        setIsGenerating(true)
        currentGeneratingMessageIdRef.current = messageId
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send message')
      }
    },
    [connected]
  )

  const interrupt = useCallback(
    async (newInput: string) => {
      if (!clientRef.current) {
        setError('Client not initialized')
        return
      }

      try {
        await clientRef.current.interruptAndAsk(newInput)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to interrupt')
      }
    },
    []
  )

  return {
    client: clientRef.current,
    connected,
    messages,
    error,
    isGenerating,
    sendMessage,
    interrupt,
  }
}
