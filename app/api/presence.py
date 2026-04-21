from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, get_db
from app.core.deps import get_current_user
from app.core.security import decode_token
from app.models.user import User
from app.schemas.presence import PresenceListResponse, PresenceUserResponse
from app.utils.connection_manager import connection_manager

router = APIRouter(tags=["Presence"])


def _presence_user_to_response(user: User) -> PresenceUserResponse:
    user_id_str = str(user.id)
    last_seen = connection_manager.get_last_seen(user_id_str)
    return PresenceUserResponse(
        user_id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        user_type=user.user_type,
        is_online=connection_manager.is_user_online(user_id_str),
        last_seen_at=last_seen,
    )


@router.get("/presence", response_model=PresenceListResponse)
def list_presence(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return PresenceListResponse(users=[_presence_user_to_response(u) for u in users])


def _get_user_from_token(db: Session, token: str) -> User | None:
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        return None

    return user


@router.websocket("/ws/presence")
async def ws_presence(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    db: Session = SessionLocal()
    user: User | None = None
    try:
        await websocket.accept()

        user = _get_user_from_token(db=db, token=token)
        if not user:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        user_id_str = str(user.id)
        await connection_manager.connect_presence(user_id=user_id_str, websocket=websocket)

        # Broadcast online transition.
        last_seen = connection_manager.get_last_seen(user_id_str)
        await connection_manager.broadcast_to_presence(
            {
                "type": "presence_update",
                "user_id": user_id_str,
                "is_online": True,
                "last_seen_at": last_seen.isoformat() if last_seen else None,
            }
        )

        # Initial snapshot to this connection.
        all_users = db.query(User).all()
        snapshot = {
            "type": "presence_snapshot",
            "users": [
                {
                    "user_id": str(u.id),
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "user_type": u.user_type,
                    "is_online": connection_manager.is_user_online(str(u.id)),
                    "last_seen_at": (
                        connection_manager.get_last_seen(str(u.id)).isoformat()
                        if connection_manager.get_last_seen(str(u.id))
                        else None
                    ),
                }
                for u in all_users
            ],
        }
        await websocket.send_json(snapshot)

        while True:
            raw = await websocket.receive_text()

            # Client sends heartbeat every ~30s (format not strictly defined).
            is_heartbeat = False
            try:
                data = json.loads(raw)
                is_heartbeat = data.get("type") == "heartbeat" or data.get("heartbeat") is True
            except Exception:
                is_heartbeat = raw.strip().lower() in {"heartbeat", "ping"}

            if not is_heartbeat:
                continue

            await connection_manager.update_last_seen(user_id=user_id_str)
            last_seen = connection_manager.get_last_seen(user_id_str)

            update = {
                "type": "presence_update",
                "user_id": user_id_str,
                "is_online": True,
                "last_seen_at": last_seen.isoformat() if last_seen else None,
            }
            await connection_manager.broadcast_to_presence(update)

    except WebSocketDisconnect:
        if user:
            user_id_str = str(user.id)
            await connection_manager.disconnect_presence(user_id=user_id_str, websocket=websocket)
            # Broadcast offline transition.
            last_seen = connection_manager.get_last_seen(user_id_str)
            await connection_manager.broadcast_to_presence(
                {
                    "type": "presence_update",
                    "user_id": user_id_str,
                    "is_online": False,
                    "last_seen_at": last_seen.isoformat() if last_seen else None,
                }
            )
    finally:
        db.close()

