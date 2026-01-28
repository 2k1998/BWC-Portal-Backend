# models.py - FIXED VERSION (Remove the incorrect import line)
from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey, DateTime, Table, Enum, Text, Numeric, JSON, text
from sqlalchemy.orm import relationship, validates
from datetime import datetime, timezone
from database import Base
import enum

# --- EXISTING ENUMS (keep these) ---
class TaskStatus(str, enum.Enum):
    new = "new"
    received = "received"
    on_process = "on_process"
    pending = "pending"
    completed = "completed"
    loose_end = "loose_end"

class GasTankLevel(str, enum.Enum):
    empty = "Empty"
    quarter = "1/4"
    half = "1/2"
    three_quarters = "3/4"
    full = "Full"

class ProjectStatus(str, enum.Enum):
    planning = "planning"
    in_progress = "in_progress" 
    completed = "completed"
    on_hold = "on_hold"
    cancelled = "cancelled"

class ProjectType(str, enum.Enum):
    new_store = "new_store"
    renovation = "renovation"
    maintenance = "maintenance"
    expansion = "expansion"
    other = "other"

# --- NEW ENUMS (add these) ---
class SaleType(str, enum.Enum):
    store_opening = "store_opening"
    renovation = "renovation"
    maintenance_contract = "maintenance_contract"
    consulting = "consulting"
    car_rental = "car_rental"
    other = "other"

class SaleStatus(str, enum.Enum):
    lead = "lead"
    proposal_sent = "proposal_sent"
    negotiating = "negotiating"
    closed_won = "closed_won"
    closed_lost = "closed_lost"
    cancelled = "cancelled"

class CommissionStatus(str, enum.Enum):
    pending = "pending"
    calculated = "calculated"
    paid = "paid"
    disputed = "disputed"

class PaymentType(str, enum.Enum):
    commission_payment = "commission_payment"
    base_salary = "base_salary"
    bonus = "bonus"
    car_rental_income = "car_rental_income"
    business_expense = "business_expense"
    office_rent = "office_rent"
    utility_bill = "utility_bill"
    equipment_purchase = "equipment_purchase"
    other_income = "other_income"
    other_expense = "other_expense"

class PaymentStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"
    disputed = "disputed"

# --- TASK ASSIGNMENT/CONVERSATION ENUMS ---
class TaskAssignmentStatus(str, enum.Enum):
    pending_acceptance = "pending_acceptance"
    accepted = "accepted"
    rejected = "rejected"
    discussion_requested = "discussion_requested"
    discussion_active = "discussion_active"
    discussion_completed = "discussion_completed"

class MessageType(str, enum.Enum):
    text = "text"
    system = "system"
    call_request = "call_request"
    call_scheduled = "call_scheduled"
    call_completed = "call_completed"

class ConversationStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    archived = "archived"

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
    is_active = Column(Boolean, default=True, nullable=False)
    profile_picture_url = Column(String, nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    is_online = Column(Boolean, default=False)

    # --- Add this line for permissions ---
    permissions = Column(JSON, default=dict)  # Store dictionary of permission strings

    # Google Calendar integration
    google_credentials = Column(JSON, nullable=True)
    google_calendar_sync_enabled = Column(Boolean, default=False, nullable=False)

    @property
    def full_name(self) -> str:
        if self.first_name and self.surname:
            return f"{self.first_name} {self.surname}"
        return self.first_name or self.surname or self.email

    # Fixed relationships with explicit foreign_keys
    tasks = relationship("Task", foreign_keys="[Task.owner_id]", back_populates="owner")
    groups = relationship("Group", secondary=group_members, back_populates="members")
    events = relationship("Event", back_populates="creator")
    notifications = relationship("Notification", back_populates="user")
    contacts = relationship("Contact", back_populates="owner")
    daily_calls = relationship("DailyCall", back_populates="user")
    uploaded_documents = relationship("Document", back_populates="uploaded_by")

    # Task assignment workflow relationships
    task_assignments_given = relationship(
        "TaskAssignment",
        foreign_keys="[TaskAssignment.assigned_by_id]",
        back_populates="assigned_by"
    )
    task_assignments_received = relationship(
        "TaskAssignment",
        foreign_keys="[TaskAssignment.assigned_to_id]",
        back_populates="assigned_to"
    )
    task_notifications = relationship("TaskNotification", back_populates="user")

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
    
    status = Column(Enum(TaskStatus), default=TaskStatus.new)
    status_comments = Column(Text)
    status_updated_at = Column(DateTime)
    status_updated_by = Column(Integer, ForeignKey("users.id"))
    
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    group_id = Column(Integer, ForeignKey("groups.id"))
    company_id = Column(Integer, ForeignKey("companies.id"))
    
    # Fixed relationships with explicit foreign_keys
    owner = relationship("User", foreign_keys=[owner_id], back_populates="tasks")
    created_by = relationship("User", foreign_keys=[created_by_id])
    status_updater = relationship("User", foreign_keys=[status_updated_by])
    deleted_by = relationship("User", foreign_keys="[Task.deleted_by_id]")
    group = relationship("Group")
    company = relationship("Company")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    history = relationship("TaskHistory", back_populates="task", cascade="all, delete-orphan")
    assignments = relationship("TaskAssignment", back_populates="task", cascade="all, delete-orphan")

    # Completion tracking
    completed = Column(Boolean, nullable=False, server_default=text("false"), default=False)
    completed_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

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
    head_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    members = relationship("User", secondary=group_members, back_populates="groups")
    tasks = relationship("Task", back_populates="group")
    head = relationship("User", foreign_keys=[head_id])

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

    @property
    def display_name(self):
        if self.name == "Best Solution Cars":
            return "Best Solutions Cars"
        return self.name

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True, nullable=False)
    description = Column(String, nullable=True)
    location = Column(String, nullable=False)
    event_date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    creator = relationship("User", back_populates="events")

