'use client'

import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'
import { ChatWindow } from '@/components/ChatWindow'
import { useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'

/**
 * Página de chat en tiempo real.
 * Usa URL params para obtener sessionId: /chat?sessionId=XXX
 */
export default function ChatPage() {
  const router = useRouter()
  const { user } = useAuth()
  const searchParams = useSearchParams()
  const [sessionId, setSessionId] = useState<string | null>(null)

  useEffect(() => {
    // Obtener sessionId de URL
    const sid = searchParams.get('sessionId')
    if (!sid) {
      // Generar uno nuevo si no existe
      const newSessionId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
      setSessionId(newSessionId)
      // Opcionalmente, actualizar URL
      router.push(`/chat?sessionId=${newSessionId}`)
    } else {
      setSessionId(sid)
    }
  }, [searchParams, router])

  if (!user) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Acceso denegado</h1>
          <p className="text-gray-600 mb-6">Debes iniciar sesión para usar el chat</p>
          <a
            href="/login"
            className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            Ir a login
          </a>
        </div>
      </div>
    )
  }

  if (!sessionId) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <h1 className="text-2xl font-bold">Cargando...</h1>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-2xl mx-auto h-screen flex flex-col">
        {/* Header */}
        <div className="mb-4">
          <h1 className="text-3xl font-bold text-gray-800">Chat de Soporte en Tiempo Real</h1>
          <p className="text-gray-600 mt-2">
            Sesión: <code className="bg-gray-200 px-2 py-1 rounded text-sm">{sessionId}</code>
          </p>
          <p className="text-gray-600 mt-1">Usuario: {user.email}</p>
        </div>

        {/* Chat window */}
        <div className="flex-1 min-h-0">
          <ChatWindow sessionId={sessionId} />
        </div>

        {/* Footer */}
        <div className="mt-4 text-center text-sm text-gray-600">
          Los mensajes se almacenan en el servidor. Esta sesión es persistente.
        </div>
      </div>
    </div>
  )
}
