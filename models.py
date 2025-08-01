from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey, DateTime, Table, Enum, Text
from sqlalchemy.orm import relationship, validates
from datetime import datetime, timezone
from database import Base
import enum

# --- ADD THIS NEW ENUM ---
class TaskStatus(str, enum.Enum):
    new = "new"
    received = "received"
    on_process = "on_process"
    pending = "pending"
    completed = "completed"
    loose_end = "loose_end"

# --- NEW: Enum for Gas Tank Level ---
class GasTankLevel(str, enum.Enum):
    empty = "Empty"
    quarter = "1/4"
    half = "1/2"
    three_quarters = "3/4"
    full = "Full"

# This is the association table for the many-to-many relationship between users and groups
group_members = Table(
    "group_members",
    Base.metadata,
    Column("group_id", Integer, ForeignKey("groups.id")),
    Column("user_id", Integer, ForeignKey("users.id"))
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    first_name = Column(String, nullable=True)
    surname = Column(String, nullable=True)
    birthday = Column(Date, nullable=True)
    role = Column(String, default="user", nullable=False)
    is_active = Column(Boolean, default=True)
    profile_picture_url = Column(String, nullable=True)

    # --- FIX: Specify foreign_keys for each relationship ---

    # Tasks owned by this user
    tasks = relationship(
        "Task", 
        foreign_keys="Task.owner_id",
        back_populates="owner"
    )

    # Tasks where this user updated the status
    status_updated_tasks = relationship(
        "Task",
        foreign_keys="Task.status_updated_by",
        back_populates="status_updater"
    )

    # Other relationships
    groups = relationship("Group", secondary=group_members, back_populates="members")
    events = relationship("Event", back_populates="creator")
    notifications = relationship("Notification", back_populates="user")
    contacts = relationship("Contact", back_populates="owner")
    daily_calls = relationship("DailyCall", back_populates="user")

    @property
    def full_name(self) -> str:
        if self.first_name and self.surname:
            return f"{self.first_name} {self.surname}"
        return self.first_name or self.surname or "No name set"

# --- ADD THIS NEW MODEL ---
class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    company = Column(String, nullable=True)
    job_title = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    # Foreign key to the user who owns this contact
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relationship back to the User model
    owner = relationship("User", back_populates="contacts")
# --- END NEW MODEL ---

class Task(Base):
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    start_date = Column(DateTime)
    deadline = Column(DateTime)
    deadline_all_day = Column(Boolean, default=False)
    urgency = Column(Boolean, default=False)
    important = Column(Boolean, default=False)
    completed = Column(Boolean, default=False)
    
    # Add this line:
    department = Column(String, nullable=True)
    
    # Status system columns
    status = Column(Enum(TaskStatus), default=TaskStatus.new, nullable=False)
    status_comments = Column(Text)
    status_updated_at = Column(DateTime)
    status_updated_by = Column(Integer, ForeignKey("users.id"))
    
    # Foreign keys
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"))
    company_id = Column(Integer, ForeignKey("companies.id"))
    
    # Relationships
    owner = relationship(
        "User", 
        foreign_keys=[owner_id],
        back_populates="tasks"
    )
    status_updater = relationship(
        "User", 
        foreign_keys=[status_updated_by],
        back_populates="status_updated_tasks"
    )
    group = relationship("Group", back_populates="tasks")
    company = relationship("Company", back_populates="tasks")
    history = relationship("TaskHistory", back_populates="task", cascade="all, delete-orphan")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @validates('status')
    def validate_status(self, key, status):
        if status == TaskStatus.completed:
            self.completed = True
        else:
            self.completed = False
        return status

class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    members = relationship("User", secondary=group_members, back_populates="groups")
    tasks = relationship("Task", back_populates="group")

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    user = relationship("User")

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    vat_number = Column(String, unique=True, index=True, nullable=True)
    occupation = Column(String, nullable=True)
    creation_date = Column(Date, nullable=True)
    description = Column(String, nullable=True)
    tasks = relationship("Task", back_populates="company")
    cars = relationship("Car", back_populates="company", cascade="all, delete-orphan")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    location = Column(String, nullable=False)
    event_date = Column(DateTime(timezone=True), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    creator = relationship("User", back_populates="events")

class Car(Base):
    __tablename__ = "cars"
    id = Column(Integer, primary_key=True, index=True)
    manufacturer = Column(String, nullable=False)
    model = Column(String, nullable=False)
    license_plate = Column(String, unique=True, index=True, nullable=False)
    vin = Column(String, unique=True, index=True, nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    company = relationship("Company", back_populates="cars")

# --- NEW: Rental Model ---
class Rental(Base):
    __tablename__ = "rentals"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    customer_surname = Column(String, nullable=False)
    rental_days = Column(Integer, nullable=False)
    return_datetime = Column(DateTime(timezone=True), nullable=False)
    
    start_kilometers = Column(Integer, nullable=False)
    end_kilometers = Column(Integer, nullable=True)  # Nullable until the car is returned
    
    gas_tank_start = Column(Enum(GasTankLevel), nullable=False)
    gas_tank_end = Column(Enum(GasTankLevel), nullable=True)  # Nullable until the car is returned
    
    is_locked = Column(Boolean, default=False, nullable=False)  # To lock the form after final update

    # Foreign keys
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)

    # Relationships
    car = relationship("Car")
    company = relationship("Company")

# --- NEW: Notification Model ---
class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    link = Column(String, nullable=True)  # Optional link to a relevant page

    # Foreign key to the user this notification is for
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Relationship back to the User model
    user = relationship("User", back_populates="notifications")

# --- ADD THIS ENTIRE NEW MODEL ---
class DailyCall(Base):
    __tablename__ = "daily_calls"

    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to the user who this call entry belongs to
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Foreign key to the contact to be called
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)

    # User-defined fields for the call list
    call_frequency_per_day = Column(Integer, default=1)
    next_call_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="daily_calls")
    contact = relationship("Contact")

# --- NEW: Task History Model ---
class TaskHistory(Base):
    __tablename__ = "task_history"
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status_from = Column(Enum(TaskStatus), nullable=True)
    status_to = Column(Enum(TaskStatus), nullable=True)
    comment = Column(Text, nullable=True)

    task = relationship("Task", back_populates="history")
    changed_by = relationship("User", foreign_keys=[changed_by_id])

def update_task_status(task, update_data):
    if "completed" in update_data:
        task.status = "completed" if task.completed else "new"
    elif "status" in update_data:
        task.completed = task.status == "completed"
