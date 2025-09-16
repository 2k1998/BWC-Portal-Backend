# routers/websocket.py - WebSocket connections for real-time updates
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, List
import json
import asyncio
from jose import jwt
from datetime import datetime, timezone

import models
from database import get_db
        
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}
        self.last_heartbeat: Dict[int, datetime] = {}
        self.grace_seconds: int = 60
    
    async def connect(self, websocket: WebSocket, user_id: int, db: Session):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)
        self.last_heartbeat[user_id] = datetime.now(timezone.utc)
        
        # Mark user as online
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if user:
            user.is_online = True
            user.last_seen = datetime.now(timezone.utc)
            db.commit()
        
        print(f"User {user_id} connected. Total connections: {len(self.active_connections.get(user_id, []))}")
        # Broadcast presence update and snapshot to all users
        await self.broadcast_to_all({"type": "presence_update", "user_id": user_id, "is_online": True, "last_seen": user.last_seen.isoformat()})
        await self.send_presence_snapshot(websocket, db)
    
    def disconnect(self, websocket: WebSocket, user_id: int, db: Session):
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
                # Do not mark offline immediately; rely on grace timeout
                    
        print(f"User {user_id} disconnected")
    
    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_text(json.dumps(message))
                except:
                    disconnected.append(connection)
            
            # Clean up disconnected connections
            for conn in disconnected:
                self.active_connections[user_id].remove(conn)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
    
    async def broadcast_to_users(self, message: dict, user_ids: List[int]):
        for user_id in user_ids:
            await self.send_personal_message(message, user_id)

    async def broadcast_to_all(self, message: dict):
        for user_id in list(self.active_connections.keys()):
            await self.send_personal_message(message, user_id)

    async def send_presence_snapshot(self, websocket: WebSocket, db: Session):
        online_users = db.query(models.User).filter(models.User.is_online == True).all()
        snapshot = [{"user_id": u.id, "last_seen": (u.last_seen.isoformat() if u.last_seen else None)} for u in online_users]
        try:
            await websocket.send_text(json.dumps({"type": "presence_snapshot", "online": snapshot}))
        except:
            pass

manager = ConnectionManager()

def get_user_from_token(token: str, db: Session):
    """Extract user from JWT token for WebSocket authentication"""
    try:
        from .auth import SECRET_KEY, ALGORITHM
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            return None
        
        user = db.query(models.User).filter(models.User.email == email).first()
        return user
    except:
        return None

@router.websocket("/ws/{token}")
async def websocket_endpoint(websocket: WebSocket, token: str, db: Session = Depends(get_db)):
    # Authenticate user from token
    user = get_user_from_token(token, db)
    if not user:
        await websocket.close(code=1008)
        return
    
    await manager.connect(websocket, user.id, db)
    
    try:
        while True:
            # Keep connection alive and listen for client messages
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            # Handle different message types
            if message_data.get("type") == "ping":
                # Update heartbeat and last_seen
                manager.last_heartbeat[user.id] = datetime.now(timezone.utc)
                db_user = db.query(models.User).filter(models.User.id == user.id).first()
                if db_user:
                    db_user.last_seen = datetime.now(timezone.utc)
                    if not db_user.is_online:
                        db_user.is_online = True
                        await manager.broadcast_to_all({"type": "presence_update", "user_id": user.id, "is_online": True, "last_seen": db_user.last_seen.isoformat()})
                    db.commit()
                await websocket.send_text(json.dumps({"type": "pong"}))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id, db)

# Background task suggestion (to be scheduled by server runner):
# periodically check last_heartbeat and mark offline if exceeded grace.
async def sweep_offline_users(db: Session):
    now = datetime.now(timezone.utc)
    to_mark_offline = []
    for user_id, last in list(manager.last_heartbeat.items()):
        if (now - last).total_seconds() > manager.grace_seconds:
            to_mark_offline.append(user_id)
    for uid in to_mark_offline:
        user = db.query(models.User).filter(models.User.id == uid).first()
        if user and user.is_online:
            user.is_online = False
            user.last_seen = now
            db.commit()
            await manager.broadcast_to_all({"type": "presence_update", "user_id": uid, "is_online": False, "last_seen": user.last_seen.isoformat()})

# Helper functions to send real-time updates

async def notify_new_message(conversation_id: int, message: dict, sender_id: int, db: Session):
    """Send real-time notification for new chat message"""
    # Get conversation participants
    conversation = db.query(models.ChatConversation).filter(
        models.ChatConversation.id == conversation_id
    ).first()
    
    if conversation:
        # Notify the other participant (not the sender)
        other_user_id = (
            conversation.participant2_id if conversation.participant1_id == sender_id 
            else conversation.participant1_id
        )
        
        await manager.send_personal_message({
            "type": "new_message",
            "conversation_id": conversation_id,
            "message": message
        }, other_user_id)

async def notify_approval_request(approval_request: dict, approver_id: int):
    """Send real-time notification for new approval request"""
    await manager.send_personal_message({
        "type": "new_approval_request",
        "approval_request": approval_request
    }, approver_id)

async def notify_approval_response(approval_request: dict, requester_id: int, response_type: str):
    """Send real-time notification for approval response"""
    await manager.send_personal_message({
        "type": "approval_response",
        "approval_request": approval_request,
        "response_type": response_type
    }, requester_id)

async def notify_general_notification(notification: dict, user_id: int):
    """Send real-time notification for general system notifications"""
    await manager.send_personal_message({
        "type": "notification",
        "notification": notification
    }, user_id)
