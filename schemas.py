from datetime import datetime, date
from pydantic import BaseModel, EmailStr, ConfigDict, computed_field, validator, Field
from typing import Optional, List
from enum import Enum
from models import GasTankLevel, TaskStatus

# --- User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    first_name: Optional[str] = None
    surname: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserResponse(UserBase):
    id: int
    is_active: bool
    role: str
    profile_picture_url: Optional[str] = None

    @computed_field
    @property
    def full_name(self) -> str:
        if self.first_name and self.surname:
            return f"{self.first_name} {self.surname}"
        return self.first_name or self.surname or self.email
    
    model_config = ConfigDict(from_attributes=True)

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    surname: Optional[str] = None
    birthday: Optional[date] = None

class UserRoleUpdate(BaseModel):
    role: str

class UserStatusUpdate(BaseModel):
    is_active: bool

# --- Basic Info Schemas (Used to break circular dependencies) ---
class UserBasicInfo(BaseModel):
    id: int
    full_name: str
    model_config = ConfigDict(from_attributes=True)


# --- Task History Schemas (Defined before they are used in TaskResponse) ---
class TaskHistoryBase(BaseModel):
    timestamp: datetime
    status_from: Optional[TaskStatus] = None
    status_to: Optional[TaskStatus] = None
    comment: Optional[str] = None

class TaskHistoryOut(TaskHistoryBase):
    id: int
    changed_by: UserBasicInfo
    model_config = ConfigDict(from_attributes=True)


# --- Token Schemas ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    id: Optional[int] = None
    email: Optional[EmailStr] = None


# --- Task Schemas ---
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    deadline_all_day: bool = False
    deadline: Optional[datetime] = None
    urgency: bool = False
    important: bool = False
    company_id: Optional[int] = None
    owner_id: Optional[int] = None
    department: Optional[str] = None

class TaskCreate(TaskBase):
    pass

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    deadline_all_day: Optional[bool] = None
    deadline: Optional[datetime] = None
    urgency: Optional[bool] = False
    important: Optional[bool] = False
    status: Optional[TaskStatus] = None
    company_id: Optional[int] = None
    department: Optional[str] = None
    comment: Optional[str] = None

class TaskStatusEnum(str, Enum):
    NEW = "new"
    RECEIVED = "received"
    ON_PROCESS = "on_process"
    PENDING = "pending"
    COMPLETED = "completed"
    LOOSE_END = "loose_end"

class TaskStatusUpdate(BaseModel):
    status: TaskStatusEnum
    status_comments: Optional[str] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    start_date: Optional[datetime]
    deadline: Optional[datetime]
    deadline_all_day: bool
    urgency: bool
    important: bool
    completed: bool

    # NEW: Status fields
    status: TaskStatusEnum
    status_comments: Optional[str]
    status_updated_at: Optional[datetime]
    status_updated_by: Optional[int]

    owner_id: int
    group_id: Optional[int]
    company_id: Optional[int]
    created_at: datetime
    updated_at: datetime

    # Include related objects
    owner: Optional["UserResponse"]
    status_updater: Optional["UserResponse"]

    class Config:
        from_attributes = True


# --- Group Schemas ---
class GroupCreate(BaseModel):
    name: str

class GroupOut(BaseModel):
    id: int
    name: str
    members: List[UserResponse] = []
    model_config = ConfigDict(from_attributes=True)

# --- THIS CLASS IS NOW RESTORED ---
class GroupTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_date: Optional[datetime] = None
    deadline_all_day: bool = False
    deadline: Optional[datetime] = None
    urgency: bool = False
    important: bool = False

# --- Other Schemas ---
class PasswordResetRequest(BaseModel):
    email: EmailStr

class PasswordReset(BaseModel):
    token: str
    new_password: str

class NotificationOut(BaseModel):
    id: int
    message: str
    link: Optional[str] = None
    is_read: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Contact Schemas ---
class ContactBase(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    notes: Optional[str] = None

    @validator('email', pre=True)
    def blank_string_to_none(cls, v):
        if v == "":
            return None
        return v

class ContactCreate(ContactBase):
    pass

class ContactUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    company: Optional[str] = None
    job_title: Optional[str] = None
    notes: Optional[str] = None

    @validator('email', pre=True)
    def blank_string_to_none(cls, v):
        if v == "":
            return None
        return v

class ContactOut(ContactBase):
    id: int
    owner_id: int
    model_config = ConfigDict(from_attributes=True)

class ContactIdList(BaseModel):
    contact_ids: List[int]

class ContactImport(BaseModel):
    contacts: List[ContactCreate]

# --- Daily Call Schemas ---
class DailyCallCreate(BaseModel):
    contact_id: int

class DailyCallUpdate(BaseModel):
    call_frequency_per_day: Optional[int] = None
    next_call_at: Optional[datetime] = None

class DailyCallOut(BaseModel):
    id: int
    user_id: int
    contact_id: int
    call_frequency_per_day: int
    next_call_at: Optional[datetime] = None
    contact: ContactOut 
    model_config = ConfigDict(from_attributes=True)

# --- Company Schemas ---
class CompanyBase(BaseModel):
    name: str
    vat_number: Optional[str] = None
    occupation: Optional[str] = None
    creation_date: Optional[date] = None
    description: Optional[str] = None

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    vat_number: Optional[str] = None
    occupation: Optional[str] = None
    creation_date: Optional[date] = None
    description: Optional[str] = None

class CompanyOut(CompanyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# --- Car & Rental Schemas ---
class CarBase(BaseModel):
    manufacturer: str
    model: str
    license_plate: str
    vin: str

class CarCreate(CarBase):
    pass

class CarUpdate(CarBase):
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    license_plate: Optional[str] = None
    vin: Optional[str] = None

class CarOut(CarBase):
    id: int
    company_id: int
    model_config = ConfigDict(from_attributes=True)
    
class RentalBase(BaseModel):
    customer_name: str
    customer_surname: str
    rental_days: int
    return_datetime: datetime
    start_kilometers: int
    gas_tank_start: GasTankLevel
    car_id: int

class RentalCreate(RentalBase):
    pass

class RentalUpdate(BaseModel):
    end_kilometers: int
    gas_tank_end: GasTankLevel

class RentalOut(RentalBase):
    id: int
    company_id: int
    end_kilometers: Optional[int] = None
    gas_tank_end: Optional[GasTankLevel] = None
    model_config = ConfigDict(from_attributes=True)
    
class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    location: str
    event_date: datetime

class EventCreate(EventBase):
    pass

class EventOut(EventBase):
    id: int
    created_by_id: int
    model_config = ConfigDict(from_attributes=True)

class CalendarEvent(BaseModel):
    title: str
    start: datetime | date
    end: datetime | date
    type: str
    allDay: bool
    user_id: Optional[int] = None
    task_id: Optional[int] = None
    group_id: Optional[int] = None
    details: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)