from sqlalchemy.orm import Session
from datetime import date, datetime, time
from typing import Optional, List
from . import models
from . import schemas
from . import auth

# --- USER & EMPLOYEE CRUD ---

def get_employee(db: Session, employee_id: int) -> Optional[models.Employee]:
    return db.query(models.Employee).filter(models.Employee.id == employee_id).first()

def get_employee_by_email(db: Session, email: str) -> Optional[models.Employee]:
    return db.query(models.Employee).filter(models.Employee.email == email).first()

def get_employee_by_user_id(db: Session, user_id: int) -> Optional[models.Employee]:
    return db.query(models.Employee).filter(models.Employee.user_id == user_id).first()

def get_employees(db: Session, skip: int = 0, limit: int = 100) -> List[models.Employee]:
    return db.query(models.Employee).offset(skip).limit(limit).all()

def create_employee(db: Session, emp: schemas.EmployeeCreate) -> models.Employee:
    # 1. Create the user credentials first
    hashed_pwd = auth.get_password_hash(emp.password)
    db_user = models.User(
        username=emp.username,
        password_hash=hashed_pwd,
        role="employee"
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # 2. Create the Employee profile
    db_employee = models.Employee(
        user_id=db_user.id,
        first_name=emp.first_name,
        last_name=emp.last_name,
        email=emp.email,
        phone=emp.phone,
        department=emp.department,
        designation=emp.designation,
        join_date=emp.join_date,
        base_salary=emp.base_salary,
        bank_account=emp.bank_account
    )
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)

    # 3. Initialize default Leave Balances (12 Sick, 12 Casual, 15 Paid leaves)
    default_leaves = [
        {"type": "Sick", "allocated": 12},
        {"type": "Casual", "allocated": 12},
        {"type": "Paid", "allocated": 15}
    ]
    for leave in default_leaves:
        db_balance = models.LeaveBalance(
            employee_id=db_employee.id,
            leave_type=leave["type"],
            allocated=leave["allocated"],
            used=0
        )
        db.add(db_balance)
    
    db.commit()
    db.refresh(db_employee)
    return db_employee

def update_employee(db: Session, employee_id: int, emp_update: schemas.EmployeeUpdate) -> Optional[models.Employee]:
    db_employee = get_employee(db, employee_id)
    if not db_employee:
        return None
    
    update_data = emp_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_employee, key, value)
        
    db.commit()
    db.refresh(db_employee)
    return db_employee

def delete_employee(db: Session, employee_id: int) -> bool:
    db_employee = get_employee(db, employee_id)
    if not db_employee:
        return False
    
    # Get associated User object to delete it as well
    db_user = db.query(models.User).filter(models.User.id == db_employee.user_id).first()
    
    db.delete(db_employee)
    if db_user:
        db.delete(db_user)
        
    db.commit()
    return True


# --- ATTENDANCE CRUD ---

def get_attendance_by_date(db: Session, employee_id: int, attendance_date: date) -> Optional[models.Attendance]:
    return db.query(models.Attendance).filter(
        models.Attendance.employee_id == employee_id,
        models.Attendance.date == attendance_date
    ).first()

def get_attendance_history(db: Session, employee_id: int, start: Optional[date] = None, end: Optional[date] = None) -> List[models.Attendance]:
    query = db.query(models.Attendance).filter(models.Attendance.employee_id == employee_id)
    if start:
        query = query.filter(models.Attendance.date >= start)
    if end:
        query = query.filter(models.Attendance.date <= end)
    return query.order_by(models.Attendance.date.desc()).all()

def get_attendance_today(db: Session) -> List[models.Attendance]:
    return db.query(models.Attendance).filter(models.Attendance.date == date.today()).all()

def clock_in(db: Session, employee_id: int, clock_in_time: Optional[time] = None, attendance_date: Optional[date] = None) -> models.Attendance:
    att_date = attendance_date or date.today()
    c_in = clock_in_time or datetime.now().time()
    
    # Check if entry already exists
    existing = get_attendance_by_date(db, employee_id, att_date)
    if existing:
        return existing
        
    # Standard check-in hour is 09:00:00. Late after 09:15:00.
    # Status calculation
    status = "Present"
    late_threshold = time(9, 15, 0)
    if c_in > late_threshold:
        status = "Late"
        
    db_attendance = models.Attendance(
        employee_id=employee_id,
        date=att_date,
        clock_in=c_in,
        status=status
    )
    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)
    return db_attendance

