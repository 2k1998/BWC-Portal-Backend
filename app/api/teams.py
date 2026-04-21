from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.models.team import Team
from app.models.team_member import TeamMember
from app.schemas.team import TeamCreate, TeamUpdate, TeamResponse, TeamListResponse, AddMembersRequest, TeamMemberResponse

router = APIRouter(prefix="/teams", tags=["Teams"])


def is_team_head_or_admin(team: Team, current_user: User) -> bool:
    """Check if user is team head or admin."""
    return current_user.user_type == "Admin" or str(team.head_user_id) == str(current_user.id)


def is_team_member_or_admin(team_id: str, current_user: User, db: Session) -> bool:
    """Check if user is a team member or admin."""
    if current_user.user_type == "Admin":
        return True
    
    # Check if user is a member of this team
    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == current_user.id
    ).first()
    
    return member is not None


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
def create_team(
    team_data: TeamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new team (admin only).
    Team name must be unique.
    Head is automatically added as a team member with role 'head'.
    """
    # Check if team name already exists
    existing = db.query(Team).filter(Team.name == team_data.name).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Team with name '{team_data.name}' already exists"
        )
    
    # Verify head user exists
    head_user = db.query(User).filter(User.id == team_data.head_user_id).first()
    if not head_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Head user not found"
        )
    
    # Create team
    team = Team(
        name=team_data.name,
        head_user_id=team_data.head_user_id,
        created_by_user_id=current_user.id
    )
    
    db.add(team)
    db.flush()  # Get team ID
    
    # Add head as team member with role 'head'
    head_member = TeamMember(
        team_id=team.id,
        user_id=team_data.head_user_id,
        role="head"
    )
    db.add(head_member)
    
    # Add other members
    for member_id in team_data.member_ids:
        # Skip if it's the head (already added)
        if str(member_id) == str(team_data.head_user_id):
            continue
        
        # Verify user exists
        user = db.query(User).filter(User.id == member_id).first()
        if not user:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {member_id} not found"
            )
        
        member = TeamMember(
            team_id=team.id,
            user_id=member_id,
            role="member"
        )
        db.add(member)
    
    db.commit()
    db.refresh(team)
    
    # Load members for response
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    team_response = TeamResponse.model_validate(team)
    team_response.members = [TeamMemberResponse(user_id=m.user_id, role=m.role) for m in members]
    
    return team_response


@router.get("", response_model=TeamListResponse)
def list_teams(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List teams.
    - Admin sees all teams
    - Regular users see only teams they belong to
    """
    if current_user.user_type == "Admin":
        # Admin sees all teams
        query = db.query(Team)
    else:
        # Regular users see only their teams
        query = db.query(Team).join(TeamMember).filter(TeamMember.user_id == current_user.id)
    
    # Get total count
    total = query.count()
    
    # Apply pagination
    teams = query.order_by(Team.name).offset((page - 1) * page_size).limit(page_size).all()
    
    # Load members for all returned teams in one query to avoid N+1.
    team_ids = [team.id for team in teams]
    members_by_team = {team_id: [] for team_id in team_ids}
    if team_ids:
        members = db.query(TeamMember).filter(TeamMember.team_id.in_(team_ids)).all()
        for member in members:
            members_by_team.setdefault(member.team_id, []).append(member)

    team_responses = []
    for team in teams:
        team_members = members_by_team.get(team.id, [])
        team_response = TeamResponse.model_validate(team)
        team_response.members = [TeamMemberResponse(user_id=m.user_id, role=m.role) for m in team_members]
        team_responses.append(team_response)
    
    return TeamListResponse(
        teams=team_responses,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(
    team_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get team details.
    - Admin can view any team
    - Regular users can only view teams they belong to
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check if user has access
    if not is_team_member_or_admin(team_id, current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this team"
        )
    
    # Load members
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    team_response = TeamResponse.model_validate(team)
    team_response.members = [TeamMemberResponse(user_id=m.user_id, role=m.role) for m in members]
    
    return team_response


@router.put("/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: str,
    team_data: TeamUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update team (admin or team head only).
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check authorization
    if not is_team_head_or_admin(team, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team head or admin can update this team"
        )
    
    # Check if new name conflicts
    if team_data.name and team_data.name != team.name:
        existing = db.query(Team).filter(
            Team.name == team_data.name,
            Team.id != team_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Team with name '{team_data.name}' already exists"
            )
    
    # Update fields
    if team_data.name is not None:
        team.name = team_data.name
    
    if team_data.head_user_id is not None:
        # Verify new head exists
        new_head = db.query(User).filter(User.id == team_data.head_user_id).first()
        if not new_head:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="New head user not found"
            )
        
        # Update old head's role to 'member'
        old_head_member = db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == team.head_user_id
        ).first()
        if old_head_member:
            old_head_member.role = "member"
        
        # Update team head
        team.head_user_id = team_data.head_user_id
        
        # Check if new head is already a member
        new_head_member = db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == team_data.head_user_id
        ).first()
        
        if new_head_member:
            # Update existing member to head
            new_head_member.role = "head"
        else:
            # Add new head as member
            new_member = TeamMember(
                team_id=team_id,
                user_id=team_data.head_user_id,
                role="head"
            )
            db.add(new_member)
    
    db.commit()
    db.refresh(team)
    
    # Load members
    members = db.query(TeamMember).filter(TeamMember.team_id == team.id).all()
    team_response = TeamResponse.model_validate(team)
    team_response.members = [TeamMemberResponse(user_id=m.user_id, role=m.role) for m in members]
    
    return team_response


@router.post("/{team_id}/members", status_code=status.HTTP_200_OK)
def add_team_members(
    team_id: str,
    members_data: AddMembersRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add members to a team (admin or team head only).
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check authorization
    if not is_team_head_or_admin(team, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team head or admin can add members"
        )
    
    added_count = 0
    skipped_count = 0
    
    for user_id in members_data.user_ids:
        # Verify user exists
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found"
            )
        
        # Check if already a member
        existing = db.query(TeamMember).filter(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id
        ).first()
        
        if existing:
            skipped_count += 1
            continue
        
        # Add as member
        member = TeamMember(
            team_id=team_id,
            user_id=user_id,
            role="member"
        )
        db.add(member)
        added_count += 1
    
    db.commit()
    
    return {
        "message": f"Added {added_count} members, skipped {skipped_count} (already members)",
        "added": added_count,
        "skipped": skipped_count
    }


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_200_OK)
def remove_team_member(
    team_id: str,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove a member from a team (admin or team head only).
    Cannot remove the team head.
    """
    team = db.query(Team).filter(Team.id == team_id).first()
    
    if not team:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found"
        )
    
    # Check authorization
    if not is_team_head_or_admin(team, current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only team head or admin can remove members"
        )
    
    # Cannot remove the head
    if str(user_id) == str(team.head_user_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove team head. Change the head first if needed."
        )
    
    # Find and remove member
    member = db.query(TeamMember).filter(
        TeamMember.team_id == team_id,
        TeamMember.user_id == user_id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User is not a member of this team"
        )
    
    db.delete(member)
    db.commit()
    
    return {"message": f"Member removed from team successfully"}
