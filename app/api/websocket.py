import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.event_bus import event_bus, WebSocketSubscriber

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[WS DEBUG] Nova conexão WebSocket aceita em /ws")
    logger.info("WebSocket connection accepted.")
    
    subscriber = WebSocketSubscriber(websocket)
    subscribed_channels = set()
    
    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")
            channel = data.get("channel")
            
            if not action or not channel:
                logger.warning(f"Invalid message format received on WebSocket: {data}")
                continue
                
            if action == "subscribe":
                if channel not in subscribed_channels:
                    print(f"[WS DEBUG] Inscrição realizada no canal '{channel}'")
                    event_bus.register(channel, subscriber)
                    subscribed_channels.add(channel)
                    logger.info(f"WebSocket client subscribed to channel: {channel}")
            elif action == "unsubscribe":
                if channel in subscribed_channels:
                    print(f"[WS DEBUG] Desinscrição realizada do canal '{channel}'")
                    event_bus.unregister(channel, subscriber)
                    subscribed_channels.discard(channel)
                    logger.info(f"WebSocket client unsubscribed from channel: {channel}")
            else:
                logger.warning(f"Unknown action: {action}")
                
    except WebSocketDisconnect:
        print("[WS DEBUG] Cliente desconectado do WebSocket.")
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        print(f"[WS DEBUG] Erro na sessão WebSocket: {e}")
        logger.error(f"Error in WebSocket session: {e}", exc_info=True)
    finally:
        # Cleanup all subscriptions for this subscriber
        print(f"[WS DEBUG] Limpando inscrições ativas do cliente que desconectou: {subscribed_channels}")
        for channel in subscribed_channels:
            event_bus.unregister(channel, subscriber)
        logger.info("WebSocket subscription cleanup completed.")
