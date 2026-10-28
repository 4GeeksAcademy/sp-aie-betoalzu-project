"""Servicio de integración del agente de soporte con WebSocket streaming.

Maneja la invocación del agente con captura de eventos de token streaming.
"""

import asyncio
from typing import AsyncGenerator, Optional
from uuid import uuid4
from sqlmodel import Session

from services.agent.support import SupportAgent, get_support_agent
from services.pubsub import get_pubsub_broker
from services.chat_service import MessageService, ChatSessionService
from services.database import engine


async def stream_agent_response(
    agent: SupportAgent,
    question: str,
    session_id: str,
    message_id: str,
    conversation_id: Optional[str] = None,
    customer_id: Optional[str] = None,
    actor_id: str = "",
    actor_role: str = "",
) -> AsyncGenerator[dict, None]:
    """Ejecutar el agente y transmitir eventos de streaming de tokens.
    
    Publicará eventos en el canal pub/sub chat.{session_id}:
    - token_chunk: cada token generado
    - generation_completed: cuando termina
    - generation_interrupted: si se cancela
    
    Args:
        agent: Instancia del SupportAgent
        question: Pregunta del usuario
        session_id: ID de la sesión de chat
        message_id: ID del mensaje que generará la respuesta
        conversation_id: ID de conversación (opcional, derivado del session_id)
        customer_id: ID del cliente (opcional)
        actor_id: ID del actor (usuario)
        actor_role: Rol del actor
        
    Yields:
        Eventos de token a medida que se generan
    """
    pubsub = get_pubsub_broker()
    channel = f"chat.{session_id}"
    
    # Usar el thread_id derivado del session_id
    thread_id = f"chat:{session_id}"
    conversation = conversation_id or session_id
    
    try:
        # Inicializar el contador de tokens
        token_count = 0
        buffer = ""
        
        # Invocar el agente con streaming de eventos
        # LangGraph stream_events es un generador síncrono, así que lo ejecutamos en un executor
        loop = asyncio.get_event_loop()
        
        def get_stream_events():
            """Obtener stream de eventos del agente."""
            # Usar stream_events si está disponible, sino usar invoke
            if hasattr(agent.graph, "stream_events"):
                return agent.graph.stream_events(
                    {
                        "question": question,
                        "context": [],
                        "answer": "",
                        "error": None,
                        "run_id": f"ws_{uuid4().hex[:8]}",
                        "memory_context": [],
                        "conversation_id": conversation,
                        "customer_id": customer_id,
                        "actor_id": actor_id,
                        "actor_role": actor_role,
                        "response_composed": False,
                    },
                    {
                        "configurable": {"thread_id": thread_id},
                    },
                    version="v2",  # v2 incluye eventos de token
                )
            else:
                # Fallback: usar invoke y emular tokens
                result = agent.invoke(
                    question,
                    conversation_id=conversation,
                    customer_id=customer_id,
                    actor_id=actor_id,
                    actor_role=actor_role,
                )
                # Emular tokens de la respuesta
                return result.get("answer", "")
        
        # Ejecutar en thread pool para no bloquear
        events = await loop.run_in_executor(None, get_stream_events)
        
        # Procesar eventos
        if isinstance(events, str):
            # Fallback: respuesta simple, tokenizar
            answer = events
            tokens = answer.split()
            for token in tokens:
                token_count += 1
                await pubsub.publish(channel, {
                    "event": "token_chunk",
                    "data": {
                        "session_id": session_id,
                        "message_id": message_id,
                        "token": token + " ",
                        "sequence": token_count,
                    }
                })
                yield {"type": "token", "content": token}
            
            # Señalar fin
            await pubsub.publish(channel, {
                "event": "generation_completed",
                "data": {
                    "session_id": session_id,
                    "message_id": message_id,
                    "status": "completed",
                    "total_tokens": token_count,
                }
            })
        else:
            # Procesar eventos reales de LangGraph
            full_answer = ""
            for event in events:
                event_type = event.get("event")
                data = event.get("data", {})
                
                # Detectar cuando se genera un token (varía según LangGraph version)
                if event_type == "on_chat_model_stream":
                    # Evento de stream de modelo
                    chunk = data.get("chunk", {})
                    if hasattr(chunk, "content"):
                        token = chunk.content
                    elif isinstance(chunk, dict):
                        token = chunk.get("content", "")
                    else:
                        token = str(chunk)
                    
                    if token:
                        token_count += 1
                        full_answer += token
                        
                        await pubsub.publish(channel, {
                            "event": "token_chunk",
                            "data": {
                                "session_id": session_id,
                                "message_id": message_id,
                                "token": token,
                                "sequence": token_count,
                            }
                        })
                        yield {"type": "token", "content": token}
                
                elif event_type == "on_chain_end":
                    # Fin de la cadena/grafo
                    if data.get("output", {}).get("answer"):
                        full_answer = data["output"]["answer"]
            
            # Señalar fin
            await pubsub.publish(channel, {
                "event": "generation_completed",
                "data": {
                    "session_id": session_id,
                    "message_id": message_id,
                    "status": "completed",
                    "total_tokens": token_count,
                }
            })
            
    except asyncio.CancelledError:
        # Streaming cancelado por el usuario
        await pubsub.publish(channel, {
            "event": "generation_interrupted",
            "data": {
                "session_id": session_id,
                "message_id": message_id,
                "status": "interrupted",
                "tokens_shown": token_count,
            }
        })
        yield {"type": "interrupted"}
    except Exception as e:
        # Error durante el streaming
        await pubsub.publish(channel, {
            "event": "error",
            "data": {
                "code": 500,
                "message": f"Error generating response: {str(e)}",
            }
        })
        yield {"type": "error", "message": str(e)}


