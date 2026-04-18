import argparse
import asyncio
import json
import os
from typing import Any, Dict, Optional
import websockets
from websockets.server import WebSocketServerProtocol
rooms: Dict[str, Dict[str, Optional[WebSocketServerProtocol]]] = {}
def _get_peer(room_id: str, ws: WebSocketServerProtocol) -> Optional[WebSocketServerProtocol]:
    r = rooms.get(room_id)
    if not r:
        return None
    if r.get("host") is ws:
        return r.get("guest")
    if r.get("guest") is ws:
        return r.get("host")
    return None
async def _notify_peer(
    room_id: str, ws: WebSocketServerProtocol, obj: dict[str, Any]
) -> None:
    peer = _get_peer(room_id, ws)
    if peer is None:
        return
    try:
        await peer.send(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    except Exception:
        pass
async def handler(ws: WebSocketServerProtocol) -> None:
    room_id: Optional[str] = None
    try:
        async for message in ws:
            if isinstance(message, bytes):
                message = message.decode("utf-8")
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue
            action_raw = data.get("action")
            action = (
                str(action_raw).strip().lower() if action_raw is not None else ""
            )
            gid = data.get("game_id") or data.get("gameId")
            if isinstance(gid, str):
                gid = gid.strip().upper()
            else:
                gid = None
            join_like = action in (
                "join",
                "register",
                "connect",
                "enter",
                "handshake",
            )
            if join_like and gid:
                room_id = gid
                room = rooms.setdefault(
                    room_id, {"host": None, "guest": None}  # type: ignore[arg-type]
                )
                is_host = bool(data.get("host"))
                slot = "host" if is_host else "guest"
                old = room.get(slot)
                if old is not None and old is not ws:
                    try:
                        await old.close(code=1000, reason="replaced")
                    except Exception:
                        pass
                room[slot] = ws
                await ws.send(
                    json.dumps(
                        {
                            "action": "player_joined",
                            "game_id": room_id,
                            "message": f"Room {room_id} - {'host' if is_host else 'guest'} joined.",
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                peer = _get_peer(room_id, ws)
                if peer is not None:
                    name = data.get("sender") or "Player"
                    await peer.send(
                        json.dumps(
                            {
                                "action": "player_joined",
                                "game_id": room_id,
                                "message": f"Opponent ({name}) joined.",
                            },
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    )
                continue
            if room_id is None:
                await ws.send(
                    json.dumps(
                        {
                            "error": "Send a Join message with game_id and host first."
                        }
                    )
                )
                continue
            if gid and gid != room_id:
                room_id = gid
            peer = _get_peer(room_id, ws)
            if peer is None:
                await ws.send(
                    json.dumps(
                        {
                            "action": "status",
                            "game_id": room_id,
                            "message": "Waiting for opponent in this room...",
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                )
                # Still buffer-less: don't echo own message back
                continue
            try:
                await peer.send(message)
            except Exception:
                pass
    finally:
        if room_id and room_id in rooms:
            room = rooms[room_id]
            for key in ("host", "guest"):
                if room.get(key) is ws:
                    room[key] = None
            if room.get("host") is None and room.get("guest") is None:
                rooms.pop(room_id, None)
            else:
                await _notify_peer(
                    room_id,
                    ws,
                    {
                        "action": "player_joined",
                        "game_id": room_id,
                        "message": "Opponent disconnected.",
                    },
                )
async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        default=os.environ.get("BIND_HOST", "0.0.0.0"),
        help="Listen address",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "7778")),
        help="Port (Render sets PORT)",
    )
    args = parser.parse_args()
    async with websockets.serve(
        handler,
        args.host,
        args.port,
        ping_interval=25,
        ping_timeout=120,
    ):
        print(
            f"WebSocket relay listening on ws://{args.host}:{args.port} (WSS via TLS proxy in production)"
        )
        await asyncio.Future()
if __name__ == "__main__":
    asyncio.run(main())
Retry
0 services selected:

Move
