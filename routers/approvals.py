# routers/approvals.py - Approval system endpoints
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc
from typing import List, Optional
from datetime import datetime, timezone

import models, schemas
from database import get_db
from .auth import get_current_user
from .websocket import notify_approval_request, notify_approval_response

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("/", response_model=schemas.ApprovalRequestOut)
async def create_approval_request(
    request: schemas.ApprovalRequestCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Create a new approval request"""
    
    # Validate approver exists
    approver = db.query(models.User).filter(
        and_(
            models.User.id == request.approver_id,
            models.User.is_active == True
        )
    ).first()
    
    if not approver:
        raise HTTPException(status_code=404, detail="Approver not found")
    
    if request.approver_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot request approval from yourself")
    
    # Create approval request
    db_request = models.ApprovalRequest(
        requester_id=current_user.id,
        approver_id=request.approver_id,
        title=request.title,
        description=request.description,
        request_type=models.ApprovalRequestType(request.request_type),
        request_metadata=request.request_metadata
    )
    
    db.add(db_request)
    db.flush()  # Get the ID
    
    # Create notification for approver
    notification = models.ApprovalNotification(
        user_id=request.approver_id,
        approval_request_id=db_request.id,
        notification_type="new_request",
        title=f"New Approval Request: {request.title}",
        message=f"{current_user.full_name} is requesting approval for: {request.description[:100]}..."
    )
    
    db.add(notification)
    
    # Start a chat conversation with approval request message
    # First check if conversation exists
    existing_conversation = db.query(models.ChatConversation).filter(
        or_(
            and_(
                models.ChatConversation.participant1_id == current_user.id,
                models.ChatConversation.participant2_id == request.approver_id
            ),
            and_(
                models.ChatConversation.participant1_id == request.approver_id,
                models.ChatConversation.participant2_id == current_user.id
            )
        )
    ).first()
    
    if not existing_conversation:
        # Create new conversation
        existing_conversation = models.ChatConversation(
            participant1_id=min(current_user.id, request.approver_id),
            participant2_id=max(current_user.id, request.approver_id)
        )
        db.add(existing_conversation)
        db.flush()
    
    # Add approval request message to chat
    approval_message = models.ChatMessage(
        conversation_id=existing_conversation.id,
        sender_id=current_user.id,
        content=f"📋 **Approval Request: {request.title}**\n\n{request.description}",
        message_type="approval_request",
        approval_request_id=db_request.id,
        is_system_message=True
    )
    
    db.add(approval_message)
    
    # Update conversation
    existing_conversation.last_message_at = datetime.now(timezone.utc)
    existing_conversation.last_message_preview = f"Approval Request: {request.title}"
    existing_conversation.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(db_request)
    
    # Load relationships for response
    db_request.requester = current_user
    db_request.approver = approver
    
    # Send real-time notification to approver
    approval_dict = {
        "id": db_request.id,
        "title": db_request.title,
        "description": db_request.description,
        "request_type": db_request.request_type,
        "status": db_request.status,
        "created_at": db_request.created_at.isoformat(),
        "requester": {
            "id": current_user.id,
            "full_name": current_user.full_name
        }
    }
    
    # Send notification asynchronously
    import asyncio
    asyncio.create_task(notify_approval_request(approval_dict, request.approver_id))
    
    return db_request


@router.get("/", response_model=List[schemas.ApprovalRequestOut])
async def get_approval_requests(
    status_filter: Optional[str] = None,
    as_requester: bool = False,
    as_approver: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get approval requests - can filter by status and role"""
    
    query = db.query(models.ApprovalRequest).options(
        joinedload(models.ApprovalRequest.requester),
        joinedload(models.ApprovalRequest.approver)
    )
    
    # Filter by role
    if as_requester and as_approver:
        # Both - get all requests involving user
        query = query.filter(
            or_(
                models.ApprovalRequest.requester_id == current_user.id,
                models.ApprovalRequest.approver_id == current_user.id
            )
        )
    elif as_requester:
        # Only requests made by current user
        query = query.filter(models.ApprovalRequest.requester_id == current_user.id)
    elif as_approver:
        # Only requests assigned to current user
        query = query.filter(models.ApprovalRequest.approver_id == current_user.id)
    else:
        # Default: get all requests involving user
        query = query.filter(
            or_(
                models.ApprovalRequest.requester_id == current_user.id,
                models.ApprovalRequest.approver_id == current_user.id
            )
        )
    
    # Filter by status
    if status_filter:
        try:
            status_enum = models.ApprovalStatus(status_filter)
            query = query.filter(models.ApprovalRequest.status == status_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status_filter}")
    
    requests = query.order_by(desc(models.ApprovalRequest.created_at)).all()
    
    return requests


@router.get("/{request_id}", response_model=schemas.ApprovalRequestOut)
async def get_approval_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get a specific approval request"""
    
    request = db.query(models.ApprovalRequest).options(
        joinedload(models.ApprovalRequest.requester),
        joinedload(models.ApprovalRequest.approver)
    ).filter(models.ApprovalRequest.id == request_id).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    # Check access
    if not (request.requester_id == current_user.id or request.approver_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to view this request")
    
    return request


@router.post("/{request_id}/respond", response_model=schemas.ApprovalRequestOut)
async def respond_to_approval_request(
    request_id: int,
    response: schemas.ApprovalRequestResponse,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Respond to an approval request (approve/reject/discussion)"""
    
    request = db.query(models.ApprovalRequest).options(
        joinedload(models.ApprovalRequest.requester),
        joinedload(models.ApprovalRequest.approver)
    ).filter(models.ApprovalRequest.id == request_id).first()
    
    if not request:
        raise HTTPException(status_code=404, detail="Approval request not found")
    
    # Only approver can respond
    if request.approver_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the approver can respond to this request")
    
    # Validate action
    if response.action not in ["approve", "reject", "discussion"]:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'approve', 'reject', or 'discussion'")
    
    # Update request
    now = datetime.now(timezone.utc)
    request.responded_at = now
    request.updated_at = now
    request.response_message = response.response_message
    
    # Set status based on action
    if response.action == "approve":
        request.status = models.ApprovalStatus.APPROVED
        notification_type = "approved"
        notification_title = f"Request Approved: {request.title}"
        notification_message = f"Your approval request has been approved by {current_user.full_name}"
        
    elif response.action == "reject":
        request.status = models.ApprovalStatus.REJECTED
        notification_type = "rejected"
        notification_title = f"Request Rejected: {request.title}"
        notification_message = f"Your approval request has been rejected by {current_user.full_name}"
        
    else:  # discussion
        request.status = models.ApprovalStatus.DISCUSSION
        notification_type = "discussion"
        notification_title = f"Discussion Requested: {request.title}"
        notification_message = f"{current_user.full_name} wants to discuss your approval request"
    
    # Create notification for requester
    notification = models.ApprovalNotification(
        user_id=request.requester_id,
        approval_request_id=request.id,
        notification_type=notification_type,
        title=notification_title,
        message=notification_message
    )
    
    db.add(notification)
    
    # If discussion is requested, add a system message to the chat
    if response.action == "discussion":
        # Find the conversation
        conversation = db.query(models.ChatConversation).filter(
            or_(
                and_(
                    models.ChatConversation.participant1_id == request.requester_id,
                    models.ChatConversation.participant2_id == current_user.id
                ),
                and_(
                    models.ChatConversation.participant1_id == current_user.id,
                    models.ChatConversation.participant2_id == request.requester_id
                )
            )
        ).first()
        
        if conversation:
            discussion_message = models.ChatMessage(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                content=f"💬 Let's discuss the approval request: **{request.title}**\n\n{response.response_message or 'I have some questions about this request.'}",
                message_type="system",
                is_system_message=True
            )
            
            db.add(discussion_message)
            
            # Update conversation
            conversation.last_message_at = now
            conversation.last_message_preview = "Discussion requested for approval"
            conversation.updated_at = now
    
    db.commit()
    db.refresh(request)
    
    return request


@router.get("/notifications/", response_model=List[schemas.ApprovalNotificationOut])
async def get_approval_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get approval notifications for current user"""
    
    query = db.query(models.ApprovalNotification).options(
        joinedload(models.ApprovalNotification.approval_request).joinedload(models.ApprovalRequest.requester),
        joinedload(models.ApprovalNotification.approval_request).joinedload(models.ApprovalRequest.approver)
    ).filter(models.ApprovalNotification.user_id == current_user.id)
    
    if unread_only:
        query = query.filter(models.ApprovalNotification.is_read == False)
    
    notifications = query.order_by(desc(models.ApprovalNotification.created_at)).limit(limit).all()
    
    return notifications


@router.put("/notifications/{notification_id}/read")
async def mark_approval_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark an approval notification as read"""
    
    notification = db.query(models.ApprovalNotification).filter(
        and_(
            models.ApprovalNotification.id == notification_id,
            models.ApprovalNotification.user_id == current_user.id
        )
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return {"message": "Notification marked as read"}


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
async def dismiss_approval_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Dismiss/delete an approval notification"""
    
    notification = db.query(models.ApprovalNotification).filter(
        and_(
            models.ApprovalNotification.id == notification_id,
            models.ApprovalNotification.user_id == current_user.id
        )
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notification)
    db.commit()
    
    return


@router.delete("/notifications/clear-all", status_code=status.HTTP_204_NO_CONTENT)
async def clear_all_approval_notifications(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Clear all approval notifications for the current user"""
    
    deleted_count = db.query(models.ApprovalNotification).filter(
        models.ApprovalNotification.user_id == current_user.id
    ).delete()
    
    db.commit()
    
    return