class Car(Base):
    __tablename__ = "cars"
    id = Column(Integer, primary_key=True, index=True)
    manufacturer = Column(String, nullable=False)
    model = Column(String, nullable=False)
    license_plate = Column(String, unique=True, index=True, nullable=False)
    vin = Column(String, unique=True, index=True, nullable=False)
    kteo_last_date = Column(Date, nullable=True)
    kteo_next_date = Column(Date, nullable=True)
    service_last_date = Column(Date, nullable=True)
    service_next_date = Column(Date, nullable=True)
    tire_change_date = Column(Date, nullable=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    company = relationship("Company", back_populates="cars")
    rentals = relationship("Rental", back_populates="car", cascade="all, delete-orphan")
    
    # Add these relationships
    income_records = relationship("CarIncome", back_populates="car", cascade="all, delete-orphan")
    expense_records = relationship("CarExpense", back_populates="car", cascade="all, delete-orphan")

class Rental(Base):
    __tablename__ = "rentals"
    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String, nullable=False)
    customer_surname = Column(String, nullable=False)
    rental_days = Column(Integer, nullable=False)
    return_datetime = Column(DateTime, nullable=False)
    start_kilometers = Column(Integer, nullable=False)
    gas_tank_start = Column(Enum(GasTankLevel), nullable=False)
    end_kilometers = Column(Integer, nullable=True)
    gas_tank_end = Column(Enum(GasTankLevel), nullable=True)
    is_locked = Column(Boolean, default=False)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    car = relationship("Car", back_populates="rentals")
    
    # Add this relationship
    income_records = relationship("CarIncome", back_populates="rental", cascade="all, delete-orphan")

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(String, nullable=False)
    link = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="notifications")

# --- ADD THIS NEW MODEL ---
class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    file_type = Column(String(100), nullable=False)
    category = Column(String(100), nullable=True)
    
    # Access control
    is_public = Column(Boolean, default=True, nullable=False)  # Everyone can view/download
    can_delete_admin_only = Column(Boolean, default=True, nullable=False)  # Only admin can delete
    
    # Metadata
    upload_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    uploaded_by = relationship("User", back_populates="uploaded_documents")
    
    # Download tracking
    download_count = Column(Integer, default=0, nullable=False)
    last_downloaded_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<Document(title='{self.title}', filename='{self.filename}')>"

# --- ADD THIS NEW MODEL ---
class DailyCall(Base):
    __tablename__ = "daily_calls"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    contact_id = Column(Integer, ForeignKey("contacts.id"), nullable=False)

    # How many times per day this contact should be called
    call_frequency_per_day = Column(Integer, default=1)
    
    # When is the next call due?
    next_call_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="daily_calls")
    contact = relationship("Contact")
# --- END NEW MODEL ---