async def invoke_agent_for_chat(
    question: str,
    session_id: str,
    message_id: str,
    user_id: str,
    client_id: str,
    conversation_id: Optional[str] = None,
    customer_id: Optional[str] = None,
) -> None:
    """Invocar el agente y guardar la respuesta completa.
    
    Esta función:
    1. Obtiene el agente de soporte
    2. Invoca el agente con streaming
    3. Acumula la respuesta
    4. Guarda el mensaje completo en BD
    
    Args:
        question: Pregunta del usuario
        session_id: ID de la sesión
        message_id: ID del mensaje
        user_id: ID del usuario (del JWT)
        client_id: ID del cliente (del JWT)
        conversation_id: ID de conversación (opcional)
        customer_id: ID del cliente en el sistema (opcional)
    """
    agent = get_support_agent()
    
    with Session(engine) as db:
        message_service = MessageService(db)
        chat_service = ChatSessionService(db)
        
        try:
            # Acumular respuesta durante streaming
            full_response = ""
            
            async for event in stream_agent_response(
                agent,
                question,
                session_id,
                message_id,
                conversation_id=conversation_id,
                customer_id=customer_id,
                actor_id=user_id,
                actor_role="customer",
            ):
                if event.get("type") == "token":
                    full_response += event.get("content", "")
                elif event.get("type") == "interrupted":
                    # Marcar como interrumpido
                    await message_service.update_message(
                        message_id,
                        text=full_response,
                        status="interrupted",
                        tokens_received=len(full_response.split()),
                    )
                    return
                elif event.get("type") == "error":
                    # Guardar error
                    await message_service.update_message(
                        message_id,
                        text="",
                        status="pending",
                    )
                    return
            
            # Guardar respuesta completa
            await message_service.update_message(
                message_id,
                text=full_response,
                status="completed",
            )
            
            # Actualizar timestamp de sesión
            await chat_service.update_session_status(session_id, "active")
            
        except Exception as e:
            # Error no capturado
            await message_service.update_message(message_id, text="", status="pending")
