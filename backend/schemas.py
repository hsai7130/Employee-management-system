from pydantic import BaseModel, EmailStr, Field
from datetime import date, time, datetime
from typing import Optional, List

# --- AUTH SCHEMAS ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "employee"  # "admin" or "employee"

class UserResponse(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True

# --- EMPLOYEE SCHEMAS ---
class EmployeeBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    join_date: date
    base_salary: float = Field(ge=0.0)
    bank_account: Optional[str] = None

class EmployeeCreate(EmployeeBase):
    username: str
    password: str

class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    designation: Optional[str] = None
    base_salary: Optional[float] = Field(None, ge=0.0)
    bank_account: Optional[str] = None

class EmployeeResponse(EmployeeBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True

class EmployeeDetailResponse(EmployeeResponse):
    user: UserResponse

    class Config:
        from_attributes = True

# --- ATTENDANCE SCHEMAS ---
class AttendanceBase(BaseModel):
    date: date
    clock_in: time
    clock_out: Optional[time] = None
    status: str  # "Present", "Absent", "Late", "Half-day"

class AttendanceCreate(AttendanceBase):
    employee_id: int

class AttendanceResponse(AttendanceBase):
    id: int
    employee_id: int

    class Config:
        from_attributes = True

class ClockInRequest(BaseModel):
    date: Optional[date] = None
    clock_in: Optional[time] = None

class ClockOutRequest(BaseModel):
    clock_out: Optional[time] = None

# --- LEAVE SCHEMAS ---
class LeaveRequestBase(BaseModel):
    leave_type: str  # "Sick", "Casual", "Paid"
    start_date: date
    end_date: date
    reason: Optional[str] = None

class LeaveRequestCreate(LeaveRequestBase):
    pass

class LeaveRequestApproval(BaseModel):
    status: str  # "Approved", "Rejected"

class LeaveRequestResponse(LeaveRequestBase):
    id: int
    employee_id: int
    status: str
    approved_by: Optional[int] = None
    employee: Optional[EmployeeResponse] = None

    class Config:
        from_attributes = True

class LeaveBalanceResponse(BaseModel):
    id: int
    employee_id: int
    leave_type: str
    allocated: int
    used: int

    class Config:
        from_attributes = True

# --- PAYROLL SCHEMAS ---
class PayrollRecordBase(BaseModel):
    month: str  # YYYY-MM
    working_days: int
    present_days: int
    absent_days: int
    base_salary: float
    allowances: float
    deductions: float
    net_salary: float
    status: str  # "Draft", "Paid"

class PayrollProcessRequest(BaseModel):
    month: str  # YYYY-MM
    working_days: int

class PayrollRecordResponse(PayrollRecordBase):
    id: int
    employee_id: int
    employee: Optional[EmployeeResponse] = None

    class Config:
        from_attributes = True

# --- DASHBOARD & ANALYTICS ---
class AdminDashboardStats(BaseModel):
    total_employees: int
    active_leaves_pending: int
    monthly_payout: float
    attendance_today_count: int