# --- ADD THIS NEW MODEL ---
class TaskHistory(Base):
    __tablename__ = "task_histories"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    changed_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    status_from = Column(Enum(TaskStatus), nullable=True)
    status_to = Column(Enum(TaskStatus), nullable=True)
    comment = Column(Text, nullable=True)

    # Relationships
    task = relationship("Task", back_populates="history")
    changed_by = relationship("User")
# --- END NEW MODEL ---

# Add Project model
class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    project_type = Column(Enum(ProjectType), nullable=False)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.planning)
    
    # Location/Store info
    store_location = Column(String(255))
    store_address = Column(Text)
    
    # Company relationship
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
    company = relationship("Company")
    
    # Project manager - Fixed with explicit foreign_keys
    project_manager_id = Column(Integer, ForeignKey("users.id"))
    project_manager = relationship("User", foreign_keys=[project_manager_id])
    
    # Dates
    start_date = Column(Date)
    expected_completion_date = Column(Date)
    actual_completion_date = Column(Date)
    
    # Budget
    estimated_budget = Column(Numeric(10, 2))
    actual_cost = Column(Numeric(10, 2))
    
    # Progress tracking
    progress_percentage = Column(Integer, default=0)
    
    # Notes and updates
    notes = Column(Text)
    last_update = Column(Text)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Fixed relationships with explicit foreign_keys
    created_by = relationship("User", foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f"<Project(name='{self.name}', status='{self.status}', company='{self.company.name if self.company else 'No Company'}')>"

# --- SALES & COMMISSION SYSTEM MODELS ---

class Sale(Base):
    __tablename__ = "sales"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Sale details
    title = Column(String(255), nullable=False)
    description = Column(Text)
    sale_type = Column(Enum(SaleType), nullable=False)
    status = Column(Enum(SaleStatus), default=SaleStatus.lead)
    
    # Financial info
    sale_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="EUR")
    
    # Client info
    client_name = Column(String(255), nullable=False)
    client_company = Column(String(255))
    client_email = Column(String(255))
    client_phone = Column(String(50))
    
    # Relationships
    salesperson_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    salesperson = relationship("User", foreign_keys=[salesperson_id])
    
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    company = relationship("Company")
    
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project = relationship("Project")
    
    # Important dates
    lead_date = Column(Date, nullable=False)
    proposal_date = Column(Date, nullable=True)
    close_date = Column(Date, nullable=True)
    expected_close_date = Column(Date, nullable=True)
    
    # Commission calculation
    commission_rate = Column(Numeric(5, 2), default=10.00)
    commission_amount = Column(Numeric(10, 2), nullable=True)
    commission_status = Column(Enum(CommissionStatus), default=CommissionStatus.pending)
    
    # Notes and tracking
    notes = Column(Text)
    source = Column(String(100))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by = relationship("User", foreign_keys=[created_by_id])
    
    def __repr__(self):
        return f"<Sale(title='{self.title}', amount={self.sale_amount}, status='{self.status}')>"
    
    def calculate_commission(self):
        """Calculate commission based on sale amount and rate"""
        if self.status == SaleStatus.closed_won and self.sale_amount:
            self.commission_amount = (self.sale_amount * self.commission_rate) / 100
            self.commission_status = CommissionStatus.calculated
        else:
            self.commission_amount = 0
        return self.commission_amount

