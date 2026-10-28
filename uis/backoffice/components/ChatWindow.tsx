'use client'

import { useState, useRef, useEffect } from 'react'
import { useChatWebSocket, ChatMessageState } from '@/services/chat-ws'

interface ChatWindowProps {
  sessionId: string
}

/**
 * Componente React para ventana de chat con streaming en tiempo real.
 * 
 * Características:
 * - Renderizado progresivo de tokens (escriben a medida que llegan)
 * - Botón de interrumpción visible durante generación
 * - Soporte para múltiples turnos (usuario → asistente → usuario...)
 * - Indicador de conexión
 * - Manejo automático de reconexión
 */
export function ChatWindow({ sessionId }: ChatWindowProps) {
  const { connected, messages, error, isGenerating, sendMessage, interrupt } = useChatWebSocket(sessionId)

  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Auto-scroll al último mensaje
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim() || !connected || isGenerating) {
      return
    }

    const text = inputValue.trim()
    setInputValue('')
    setIsLoading(true)

    try {
      await sendMessage(text)
    } finally {
      setIsLoading(false)
    }
  }

  const handleInterrupt = async () => {
    if (!inputValue.trim()) {
      return
    }

    const newInput = inputValue.trim()
    setInputValue('')

    try {
      await interrupt(newInput)
    } catch (err) {
      console.error('Failed to interrupt:', err)
    }
  }

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b">
        <h2 className="text-lg font-semibold text-gray-800">Chat de Soporte</h2>
        <div className="flex items-center gap-2">
          <div className={`w-3 h-3 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-sm text-gray-600">{connected ? 'Conectado' : 'Desconectado'}</span>
        </div>
      </div>

      {/* Mensajes */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            No hay mensajes aún. Comienza a conversar.
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.message_id}
            className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                msg.sender === 'user'
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 text-gray-900'
              }`}
            >
              {/* Renderizar texto acumulado o final */}
              <p className="text-sm break-words whitespace-pre-wrap">
                {msg.displayText || msg.text}
              </p>

              {/* Indicadores de estado */}
              <div className="flex items-center gap-2 mt-1 text-xs">
                {msg.status === 'pending' && (
                  <span className="text-gray-500">⏳ Generando...</span>
                )}
                {msg.status === 'interrupted' && (
                  <span className="text-orange-600">⚠️ Interrumpido ({msg.tokens_shown || 0} tokens)</span>
                )}
                {msg.status === 'completed' && msg.sender === 'assistant' && (
                  <span className="text-gray-600">✓ Completado</span>
                )}
              </div>
            </div>
          </div>
        ))}

        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input y controles */}
      <div className="border-t p-4 bg-gray-50">
        {isGenerating && (
          <div className="mb-3 flex gap-2">
            <button
              onClick={handleInterrupt}
              disabled={!inputValue.trim()}
              className="px-4 py-2 bg-orange-500 text-white rounded hover:bg-orange-600 disabled:opacity-50 text-sm font-medium"
            >
              Interrumpir y preguntar
            </button>
            <span className="text-sm text-gray-600 flex items-center">
              Generando respuesta...
            </span>
          </div>
        )}

        <form onSubmit={handleSendMessage} className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={connected ? 'Escribe tu pregunta...' : 'Desconectado...'}
            disabled={!connected || isLoading}
            className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
          />
          <button
            type="submit"
            disabled={!connected || isLoading || !inputValue.trim() || isGenerating}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {isLoading ? 'Enviando...' : 'Enviar'}
          </button>
        </form>
      </div>
    </div>
  )
}
