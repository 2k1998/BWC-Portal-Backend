# routers/contacts.py
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session
from typing import List

import models, schemas
from database import get_db
from .auth import get_current_user
from .utils import check_roles

router = APIRouter(prefix="/contacts", tags=["contacts"])

@router.post("/", response_model=schemas.ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    contact: schemas.ContactCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Creates a new contact for the currently authenticated user.
    Accessible by Pillar, Manager, Head, and admin roles.
    """
    check_roles(current_user, ["Pillar", "Manager", "Head", "admin"])
    new_contact = models.Contact(**contact.dict(), owner_id=current_user.id)
    db.add(new_contact)
    db.commit()
    db.refresh(new_contact)
    return new_contact

@router.get("/", response_model=List[schemas.ContactOut])
def get_my_contacts(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Retrieves all contacts owned by the currently authenticated user.
    """
    check_roles(current_user, ["Pillar", "Manager", "Head", "admin"])
    return db.query(models.Contact).filter(models.Contact.owner_id == current_user.id).all()

@router.put("/{contact_id}", response_model=schemas.ContactOut)
def update_contact(
    contact_id: int,
    contact_update: schemas.ContactUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Updates a contact owned by the current user.
    """
    db_contact = db.query(models.Contact).filter(
        models.Contact.id == contact_id,
        models.Contact.owner_id == current_user.id
    ).first()

    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found or you do not have permission to edit it.")

    update_data = contact_update.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_contact, key, value)
    
    db.commit()
    db.refresh(db_contact)
    return db_contact

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Deletes a contact owned by the current user.
    """
    db_contact = db.query(models.Contact).filter(
        models.Contact.id == contact_id,
        models.Contact.owner_id == current_user.id
    ).first()

    if not db_contact:
        raise HTTPException(status_code=404, detail="Contact not found or you do not have permission to delete it.")
    
    db.delete(db_contact)
    db.commit()

@router.post("/import-csv", response_model=dict)
def import_contacts_from_csv(
    payload: schemas.ContactImport,  # Use the new schema for validation
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Imports a batch of contacts from a CSV file for the current user.
    """
    # Ensure the user has the correct role to add contacts
    check_roles(current_user, ["Pillar", "Manager", "Head", "admin"])

    new_contacts = []
    for contact_data in payload.contacts:
        # Use model_dump() instead of dict()
        new_contact = models.Contact(
            **contact_data.model_dump(),
            owner_id=current_user.id  # Assign the current user as the owner
        )
        new_contacts.append(new_contact)

    if not new_contacts:
        raise HTTPException(status_code=400, detail="No contacts to import.")

    db.add_all(new_contacts)  # Add all new contacts to the session at once
    db.commit()

    return {"message": f"Successfully imported {len(new_contacts)} contacts."}

@router.post("/import-batch", response_model=dict)
def import_contacts_batch(
    payload: schemas.ContactImport,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Imports a batch of contacts for the current user, updating existing ones
    based on the email address.
    """
    check_roles(current_user, ["Pillar", "Manager", "Head", "admin"])

    if not payload.contacts:
        raise HTTPException(status_code=400, detail="No contacts to import.")

    updated_count = 0
    created_count = 0

    for contact_data in payload.contacts:
        # Check for existing contact by email, but only for the current user
        existing_contact = None
        if contact_data.email:
            existing_contact = db.query(models.Contact).filter(
                models.Contact.email == contact_data.email,
                models.Contact.owner_id == current_user.id
            ).first()

        if existing_contact:
            # Use model_dump() instead of dict()
            for key, value in contact_data.model_dump(exclude_unset=True).items():
                setattr(existing_contact, key, value)
            updated_count += 1
        else:
            # Use model_dump() instead of dict()
            new_contact = models.Contact(
                **contact_data.model_dump(),
                owner_id=current_user.id
            )
            db.add(new_contact)
            created_count += 1

    db.commit()

    return {
        "message": f"Import complete. {created_count} contacts created, {updated_count} updated."
    }

# --- ADD THIS NEW ENDPOINT ---
@router.post("/delete-batch", status_code=status.HTTP_204_NO_CONTENT)
def delete_contacts_batch(
    payload: schemas.ContactIdList,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    if not payload.contact_ids:
        raise HTTPException(status_code=400, detail="No contact IDs provided.")

    # Delete contacts that are in the provided list AND belong to the current user
    num_deleted = db.query(models.Contact).filter(
        models.Contact.id.in_(payload.contact_ids),
        models.Contact.owner_id == current_user.id
    ).delete(synchronize_session=False)

    if num_deleted == 0 and len(payload.contact_ids) > 0:
        # This can happen if user tries to delete contacts that are not theirs
        # or don't exist. We don't raise an error for security.
        pass

    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)