class EmployeeCommissionRule(Base):
    __tablename__ = "employee_commission_rules"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Employee
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    employee = relationship("User", foreign_keys=[employee_id])  # <-- Fixed with explicit foreign_keys
    
    # Commission rules
    sale_type = Column(Enum(SaleType), nullable=True)  # If null, applies to all sale types
    base_commission_rate = Column(Numeric(5, 2), default=10.00)  # Base percentage
    min_sale_amount = Column(Numeric(10, 2), default=0)  # Minimum sale amount for commission
    
    # Bonus tiers (optional)
    tier1_threshold = Column(Numeric(12, 2), nullable=True)  # Monthly sales target
    tier1_bonus_rate = Column(Numeric(5, 2), default=0)  # Additional % if tier1 reached
    tier2_threshold = Column(Numeric(12, 2), nullable=True)
    tier2_bonus_rate = Column(Numeric(5, 2), default=0)
    tier3_threshold = Column(Numeric(12, 2), nullable=True)
    tier3_bonus_rate = Column(Numeric(5, 2), default=0)
    
    # Settings
    is_active = Column(Boolean, default=True)
    effective_from = Column(Date, default=datetime.utcnow)
    effective_until = Column(Date, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by = relationship("User", foreign_keys=[created_by_id])  # <-- Fixed with explicit foreign_keys

class MonthlyCommissionSummary(Base):
    __tablename__ = "monthly_commission_summaries"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Period and employee
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    employee = relationship("User", foreign_keys=[employee_id])  # <-- Fixed with explicit foreign_keys
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)  # 1-12
    
    # Sales summary
    total_sales_amount = Column(Numeric(12, 2), default=0)
    closed_deals_count = Column(Integer, default=0)
    active_leads_count = Column(Integer, default=0)
    
    # Commission breakdown
    base_commission = Column(Numeric(10, 2), default=0)
    tier_bonus = Column(Numeric(10, 2), default=0)  # Bonus for reaching tiers
    total_commission = Column(Numeric(10, 2), default=0)
    
    # Payment status
    payment_status = Column(Enum(CommissionStatus), default=CommissionStatus.pending)
    payment_date = Column(Date, nullable=True)
    payment_notes = Column(Text)
    
    # Breakdown by sale type (JSON)
    sales_breakdown = Column(Text)  # JSON string with sale type breakdown
    
    # Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    calculated_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    calculated_by = relationship("User", foreign_keys=[calculated_by_id])  # <-- Fixed with explicit foreign_keys

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic info
    title = Column(String(255), nullable=False)
    description = Column(Text)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default="EUR")
    
    # Payment classification
    payment_type = Column(Enum(PaymentType), nullable=False)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending)
    
    # Dates
    due_date = Column(Date, nullable=False)
    paid_date = Column(Date, nullable=True)
    
    # Employee relationship (for commission/salary payments)
    employee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    employee = relationship("User", foreign_keys=[employee_id])  # <-- Fixed with explicit foreign_keys
    
    # Commission summary relationship (for commission payments)
    commission_summary_id = Column(Integer, ForeignKey("monthly_commission_summaries.id"), nullable=True)
    commission_summary = relationship("MonthlyCommissionSummary")
    
    # Company relationship
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    company = relationship("Company")
    
    # Categories and tracking
    category = Column(String(100))
    receipt_url = Column(String(500))
    notes = Column(Text)
    
    # Approval workflow
    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_by = relationship("User", foreign_keys=[approved_by_id])  # <-- Fixed with explicit foreign_keys
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_by = relationship("User", foreign_keys=[created_by_id])  # <-- Fixed with explicit foreign_keys
    
    def __repr__(self):
        return f"<Payment(title='{self.title}', amount={self.amount}, status='{self.status}')>"

    @property
    def is_income(self):
        """Returns True if this payment represents income"""
        income_types = [PaymentType.car_rental_income, PaymentType.other_income]
        return self.payment_type in income_types
    
    @property
    def is_expense(self):
        """Returns True if this payment represents an expense"""
        return not self.is_income

class CarIncome(Base):
    __tablename__ = "car_incomes"
    
    id = Column(Integer, primary_key=True, index=True)
    rental_id = Column(Integer, ForeignKey("rentals.id"), nullable=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(Text, nullable=True)
    transaction_date = Column(Date, nullable=False)
    customer_name = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    rental = relationship("Rental", back_populates="income_records")
    car = relationship("Car", back_populates="income_records")
    created_by = relationship("User")

class CarExpense(Base):
    __tablename__ = "car_expenses"
    
    id = Column(Integer, primary_key=True, index=True)
    car_id = Column(Integer, ForeignKey("cars.id"), nullable=False)
    service_type = Column(String(50), nullable=False)  # maintenance, repair, fuel, insurance, etc.
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(Text, nullable=True)
    transaction_date = Column(Date, nullable=False)
    vendor = Column(String(200), nullable=False)
    mileage = Column(Integer, nullable=True)
    receipt_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by_id = Column(Integer, ForeignKey("users.id"))
    
    # Relationships
    car = relationship("Car", back_populates="expense_records")
    created_by = relationship("User")


# --- TASK ASSIGNMENT / CONVERSATION MODELS ---
class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    assigned_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    assignment_status = Column(Enum(TaskAssignmentStatus), default=TaskAssignmentStatus.pending_acceptance)
    assigned_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    response_at = Column(DateTime(timezone=True), nullable=True)

    assignment_message = Column(Text, nullable=True)
    response_message = Column(Text, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    call_requested = Column(Boolean, default=False)
    call_scheduled_at = Column(DateTime(timezone=True), nullable=True)
    call_completed_at = Column(DateTime(timezone=True), nullable=True)
    call_notes = Column(Text, nullable=True)

    task = relationship("Task", back_populates="assignments")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id], back_populates="task_assignments_given")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], back_populates="task_assignments_received")
    conversation = relationship("TaskConversation", back_populates="assignment", uselist=False)