def clock_out(db: Session, employee_id: int, clock_out_time: Optional[time] = None, attendance_date: Optional[date] = None) -> Optional[models.Attendance]:
    att_date = attendance_date or date.today()
    c_out = clock_out_time or datetime.now().time()
    
    db_attendance = get_attendance_by_date(db, employee_id, att_date)
    if not db_attendance:
        return None
        
    db_attendance.clock_out = c_out
    
    # Calculate hours worked (simple check: if total hours < 4, mark Half-day)
    # Re-verify status based on work hours if clock_in and clock_out are populated
    try:
        t1 = datetime.combine(date.today(), db_attendance.clock_in)
        t2 = datetime.combine(date.today(), c_out)
        diff_hours = (t2 - t1).total_seconds() / 3600.0
        
        # If total duration of work is less than 4 hours, status changes to Half-day
        if diff_hours < 4.0:
            db_attendance.status = "Half-day"
    except Exception:
        pass
        
    db.commit()
    db.refresh(db_attendance)
    return db_attendance


# --- LEAVE MANAGEMENT CRUD ---

def get_leave_balances(db: Session, employee_id: int) -> List[models.LeaveBalance]:
    return db.query(models.LeaveBalance).filter(models.LeaveBalance.employee_id == employee_id).all()

def get_leave_balance_by_type(db: Session, employee_id: int, leave_type: str) -> Optional[models.LeaveBalance]:
    return db.query(models.LeaveBalance).filter(
        models.LeaveBalance.employee_id == employee_id,
        models.LeaveBalance.leave_type == leave_type
    ).first()

def get_leave_requests(db: Session, status: Optional[str] = None) -> List[models.LeaveRequest]:
    query = db.query(models.LeaveRequest)
    if status:
        query = query.filter(models.LeaveRequest.status == status)
    return query.order_by(models.LeaveRequest.start_date.desc()).all()

def get_employee_leave_requests(db: Session, employee_id: int) -> List[models.LeaveRequest]:
    return db.query(models.LeaveRequest).filter(
        models.LeaveRequest.employee_id == employee_id
    ).order_by(models.LeaveRequest.start_date.desc()).all()

def create_leave_request(db: Session, employee_id: int, req: schemas.LeaveRequestCreate) -> Optional[models.LeaveRequest]:
    # Check if balance is available
    balance = get_leave_balance_by_type(db, employee_id, req.leave_type)
    if not balance:
        return None
        
    requested_days = (req.end_date - req.start_date).days + 1
    if requested_days <= 0:
        return None
        
    available = balance.allocated - balance.used
    if requested_days > available:
        # User requested more than their available limit
        return None
        
    db_request = models.LeaveRequest(
        employee_id=employee_id,
        leave_type=req.leave_type,
        start_date=req.start_date,
        end_date=req.end_date,
        reason=req.reason,
        status="Pending"
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request

def update_leave_request_status(db: Session, leave_id: int, status: str, admin_user_id: int) -> Optional[models.LeaveRequest]:
    db_request = db.query(models.LeaveRequest).filter(models.LeaveRequest.id == leave_id).first()
    if not db_request:
        return None
        
    # If request is already processed and status is unchanged, return it
    if db_request.status == status:
        return db_request
        
    old_status = db_request.status
    db_request.status = status
    db_request.approved_by = admin_user_id
    
    # Adjust leave balance if changing status to "Approved"
    if status == "Approved" and old_status != "Approved":
        balance = get_leave_balance_by_type(db, db_request.employee_id, db_request.leave_type)
        if balance:
            requested_days = (db_request.end_date - db_request.start_date).days + 1
            balance.used += requested_days
            
    # Adjust leave balance back if changing status from "Approved" to something else (e.g. Admin corrections)
    elif old_status == "Approved" and status != "Approved":
        balance = get_leave_balance_by_type(db, db_request.employee_id, db_request.leave_type)
        if balance:
            requested_days = (db_request.end_date - db_request.start_date).days + 1
            balance.used = max(0, balance.used - requested_days)
            
    db.commit()
    db.refresh(db_request)
    return db_request


# --- PAYROLL CRUD ---

def get_payroll_records(db: Session, month: Optional[str] = None) -> List[models.PayrollRecord]:
    query = db.query(models.PayrollRecord)
    if month:
        query = query.filter(models.PayrollRecord.month == month)
    return query.all()

def get_employee_payroll_records(db: Session, employee_id: int) -> List[models.PayrollRecord]:
    return db.query(models.PayrollRecord).filter(
        models.PayrollRecord.employee_id == employee_id
    ).order_by(models.PayrollRecord.month.desc()).all()

def get_payroll_record(db: Session, record_id: int) -> Optional[models.PayrollRecord]:
    return db.query(models.PayrollRecord).filter(models.PayrollRecord.id == record_id).first()

def get_payroll_by_employee_and_month(db: Session, employee_id: int, month: str) -> Optional[models.PayrollRecord]:
    return db.query(models.PayrollRecord).filter(
        models.PayrollRecord.employee_id == employee_id,
        models.PayrollRecord.month == month
    ).first()

def delete_payroll_by_id(db: Session, record_id: int) -> bool:
    rec = get_payroll_record(db, record_id)
    if not rec:
        return False
    db.delete(rec)
    db.commit()
    return True
