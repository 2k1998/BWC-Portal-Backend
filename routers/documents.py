from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
from pathlib import Path
import shutil
from datetime import datetime

from database import get_db
import models, schemas
from .auth import get_current_user
from .utils import check_roles

router = APIRouter(prefix="/documents", tags=["documents"])

# Allowed file extensions
ALLOWED_EXTENSIONS = {
	'.pdf', '.doc', '.docx', '.xls', '.xlsx', 
	'.ppt', '.pptx', '.txt', '.jpg', '.jpeg', 
	'.png', '.zip', '.rar'
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def validate_file(file: UploadFile) -> tuple[bool, str]:
	"""Validate uploaded file"""
	# Check file extension
	file_ext = Path(file.filename).suffix.lower()
	if file_ext not in ALLOWED_EXTENSIONS:
		return False, f"File type {file_ext} not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
	
	# Check file size (basic check - actual size will be checked during upload)
	estimated_size = getattr(file, "size", None)
	if estimated_size and estimated_size > MAX_FILE_SIZE:
		return False, f"File size exceeds maximum allowed size of {MAX_FILE_SIZE / 1024 / 1024}MB"
	
	return True, ""

@router.post("/", response_model=schemas.DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
	file: UploadFile = File(...),
	title: str = Form(...),
	description: Optional[str] = Form(None),
	category: Optional[str] = Form(None),
	is_public: bool = Form(True),
	db: Session = Depends(get_db),
	current_user: models.User = Depends(get_current_user)
):
	"""Upload a new document. Only admin can upload."""
	check_roles(current_user, ["admin"])
	
	# Validate file
	is_valid, error_msg = validate_file(file)
	if not is_valid:
		raise HTTPException(status_code=400, detail=error_msg)
	
	# Create upload directory if it doesn't exist
	upload_dir = Path("uploads/documents")
	upload_dir.mkdir(parents=True, exist_ok=True)
	
	# Generate unique filename
	file_ext = Path(file.filename).suffix.lower()
	unique_filename = f"{uuid.uuid4()}{file_ext}"
	file_path = upload_dir / unique_filename
	
	# Save file
	try:
		with open(file_path, "wb") as buffer:
			shutil.copyfileobj(file.file, buffer)
		
		# Get actual file size
		file_size = os.path.getsize(file_path)
		
		# Create database record
		db_document = models.Document(
			title=title,
			description=description,
			filename=unique_filename,
			original_filename=file.filename,
			file_path=str(file_path),
			file_size=file_size,
			file_type=file.content_type or "application/octet-stream",
			category=category,
			is_public=is_public,
			uploaded_by_id=current_user.id
		)
		
		db.add(db_document)
		db.commit()
		db.refresh(db_document)
		
		# Add download URL
		db_document.download_url = f"/documents/{db_document.id}/download"
		db_document.can_delete = True  # Admin uploaded it, so can delete
		
		return db_document
		
	except Exception as e:
		# Clean up file if database operation fails
		if file_path.exists():
			os.remove(file_path)
		raise HTTPException(status_code=500, detail=f"Failed to upload document: {str(e)}")

@router.get("/", response_model=List[schemas.DocumentResponse])
async def get_documents(
	category: Optional[str] = None,
	search: Optional[str] = None,
	skip: int = 0,
	limit: int = 100,
	db: Session = Depends(get_db),
	current_user: models.User = Depends(get_current_user)
):
	"""Get all public documents. Anyone logged in can view."""
	query = db.query(models.Document).filter(models.Document.is_public == True)
	
	if category:
		query = query.filter(models.Document.category == category)
	
	if search:
		search_pattern = f"%{search}%"
		query = query.filter(
			(models.Document.title.ilike(search_pattern)) |
			(models.Document.description.ilike(search_pattern))
		)
	
	documents = query.order_by(models.Document.upload_date.desc()).offset(skip).limit(limit).all()
	
	# Add download URL and permission flags
	for doc in documents:
		doc.download_url = f"/documents/{doc.id}/download"
		doc.can_delete = current_user.role == "admin"
	
	return documents

@router.get("/{document_id}", response_model=schemas.DocumentResponse)
async def get_document(
	document_id: int,
	db: Session = Depends(get_db),
	current_user: models.User = Depends(get_current_user)
):
	"""Get a specific document by ID."""
	document = db.query(models.Document).filter(models.Document.id == document_id).first()
	
	if not document:
		raise HTTPException(status_code=404, detail="Document not found")
	
	if not document.is_public and current_user.role != "admin":
		raise HTTPException(status_code=403, detail="Access denied")
	
	document.download_url = f"/documents/{document.id}/download"
	document.can_delete = current_user.role == "admin"
	
	return document

@router.get("/{document_id}/download")
async def download_document(
	document_id: int,
	db: Session = Depends(get_db),
	current_user: models.User = Depends(get_current_user)
):
	"""Download a document. Anyone logged in can download public documents."""
	document = db.query(models.Document).filter(models.Document.id == document_id).first()
	
	if not document:
		raise HTTPException(status_code=404, detail="Document not found")
	
	if not document.is_public and current_user.role != "admin":
		raise HTTPException(status_code=403, detail="Access denied")
	
	# Check if file exists
	if not os.path.exists(document.file_path):
		raise HTTPException(status_code=404, detail="File not found on server")
	
	# Update download statistics
	document.download_count += 1
	document.last_downloaded_at = datetime.utcnow()
	db.commit()
	
	# Return file
	return FileResponse(
		path=document.file_path,
		filename=document.original_filename,
		media_type=document.file_type
	)

@router.put("/{document_id}", response_model=schemas.DocumentResponse)
async def update_document(
	document_id: int,
	document_update: schemas.DocumentUpdate,
	db: Session = Depends(get_db),
	current_user: models.User = Depends(get_current_user)
):
	"""Update document metadata. Only admin can update."""
	check_roles(current_user, ["admin"])
	
	document = db.query(models.Document).filter(models.Document.id == document_id).first()
	
	if not document:
		raise HTTPException(status_code=404, detail="Document not found")
	
	# Update fields
	update_data = document_update.model_dump(exclude_unset=True)
	for field, value in update_data.items():
		setattr(document, field, value)
	
	db.commit()
	db.refresh(document)
	
	document.download_url = f"/documents/{document.id}/download"
	document.can_delete = True
	
	return document

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
	document_id: int,
	db: Session = Depends(get_db),
	current_user: models.User = Depends(get_current_user)
):
	"""Delete a document. Only admin can delete."""
	check_roles(current_user, ["admin"])
	
	document = db.query(models.Document).filter(models.Document.id == document_id).first()
	
	if not document:
		raise HTTPException(status_code=404, detail="Document not found")
	
	# Delete file from filesystem
	try:
		if os.path.exists(document.file_path):
			os.remove(document.file_path)
	except Exception as e:
		# Log error but continue with database deletion
		print(f"Error deleting file: {e}")
	
	# Delete from database
	db.delete(document)
	db.commit()
	
	return None

@router.get("/categories/list", response_model=List[str])
async def get_categories(
	db: Session = Depends(get_db),
	current_user: models.User = Depends(get_current_user)
):
	"""Get list of all document categories."""
	categories = db.query(models.Document.category).filter(
		models.Document.category.isnot(None)
	).distinct().all()
	
	return [cat[0] for cat in categories]