class TaskConversation(Base):
    __tablename__ = "task_conversations"

    id = Column(Integer, primary_key=True, index=True)
    assignment_id = Column(Integer, ForeignKey("task_assignments.id"), nullable=False)

    status = Column(Enum(ConversationStatus), default=ConversationStatus.active)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    completed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    assignment = relationship("TaskAssignment", back_populates="conversation")
    messages = relationship("TaskMessage", back_populates="conversation", cascade="all, delete-orphan")
    completed_by = relationship("User")


class TaskMessage(Base):
    __tablename__ = "task_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("task_conversations.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    message_type = Column(Enum(MessageType), default=MessageType.text)
    content = Column(Text, nullable=False)

    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_at = Column(DateTime(timezone=True), nullable=True)
    is_system_message = Column(Boolean, default=False)

    conversation = relationship("TaskConversation", back_populates="messages")
    sender = relationship("User")


class TaskNotification(Base):
    __tablename__ = "task_notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    assignment_id = Column(Integer, ForeignKey("task_assignments.id"), nullable=True)

    notification_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    action_url = Column(String(255), nullable=True)

    is_read = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="task_notifications")
    task = relationship("Task")
    assignment = relationship("TaskAssignment")


# ==================== CHAT SYSTEM MODELS ====================

class ChatConversation(Base):
    """Direct messaging conversations between users"""
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True)
    participant1_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    participant2_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Last message info for quick display
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    last_message_preview = Column(String(200), nullable=True)
    
    participant1 = relationship("User", foreign_keys=[participant1_id])
    participant2 = relationship("User", foreign_keys=[participant2_id])
    messages = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ChatMessage.sent_at")


class ChatMessage(Base):
    """Individual messages in chat conversations"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(Integer, ForeignKey("chat_conversations.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    content = Column(Text, nullable=False)
    message_type = Column(String(20), default="text")  # text, system, approval_request
    
    sent_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_at = Column(DateTime(timezone=True), nullable=True)
    is_system_message = Column(Boolean, default=False)
    
    # For approval requests
    approval_request_id = Column(Integer, ForeignKey("approval_requests.id"), nullable=True)
    
    conversation = relationship("ChatConversation", back_populates="messages")
    sender = relationship("User")
    approval_request = relationship("ApprovalRequest", back_populates="message")


# ==================== APPROVAL SYSTEM MODELS ====================

class ApprovalRequestType(str, enum.Enum):
    """Types of approval requests"""
    GENERAL = "general"
    EXPENSE = "expense"
    TASK = "task"
    PROJECT = "project"
    LEAVE = "leave"
    PURCHASE = "purchase"


class ApprovalStatus(str, enum.Enum):
    """Status of approval requests"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DISCUSSION = "discussion"
    CANCELLED = "cancelled"


class ApprovalRequest(Base):
    """Approval requests that can be sent between users"""
    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    request_type = Column(Enum(ApprovalRequestType), default=ApprovalRequestType.GENERAL)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)
    
    # Additional data (JSON for flexibility)
    request_metadata = Column(JSON, nullable=True)  # Can store amounts, dates, etc.
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    responded_at = Column(DateTime(timezone=True), nullable=True)
    
    # Response details
    response_message = Column(Text, nullable=True)
    
    requester = relationship("User", foreign_keys=[requester_id])
    approver = relationship("User", foreign_keys=[approver_id])
    message = relationship("ChatMessage", back_populates="approval_request", uselist=False)
    notifications = relationship("ApprovalNotification", back_populates="approval_request", cascade="all, delete-orphan")


class ApprovalNotification(Base):
    """Notifications specifically for approval requests"""
    __tablename__ = "approval_notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    approval_request_id = Column(Integer, ForeignKey("approval_requests.id"), nullable=False)
    
    notification_type = Column(String(50), nullable=False)  # new_request, approved, rejected, discussion
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    user = relationship("User")
    approval_request = relationship("ApprovalRequest", back_populates="notifications")
