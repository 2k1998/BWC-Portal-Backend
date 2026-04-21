from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import UUID4

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.approval_request import ApprovalRequest
from app.schemas.approval import (
    ApprovalCreateRequest,
    ApprovalListResponse,
    ApprovalResponse,
)
from app.utils.notification_service import create_notification
from app.utils.activity_logger import log_activity

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def _to_approval_response(approval: ApprovalRequest) -> ApprovalResponse:
    return ApprovalResponse(
        id=approval.id,
        requester_user_id=approval.requester_user_id,
        receiver_user_id=approval.receiver_user_id,
        request_type=approval.request_type,
        title=approval.title,
        description=approval.description,
        status=approval.status,
        resolved_at=approval.resolved_at,
        created_at=approval.created_at,
    )


@router.post("", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
def create_approval(
    approval_in: ApprovalCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    receiver = db.query(User).filter(User.id == approval_in.receiver_user_id).first()
    if not receiver:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receiver user not found")

    approval = ApprovalRequest(
        requester_user_id=current_user.id,
        receiver_user_id=approval_in.receiver_user_id,
        request_type=approval_in.request_type,
        title=approval_in.title,
        description=approval_in.description,
        status="pending",
        resolved_at=None,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)

    # Activity Log (PRD)
    log_activity(
        db=db,
        entity_type="ApprovalRequest",
        entity_id=str(approval.id),
        action_type="CREATE",
        performed_by_user_id=str(current_user.id),
        old_value=None,
        new_value={
            "request_type": approval.request_type,
            "title": approval.title,
            "receiver_user_id": str(approval.receiver_user_id),
            "status": approval.status,
        },
    )
    db.commit()

    # Notification (PRD)
    create_notification(
        db=db,
        recipient_ids=[approval.receiver_user_id],
        actor_id=current_user.id,
        entity_type="ApprovalRequest",
        entity_id=str(approval.id),
        title="Approval request received",
        message=f"'{approval.title}' requires your approval.",
        link=f"/approvals/{approval.id}",
        notification_type="ASSIGNMENT",
    )
    db.commit()

    return _to_approval_response(approval)


@router.get("", response_model=ApprovalListResponse)
def list_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    sent = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.requester_user_id == current_user.id)
        .order_by(ApprovalRequest.created_at.desc())
        .all()
    )
    received = (
        db.query(ApprovalRequest)
        .filter(ApprovalRequest.receiver_user_id == current_user.id)
        .order_by(ApprovalRequest.created_at.desc())
        .all()
    )

    return ApprovalListResponse(
        sent_approvals=[_to_approval_response(a) for a in sent],
        received_approvals=[_to_approval_response(a) for a in received],
    )


@router.get("/{id}", response_model=ApprovalResponse)
def get_approval(
    id: UUID4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approval = (
        db.query(ApprovalRequest)
        .filter(
            ApprovalRequest.id == id,
            or_(
                ApprovalRequest.requester_user_id == current_user.id,
                ApprovalRequest.receiver_user_id == current_user.id,
            ),
        )
        .first()
    )
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

    return _to_approval_response(approval)


def _resolve_approval(
    *,
    approval: ApprovalRequest,
    db: Session,
    current_user: User,
    new_status: str,
) -> ApprovalRequest:
    if str(approval.receiver_user_id) != str(current_user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only receiver can resolve")

    if approval.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Approval is already resolved")

    old_status = approval.status
    approval.status = new_status
    approval.resolved_at = datetime.now(timezone.utc)

    db.add(approval)
    db.commit()
    db.refresh(approval)

    log_activity(
        db=db,
        entity_type="ApprovalRequest",
        entity_id=str(approval.id),
        action_type="STATUS_CHANGE",
        performed_by_user_id=str(current_user.id),
        old_value={"status": old_status},
        new_value={"status": new_status},
    )
    db.commit()

    # Notification (PRD): Approval resolved -> receiver notifies requester.
    create_notification(
        db=db,
        recipient_ids=[approval.requester_user_id],
        actor_id=current_user.id,
        entity_type="ApprovalRequest",
        entity_id=str(approval.id),
        title="Approval resolved",
        message=f"'{approval.title}' was {new_status}.",
        link=f"/approvals/{approval.id}",
        notification_type="STATUS_CHANGE",
    )
    db.commit()

    return approval


@router.post("/{id}/approve", response_model=ApprovalResponse)
def approve_approval(
    id: UUID4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == id).first()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

    return _resolve_approval(
        approval=approval,
        db=db,
        current_user=current_user,
        new_status="approved",
    )


@router.post("/{id}/deny", response_model=ApprovalResponse)
def deny_approval(
    id: UUID4,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approval = db.query(ApprovalRequest).filter(ApprovalRequest.id == id).first()
    if not approval:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

    return _resolve_approval(
        approval=approval,
        db=db,
        current_user=current_user,
        new_status="denied",
    )

