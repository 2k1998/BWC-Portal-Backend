from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, desc
from typing import List, Optional
from datetime import datetime, timezone

from database import get_db
import models, schemas
from .auth import get_current_user
from .utils import check_roles

router = APIRouter(prefix="/task-management", tags=["task-management"])

# ==================== TASK ASSIGNMENT ENDPOINTS ====================

@router.post("/assign", response_model=schemas.TaskAssignmentOut, status_code=status.HTTP_201_CREATED)
async def assign_task(
    assignment: schemas.TaskAssignmentCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Assign a task to a user with notification system"""
    
    # Verify task exists and user has permission to assign it
    task = db.query(models.Task).filter(models.Task.id == assignment.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check if user can assign this task (admin, task owner, task creator, or manager)
    # Allow any user to transfer tasks they created, or admins/managers to assign any task
    can_assign = (
        current_user.role in ["admin", "Manager", "Head"] or 
        task.owner_id == current_user.id or 
        task.created_by_id == current_user.id
    )
    if not can_assign:
        raise HTTPException(status_code=403, detail="Not authorized to assign this task")
    
    # Verify assignee exists
    assignee = db.query(models.User).filter(models.User.id == assignment.assigned_to_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="Assignee not found")
    
    # Check if there's already a pending assignment for this task
    existing_assignment = db.query(models.TaskAssignment).filter(
        and_(
            models.TaskAssignment.task_id == assignment.task_id,
            models.TaskAssignment.assigned_to_id == assignment.assigned_to_id,
            models.TaskAssignment.assignment_status.in_([
                models.TaskAssignmentStatus.PENDING_ACCEPTANCE,
                models.TaskAssignmentStatus.DISCUSSION_REQUESTED,
                models.TaskAssignmentStatus.DISCUSSION_ACTIVE
            ])
        )
    ).first()
    
    if existing_assignment:
        raise HTTPException(status_code=400, detail="Task already has a pending assignment to this user")
    
    # Create the assignment
    db_assignment = models.TaskAssignment(
        task_id=assignment.task_id,
        assigned_by_id=current_user.id,
        assigned_to_id=assignment.assigned_to_id,
        assignment_message=assignment.assignment_message
    )
    
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    
    # Create notification for assignee
    notification = models.TaskNotification(
        user_id=assignment.assigned_to_id,
        task_id=assignment.task_id,
        assignment_id=db_assignment.id,
        notification_type="task_assigned",
        title=f"New Task Assignment: {task.title}",
        message=f"{current_user.first_name} {current_user.surname} has assigned you a task: '{task.title}'",
        action_url=f"/tasks/assignments/{db_assignment.id}"
    )
    db.add(notification)
    db.commit()
    
    # Load relationships for response
    db_assignment = db.query(models.TaskAssignment).options(
        joinedload(models.TaskAssignment.assigned_by),
        joinedload(models.TaskAssignment.assigned_to),
        joinedload(models.TaskAssignment.task)
    ).filter(models.TaskAssignment.id == db_assignment.id).first()
    
    # TODO: Add email notification as background task
    # background_tasks.add_task(send_assignment_email, assignee.email, task.title, current_user.full_name)
    
    return db_assignment

@router.post("/transfer", response_model=schemas.TaskAssignmentOut, status_code=status.HTTP_201_CREATED)
async def transfer_task(
    transfer_data: schemas.TaskTransferCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Simple task transfer endpoint - allows users to transfer tasks they created to others"""
    
    # Verify task exists and user has permission to transfer it
    task = db.query(models.Task).filter(models.Task.id == transfer_data.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Check if user can transfer this task (admin, task owner, or task creator)
    can_transfer = (
        current_user.role in ["admin", "Manager", "Head"] or 
        task.owner_id == current_user.id or 
        task.created_by_id == current_user.id
    )
    if not can_transfer:
        raise HTTPException(status_code=403, detail="Not authorized to transfer this task")
    
    # Verify assignee exists
    assignee = db.query(models.User).filter(models.User.id == transfer_data.assigned_to_id).first()
    if not assignee:
        raise HTTPException(status_code=404, detail="Assignee not found")
    
    # Check if there's already a pending assignment for this task
    existing_assignment = db.query(models.TaskAssignment).filter(
        and_(
            models.TaskAssignment.task_id == transfer_data.task_id,
            models.TaskAssignment.assigned_to_id == transfer_data.assigned_to_id,
            models.TaskAssignment.assignment_status.in_([
                models.TaskAssignmentStatus.PENDING_ACCEPTANCE,
                models.TaskAssignmentStatus.DISCUSSION_REQUESTED,
                models.TaskAssignmentStatus.DISCUSSION_ACTIVE
            ])
        )
    ).first()
    
    if existing_assignment:
        raise HTTPException(status_code=400, detail="Task already has a pending assignment to this user")
    
    # Create the assignment
    db_assignment = models.TaskAssignment(
        task_id=transfer_data.task_id,
        assigned_by_id=current_user.id,
        assigned_to_id=transfer_data.assigned_to_id,
        assignment_message=transfer_data.message or f"Task '{task.title}' has been transferred to you by {current_user.first_name} {current_user.surname}"
    )
    
    db.add(db_assignment)
    db.commit()
    db.refresh(db_assignment)
    
    # Create notification for assignee
    notification = models.TaskNotification(
        user_id=transfer_data.assigned_to_id,
        task_id=transfer_data.task_id,
        assignment_id=db_assignment.id,
        notification_type="task_transferred",
        title=f"Task Transferred: {task.title}",
        message=f"{current_user.first_name} {current_user.surname} has transferred a task to you: '{task.title}'",
        action_url=f"/tasks/assignments/{db_assignment.id}"
    )
    db.add(notification)
    db.commit()
    
    # Load relationships for response
    db_assignment = db.query(models.TaskAssignment).options(
        joinedload(models.TaskAssignment.assigned_by),
        joinedload(models.TaskAssignment.assigned_to),
        joinedload(models.TaskAssignment.task)
    ).filter(models.TaskAssignment.id == db_assignment.id).first()
    
    return db_assignment

@router.get("/assignments/pending", response_model=List[schemas.TaskAssignmentOut])
async def get_pending_assignments(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all pending task assignments for the current user"""
    
    assignments = db.query(models.TaskAssignment).options(
        joinedload(models.TaskAssignment.assigned_by),
        joinedload(models.TaskAssignment.assigned_to),
        joinedload(models.TaskAssignment.task)
    ).filter(
        and_(
            models.TaskAssignment.assigned_to_id == current_user.id,
            models.TaskAssignment.assignment_status == models.TaskAssignmentStatus.PENDING_ACCEPTANCE
        )
    ).order_by(desc(models.TaskAssignment.assigned_at)).all()
    
    return assignments

@router.get("/assignments/{assignment_id}", response_model=schemas.TaskAssignmentOut)
async def get_assignment_details(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get detailed information about a specific assignment"""
    
    assignment = db.query(models.TaskAssignment).options(
        joinedload(models.TaskAssignment.assigned_by),
        joinedload(models.TaskAssignment.assigned_to),
        joinedload(models.TaskAssignment.task)
    ).filter(models.TaskAssignment.id == assignment_id).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check if user has access to this assignment
    if not (assignment.assigned_to_id == current_user.id or 
            assignment.assigned_by_id == current_user.id or 
            current_user.role in ["admin", "Manager", "Head"]):
        raise HTTPException(status_code=403, detail="Not authorized to view this assignment")
    
    return assignment

@router.post("/assignments/{assignment_id}/respond", response_model=schemas.TaskAssignmentOut)
async def respond_to_assignment(
    assignment_id: int,
    response: schemas.TaskAssignmentAction,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Respond to a task assignment (accept/reject/discuss)"""
    
    assignment = db.query(models.TaskAssignment).filter(
        models.TaskAssignment.id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    if assignment.assigned_to_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to respond to this assignment")
    
    if assignment.assignment_status != models.TaskAssignmentStatus.PENDING_ACCEPTANCE:
        raise HTTPException(status_code=400, detail="Assignment has already been responded to")
    
    # Update assignment based on action
    assignment.response_at = datetime.now(timezone.utc)
    assignment.response_message = response.message
    
    notification_type = ""
    notification_message = ""
    
    if response.action == "accept":
        assignment.assignment_status = models.TaskAssignmentStatus.ACCEPTED
        # Update task owner
        task = db.query(models.Task).filter(models.Task.id == assignment.task_id).first()
        if task:
            task.owner_id = current_user.id
            task.status = models.TaskStatus.RECEIVED  # Update task status
        
        notification_type = "task_accepted"
        notification_message = f"{current_user.first_name} {current_user.surname} has accepted the task assignment"
        
    elif response.action == "reject":
        assignment.assignment_status = models.TaskAssignmentStatus.REJECTED
        assignment.rejection_reason = response.rejection_reason
        
        notification_type = "task_rejected"
        notification_message = f"{current_user.first_name} {current_user.surname} has rejected the task assignment"
        
    elif response.action == "discuss":
        assignment.assignment_status = models.TaskAssignmentStatus.DISCUSSION_REQUESTED
        
        # Create conversation
        conversation = models.TaskConversation(
            assignment_id=assignment.id
        )
        db.add(conversation)
        db.flush()  # Get the conversation ID
        
        # Add initial message if provided
        if response.message:
            initial_message = models.TaskMessage(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                content=response.message,
                message_type=models.MessageType.TEXT
            )
            db.add(initial_message)
        
        notification_type = "discussion_requested"
        notification_message = f"{current_user.first_name} {current_user.surname} wants to discuss the task assignment"
    
    db.commit()
    
    # Create notification for assigner
    notification = models.TaskNotification(
        user_id=assignment.assigned_by_id,
        task_id=assignment.task_id,
        assignment_id=assignment.id,
        notification_type=notification_type,
        title=f"Task Assignment Response",
        message=notification_message,
        action_url=f"/tasks/assignments/{assignment.id}"
    )
    db.add(notification)
    db.commit()
    
    # Reload assignment with relationships
    assignment = db.query(models.TaskAssignment).options(
        joinedload(models.TaskAssignment.assigned_by),
        joinedload(models.TaskAssignment.assigned_to),
        joinedload(models.TaskAssignment.task)
    ).filter(models.TaskAssignment.id == assignment_id).first()
    
    return assignment

# ==================== MESSAGING ENDPOINTS ====================

@router.get("/conversations/{assignment_id}", response_model=schemas.TaskConversationOut)
async def get_conversation(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get the conversation for a specific assignment"""
    
    assignment = db.query(models.TaskAssignment).filter(
        models.TaskAssignment.id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check access
    if not (assignment.assigned_to_id == current_user.id or 
            assignment.assigned_by_id == current_user.id or 
            current_user.role in ["admin"]):
        raise HTTPException(status_code=403, detail="Not authorized to view this conversation")
    
    conversation = db.query(models.TaskConversation).options(
        joinedload(models.TaskConversation.messages).joinedload(models.TaskMessage.sender),
        joinedload(models.TaskConversation.completed_by)
    ).filter(models.TaskConversation.assignment_id == assignment_id).first()
    
    if not conversation:
        # Create conversation if it doesn't exist
        conversation = models.TaskConversation(assignment_id=assignment_id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    
    # Mark messages as read
    unread_messages = db.query(models.TaskMessage).filter(
        and_(
            models.TaskMessage.conversation_id == conversation.id,
            models.TaskMessage.sender_id != current_user.id,
            models.TaskMessage.read_at.is_(None)
        )
    ).all()
    
    for message in unread_messages:
        message.read_at = datetime.now(timezone.utc)
    
    db.commit()
    
    return conversation

@router.post("/conversations/{assignment_id}/messages", response_model=schemas.TaskMessageOut)
async def send_message(
    assignment_id: int,
    message: schemas.TaskMessageCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Send a message in a task conversation"""
    
    assignment = db.query(models.TaskAssignment).filter(
        models.TaskAssignment.id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check access
    if not (assignment.assigned_to_id == current_user.id or assignment.assigned_by_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to message in this conversation")
    
    # Get or create conversation
    conversation = db.query(models.TaskConversation).filter(
        models.TaskConversation.assignment_id == assignment_id
    ).first()
    
    if not conversation:
        conversation = models.TaskConversation(assignment_id=assignment_id)
        db.add(conversation)
        db.flush()
    
    # Create message
    db_message = models.TaskMessage(
        conversation_id=conversation.id,
        sender_id=current_user.id,
        content=message.content,
        message_type=message.message_type
    )
    
    db.add(db_message)
    
    # Update assignment status if needed
    if assignment.assignment_status == models.TaskAssignmentStatus.DISCUSSION_REQUESTED:
        assignment.assignment_status = models.TaskAssignmentStatus.DISCUSSION_ACTIVE
    
    db.commit()
    db.refresh(db_message)
    
    # Create notification for the other party
    recipient_id = assignment.assigned_by_id if current_user.id == assignment.assigned_to_id else assignment.assigned_to_id
    
    notification = models.TaskNotification(
        user_id=recipient_id,
        task_id=assignment.task_id,
        assignment_id=assignment.id,
        notification_type="message_received",
        title="New Message",
        message=f"New message from {current_user.first_name} {current_user.surname}",
        action_url=f"/tasks/assignments/{assignment.id}/conversation"
    )
    db.add(notification)
    db.commit()
    
    # Load relationships for response
    db_message = db.query(models.TaskMessage).options(
        joinedload(models.TaskMessage.sender)
    ).filter(models.TaskMessage.id == db_message.id).first()
    
    return db_message

@router.post("/conversations/{assignment_id}/complete", response_model=schemas.TaskConversationOut)
async def complete_conversation(
    assignment_id: int,
    action: schemas.ConversationAction,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark a conversation as completed"""
    
    assignment = db.query(models.TaskAssignment).filter(
        models.TaskAssignment.id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    conversation = db.query(models.TaskConversation).filter(
        models.TaskConversation.assignment_id == assignment_id
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Check access (both parties can complete)
    if not (assignment.assigned_to_id == current_user.id or assignment.assigned_by_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to complete this conversation")
    
    if action.action == "complete":
        conversation.status = models.ConversationStatus.COMPLETED
        conversation.completed_at = datetime.now(timezone.utc)
        conversation.completed_by_id = current_user.id
        assignment.assignment_status = models.TaskAssignmentStatus.DISCUSSION_COMPLETED
        
        # Add final message if provided
        if action.final_message:
            final_message = models.TaskMessage(
                conversation_id=conversation.id,
                sender_id=current_user.id,
                content=action.final_message,
                message_type=models.MessageType.SYSTEM,
                is_system_message=True
            )
            db.add(final_message)
    
    elif action.action == "reopen":
        conversation.status = models.ConversationStatus.ACTIVE
        conversation.completed_at = None
        conversation.completed_by_id = None
        assignment.assignment_status = models.TaskAssignmentStatus.DISCUSSION_ACTIVE
    
    db.commit()
    
    # Reload with relationships
    conversation = db.query(models.TaskConversation).options(
        joinedload(models.TaskConversation.messages).joinedload(models.TaskMessage.sender),
        joinedload(models.TaskConversation.completed_by)
    ).filter(models.TaskConversation.id == conversation.id).first()
    
    return conversation

# ==================== CALL MANAGEMENT ENDPOINTS ====================

@router.post("/assignments/{assignment_id}/schedule-call", response_model=schemas.TaskAssignmentOut)
async def schedule_call(
    assignment_id: int,
    call_request: schemas.CallScheduleRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Schedule a call for task discussion"""
    
    assignment = db.query(models.TaskAssignment).filter(
        models.TaskAssignment.id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check access
    if not (assignment.assigned_to_id == current_user.id or assignment.assigned_by_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to schedule call for this assignment")
    
    assignment.call_requested = True
    assignment.call_scheduled_at = call_request.scheduled_time
    
    db.commit()
    
    # Create notification for the other party
    recipient_id = assignment.assigned_by_id if current_user.id == assignment.assigned_to_id else assignment.assigned_to_id
    
    notification = models.TaskNotification(
        user_id=recipient_id,
        task_id=assignment.task_id,
        assignment_id=assignment.id,
        notification_type="call_scheduled",
        title="Call Scheduled",
        message=f"Call scheduled for {call_request.scheduled_time.strftime('%Y-%m-%d %H:%M')}",
        action_url=f"/tasks/assignments/{assignment.id}"
    )
    db.add(notification)
    
    # Add system message to conversation
    conversation = db.query(models.TaskConversation).filter(
        models.TaskConversation.assignment_id == assignment_id
    ).first()
    
    if conversation:
        system_message = models.TaskMessage(
            conversation_id=conversation.id,
            sender_id=current_user.id,
            content=f"Call scheduled for {call_request.scheduled_time.strftime('%Y-%m-%d at %H:%M')}",
            message_type=models.MessageType.CALL_SCHEDULED,
            is_system_message=True
        )
        db.add(system_message)
    
    db.commit()
    
    # Reload with relationships
    assignment = db.query(models.TaskAssignment).options(
        joinedload(models.TaskAssignment.assigned_by),
        joinedload(models.TaskAssignment.assigned_to),
        joinedload(models.TaskAssignment.task)
    ).filter(models.TaskAssignment.id == assignment_id).first()
    
    return assignment

@router.post("/assignments/{assignment_id}/complete-call", response_model=schemas.TaskAssignmentOut)
async def complete_call(
    assignment_id: int,
    call_completion: schemas.CallCompletionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark a call as completed and record notes"""
    
    assignment = db.query(models.TaskAssignment).filter(
        models.TaskAssignment.id == assignment_id
    ).first()
    
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    # Check access
    if not (assignment.assigned_to_id == current_user.id or assignment.assigned_by_id == current_user.id):
        raise HTTPException(status_code=403, detail="Not authorized to complete call for this assignment")
    
    assignment.call_completed_at = datetime.now(timezone.utc)
    assignment.call_notes = call_completion.call_notes
    
    # Update assignment status based on outcome
    if call_completion.outcome == "task_accepted":
        assignment.assignment_status = models.TaskAssignmentStatus.ACCEPTED
        # Update task owner
        task = db.query(models.Task).filter(models.Task.id == assignment.task_id).first()
        if task:
            task.owner_id = assignment.assigned_to_id
            task.status = models.TaskStatus.RECEIVED
    elif call_completion.outcome == "task_rejected":
        assignment.assignment_status = models.TaskAssignmentStatus.REJECTED
    elif call_completion.outcome == "needs_follow_up":
        assignment.assignment_status = models.TaskAssignmentStatus.DISCUSSION_ACTIVE
    
    db.commit()
    
    # Add system message to conversation
    conversation = db.query(models.TaskConversation).filter(
        models.TaskConversation.assignment_id == assignment_id
    ).first()
    
    if conversation:
        system_message = models.TaskMessage(
            conversation_id=conversation.id,
            sender_id=current_user.id,
            content=f"Call completed. Outcome: {call_completion.outcome}. Notes: {call_completion.call_notes}",
            message_type=models.MessageType.CALL_COMPLETED,
            is_system_message=True
        )
        db.add(system_message)
    
    db.commit()
    
    # Reload with relationships
    assignment = db.query(models.TaskAssignment).options(
        joinedload(models.TaskAssignment.assigned_by),
        joinedload(models.TaskAssignment.assigned_to),
        joinedload(models.TaskAssignment.task)
    ).filter(models.TaskAssignment.id == assignment_id).first()
    
    return assignment

# ==================== NOTIFICATION ENDPOINTS ====================

@router.get("/notifications", response_model=List[schemas.TaskNotificationOut])
async def get_task_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get task-related notifications for the current user"""
    
    query = db.query(models.TaskNotification).filter(
        models.TaskNotification.user_id == current_user.id
    )
    
    if unread_only:
        query = query.filter(models.TaskNotification.is_read == False)
    
    notifications = query.order_by(desc(models.TaskNotification.created_at)).limit(limit).all()
    
    return notifications

@router.put("/notifications/{notification_id}/read", response_model=schemas.TaskNotificationOut)
async def mark_task_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Mark a task notification as read"""
    
    notification = db.query(models.TaskNotification).filter(
        and_(
            models.TaskNotification.id == notification_id,
            models.TaskNotification.user_id == current_user.id
        )
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(notification)
    
    return notification

# ==================== DASHBOARD/SUMMARY ENDPOINTS ====================

@router.get("/summary", response_model=schemas.TaskAssignmentSummary)
async def get_assignment_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get summary of task assignments for the current user"""
    
    # Count pending assignments (assigned to me)
    pending_assignments = db.query(models.TaskAssignment).filter(
        and_(
            models.TaskAssignment.assigned_to_id == current_user.id,
            models.TaskAssignment.assignment_status == models.TaskAssignmentStatus.PENDING_ACCEPTANCE
        )
    ).count()
    
    # Count active discussions (either assigned by me or to me)
    active_discussions = db.query(models.TaskAssignment).filter(
        and_(
            or_(
                models.TaskAssignment.assigned_to_id == current_user.id,
                models.TaskAssignment.assigned_by_id == current_user.id
            ),
            models.TaskAssignment.assignment_status.in_([
                models.TaskAssignmentStatus.DISCUSSION_ACTIVE,
                models.TaskAssignmentStatus.DISCUSSION_REQUESTED
            ])
        )
    ).count()
    
    # Count pending calls
    pending_calls = db.query(models.TaskAssignment).filter(
        and_(
            or_(
                models.TaskAssignment.assigned_to_id == current_user.id,
                models.TaskAssignment.assigned_by_id == current_user.id
            ),
            models.TaskAssignment.call_requested == True,
            models.TaskAssignment.call_completed_at.is_(None)
        )
    ).count()
    
    # Count total assigned by me
    total_assigned_by_me = db.query(models.TaskAssignment).filter(
        models.TaskAssignment.assigned_by_id == current_user.id
    ).count()
    
    # Count total assigned to me
    total_assigned_to_me = db.query(models.TaskAssignment).filter(
        models.TaskAssignment.assigned_to_id == current_user.id
    ).count()
    
    return schemas.TaskAssignmentSummary(
        pending_assignments=pending_assignments,
        active_discussions=active_discussions,
        pending_calls=pending_calls,
        total_assigned_by_me=total_assigned_by_me,
        total_assigned_to_me=total_assigned_to_me
    )

@router.get("/my-assignments", response_model=List[schemas.TaskAssignmentOut])
async def get_my_assignments(
    status_filter: Optional[str] = None,
    assigned_by_me: bool = False,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all assignments (either assigned to me or by me)"""
    
    if assigned_by_me:
        query = db.query(models.TaskAssignment).filter(
            models.TaskAssignment.assigned_by_id == current_user.id
        )
    else:
        query = db.query(models.TaskAssignment).filter(
            models.TaskAssignment.assigned_to_id == current_user.id
        )
    
    if status_filter:
        query = query.filter(models.TaskAssignment.assignment_status == status_filter)
    
    assignments = query.options(
        joinedload(models.TaskAssignment.assigned_by),
        joinedload(models.TaskAssignment.assigned_to),
        joinedload(models.TaskAssignment.task)
    ).order_by(desc(models.TaskAssignment.assigned_at)).all()
    
    return assignments


