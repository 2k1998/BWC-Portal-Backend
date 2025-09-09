# routers/chat.py - Chat system endpoints
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc, func
from typing import List, Optional
from datetime import datetime, timezone

import models, schemas
from database import get_db
from .auth import get_current_user
from .websocket import notify_new_message

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/conversations", response_model=List[schemas.ChatConversationSummary])
async def get_my_conversations(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all conversations for the current user"""
    
    # Get conversations where user is either participant1 or participant2
    conversations = db.query(models.ChatConversation).options(
        joinedload(models.ChatConversation.participant1),
        joinedload(models.ChatConversation.participant2),
        joinedload(models.ChatConversation.messages)
    ).filter(
        or_(
            models.ChatConversation.participant1_id == current_user.id,
            models.ChatConversation.participant2_id == current_user.id
        )
    ).order_by(desc(models.ChatConversation.last_message_at)).all()
    
    # Transform to summary format
    summaries = []
    for conv in conversations:
        # Determine the other participant
        other_participant = (
            conv.participant2 if conv.participant1_id == current_user.id 
            else conv.participant1
        )
        
        # Count unread messages
        unread_count = db.query(func.count(models.ChatMessage.id)).filter(
            and_(
                models.ChatMessage.conversation_id == conv.id,
                models.ChatMessage.sender_id != current_user.id,
                models.ChatMessage.read_at.is_(None)
            )
        ).scalar()
        
        summaries.append(schemas.ChatConversationSummary(
            id=conv.id,
            other_participant=schemas.UserBasicInfo(
                id=other_participant.id,
                full_name=other_participant.full_name
            ),
            last_message_at=conv.last_message_at,
            last_message_preview=conv.last_message_preview,
            unread_count=unread_count or 0
        ))
    
    return summaries


@router.get("/conversations/{conversation_id}", response_model=schemas.ChatConversationOut)
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get a specific conversation with all messages"""
    
    conversation = db.query(models.ChatConversation).options(
        joinedload(models.ChatConversation.participant1),
        joinedload(models.ChatConversation.participant2),
        joinedload(models.ChatConversation.messages).joinedload(models.ChatMessage.sender)
    ).filter(models.ChatConversation.id == conversation_id).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check access
    if not (conversation.participant1_id == current_user.id or 
            conversation.participant2_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to view this conversation")
    
    # Mark messages as read
    unread_messages = db.query(models.ChatMessage).filter(
        and_(
            models.ChatMessage.conversation_id == conversation_id,
            models.ChatMessage.sender_id != current_user.id,
            models.ChatMessage.read_at.is_(None)
        )
    ).all()
    
    for message in unread_messages:
        message.read_at = datetime.now(timezone.utc)
    
    if unread_messages:
        db.commit()
    
    return conversation


@router.post("/conversations/{user_id}", response_model=schemas.ChatConversationOut)
async def start_conversation(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Start a new conversation with a user or get existing one"""
    
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot start conversation with yourself")
    
    # Check if target user exists
    target_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if conversation already exists
    existing_conversation = db.query(models.ChatConversation).filter(
        or_(
            and_(
                models.ChatConversation.participant1_id == current_user.id,
                models.ChatConversation.participant2_id == user_id
            ),
            and_(
                models.ChatConversation.participant1_id == user_id,
                models.ChatConversation.participant2_id == current_user.id
            )
        )
    ).first()
    
    if existing_conversation:
        # Return existing conversation
        return await get_conversation(existing_conversation.id, db, current_user)
    
    # Create new conversation
    new_conversation = models.ChatConversation(
        participant1_id=min(current_user.id, user_id),  # Always put smaller ID first
        participant2_id=max(current_user.id, user_id)
    )
    
    db.add(new_conversation)
    db.commit()
    db.refresh(new_conversation)
    
    return await get_conversation(new_conversation.id, db, current_user)


@router.post("/conversations/{conversation_id}/messages", response_model=schemas.ChatMessageOut)
async def send_message(
    conversation_id: int,
    message: schemas.ChatMessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Send a message in a conversation"""
    
    conversation = db.query(models.ChatConversation).filter(
        models.ChatConversation.id == conversation_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check access
    if not (conversation.participant1_id == current_user.id or 
            conversation.participant2_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to send messages in this conversation")
    
    # Create message
    db_message = models.ChatMessage(
        conversation_id=conversation_id,
        sender_id=current_user.id,
        content=message.content,
        message_type=message.message_type
    )
    
    db.add(db_message)
    
    # Update conversation last message info
    conversation.last_message_at = datetime.now(timezone.utc)
    conversation.last_message_preview = message.content[:200]
    conversation.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(db_message)
    
    # Load sender info for response
    db_message.sender = current_user
    
    # Send real-time notification
    message_dict = {
        "id": db_message.id,
        "conversation_id": db_message.conversation_id,
        "sender_id": db_message.sender_id,
        "content": db_message.content,
        "message_type": db_message.message_type,
        "sent_at": db_message.sent_at.isoformat(),
        "sender": {
            "id": current_user.id,
            "full_name": current_user.full_name
        }
    }
    
    # Send notification asynchronously
    import asyncio
    asyncio.create_task(notify_new_message(conversation_id, message_dict, current_user.id, db))
    
    return db_message


@router.get("/users/search")
async def search_users(
    query: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Search for users to start conversations with"""
    
    users_query = db.query(models.User).filter(
        and_(
            models.User.id != current_user.id,  # Exclude current user
            models.User.is_active == True
        )
    )
    
    if query:
        search_filter = or_(
            models.User.first_name.ilike(f"%{query}%"),
            models.User.surname.ilike(f"%{query}%"),
            models.User.email.ilike(f"%{query}%")
        )
        users_query = users_query.filter(search_filter)
    
    users = users_query.limit(limit).all()
    
    return [
        {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "profile_picture_url": user.profile_picture_url
        }
        for user in users
    ]
