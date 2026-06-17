from fastapi import FastAPI, Depends, HTTPException, status, Response, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from datetime import date, time, datetime
from typing import List, Optional
import os

import models
import schemas
import crud
import auth
import payroll_calculator
import payslip_generator
from database import engine, SessionLocal, get_db

app = FastAPI(title="Employee Management System API", version="1.0.0")

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup DB initialization & default admin seeding
@app.on_event("startup")
def startup_event():
    models.Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if any admin exists
        admin_user = db.query(models.User).filter(models.User.role == "admin").first()
        if not admin_user:
            hashed_pwd = auth.get_password_hash("admin123")
            admin_user = models.User(
                username="admin",
                password_hash=hashed_pwd,
                role="admin"
            )
            db.add(admin_user)
            db.commit()
            print("Default admin created: username='admin', password='admin123'")
    except Exception as e:
        print(f"Error on startup database seeding: {e}")
    finally:
        db.close()


# --- AUTH ENDPOINTS ---

@app.post("/api/auth/login", response_model=schemas.Token)
def login(form_data: schemas.UserLogin, db: Session = Depends(get_db)):
    user = auth.get_user_by_username(db, form_data.username)
    if not user or not auth.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# --- ADMIN DASHBOARD STATS ---

@app.get("/api/admin/stats", response_model=schemas.AdminDashboardStats)
def get_admin_stats(db: Session = Depends(get_db), current_admin: models.User = Depends(auth.get_current_admin)):
    total_employees = db.query(models.Employee).count()
    active_leaves = db.query(models.LeaveRequest).filter(models.LeaveRequest.status == "Pending").count()
    
    current_month = datetime.now().strftime("%Y-%m")
    payrolls = db.query(models.PayrollRecord).filter(models.PayrollRecord.month == current_month).all()
    monthly_payout = sum(p.net_salary for p in payrolls)
    
    attendance_today = db.query(models.Attendance).filter(
        models.Attendance.date == date.today(),
        models.Attendance.status.in_(["Present", "Late", "Half-day"])
    ).count()
    
    return {
        "total_employees": total_employees,
        "active_leaves_pending": active_leaves,
        "monthly_payout": monthly_payout,
        "attendance_today_count": attendance_today
    }


# --- EMPLOYEE ENDPOINTS ---

@app.get("/api/employees", response_model=List[schemas.EmployeeResponse])
def read_employees(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    return crud.get_employees(db, skip=skip, limit=limit)

@app.post("/api/employees", response_model=schemas.EmployeeResponse, status_code=status.HTTP_201_CREATED)
def register_employee(
    emp: schemas.EmployeeCreate, 
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    # Check if username or email already exists
    existing_user = auth.get_user_by_username(db, emp.username)
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already registered")
        
    existing_emp = crud.get_employee_by_email(db, emp.email)
    if existing_emp:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    return crud.create_employee(db=db, emp=emp)

@app.get("/api/employees/me", response_model=schemas.EmployeeResponse)
def read_my_employee_profile(
    current_employee: models.Employee = Depends(auth.get_current_employee)
):
    return current_employee

@app.get("/api/employees/{employee_id}", response_model=schemas.EmployeeResponse)
def read_employee_by_id(
    employee_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Employees can only view their own profile, admin can view all
    if current_user.role != "admin":
        emp = crud.get_employee_by_user_id(db, current_user.id)
        if not emp or emp.id != employee_id:
            raise HTTPException(status_code=403, detail="Not authorized to view this profile")
            
    db_employee = crud.get_employee(db, employee_id)
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return db_employee

@app.put("/api/employees/{employee_id}", response_model=schemas.EmployeeResponse)
def update_employee_profile(
    employee_id: int,
    emp_update: schemas.EmployeeUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Employees can edit basic info of their own profile; admins can edit everything.
    if current_user.role != "admin":
        emp = crud.get_employee_by_user_id(db, current_user.id)
        if not emp or emp.id != employee_id:
            raise HTTPException(status_code=403, detail="Not authorized to edit this profile")
        
        # Prevent non-admin from updating salary
        if emp_update.base_salary is not None:
            emp_update.base_salary = None
            
    db_employee = crud.update_employee(db, employee_id, emp_update)
    if not db_employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return db_employee

@app.delete("/api/employees/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    success = crud.delete_employee(db, employee_id)
    if not success:
        raise HTTPException(status_code=404, detail="Employee not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- ATTENDANCE ENDPOINTS ---

@app.post("/api/attendance/clock-in", response_model=schemas.AttendanceResponse)
def do_clock_in(
    req: Optional[schemas.ClockInRequest] = None,
    db: Session = Depends(get_db),
    current_employee: models.Employee = Depends(auth.get_current_employee)
):
    att_date = req.date if (req and req.date) else date.today()
    c_in = req.clock_in if (req and req.clock_in) else datetime.now().time()
    
    # Check if already clocked in
    existing = crud.get_attendance_by_date(db, current_employee.id, att_date)
    if existing:
        raise HTTPException(status_code=400, detail="Already clocked in for this day")
        
    return crud.clock_in(db, current_employee.id, clock_in_time=c_in, attendance_date=att_date)

@app.post("/api/attendance/clock-out", response_model=schemas.AttendanceResponse)
def do_clock_out(
    req: Optional[schemas.ClockOutRequest] = None,
    db: Session = Depends(get_db),
    current_employee: models.Employee = Depends(auth.get_current_employee)
):
    c_out = req.clock_out if (req and req.clock_out) else datetime.now().time()
    att_date = date.today()
    
    # Check if clocked in
    existing = crud.get_attendance_by_date(db, current_employee.id, att_date)
    if not existing:
        raise HTTPException(status_code=400, detail="Cannot clock out without clocking in first today")
    if existing.clock_out:
        raise HTTPException(status_code=400, detail="Already clocked out for today")
        
    return crud.clock_out(db, current_employee.id, clock_out_time=c_out, attendance_date=att_date)

@app.get("/api/attendance/history", response_model=List[schemas.AttendanceResponse])
def get_history(
    employee_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if current_user.role == "admin":
        if not employee_id:
            raise HTTPException(status_code=400, detail="employee_id query parameter is required for Admin")
        target_emp_id = employee_id
    else:
        emp = crud.get_employee_by_user_id(db, current_user.id)
        if not emp:
            raise HTTPException(status_code=404, detail="Employee profile not found")
        target_emp_id = emp.id
        
    return crud.get_attendance_history(db, target_emp_id, start_date, end_date)

@app.get("/api/attendance/today", response_model=List[schemas.AttendanceResponse])
def get_today_clocks(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if current_user.role == "admin":
        return crud.get_attendance_today(db)
    else:
        emp = crud.get_employee_by_user_id(db, current_user.id)
        if not emp:
            return []
        att = crud.get_attendance_by_date(db, emp.id, date.today())
        return [att] if att else []

@app.post("/api/attendance/manual", response_model=schemas.AttendanceResponse)
def mark_attendance_manually(
    att: schemas.AttendanceCreate,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    # Check if attendance already exists
    existing = crud.get_attendance_by_date(db, att.employee_id, att.date)
    if existing:
        # Update it
        existing.clock_in = att.clock_in
        existing.clock_out = att.clock_out
        existing.status = att.status
        db.commit()
        db.refresh(existing)
        return existing
        
    db_attendance = models.Attendance(
        employee_id=att.employee_id,
        date=att.date,
        clock_in=att.clock_in,
        clock_out=att.clock_out,
        status=att.status
    )
    db.add(db_attendance)
    db.commit()
    db.refresh(db_attendance)
    return db_attendance


# --- LEAVE MANAGEMENT ENDPOINTS ---

@app.post("/api/leaves/request", response_model=schemas.LeaveRequestResponse)
def apply_leave(
    req: schemas.LeaveRequestCreate,
    db: Session = Depends(get_db),
    current_employee: models.Employee = Depends(auth.get_current_employee)
):
    # Validate date range
    if req.end_date < req.start_date:
        raise HTTPException(status_code=400, detail="End date cannot be earlier than start date")
        
    db_req = crud.create_leave_request(db, current_employee.id, req)
    if not db_req:
        raise HTTPException(status_code=400, detail="Insufficient leave balance or invalid dates")
    return db_req

@app.get("/api/leaves/requests", response_model=List[schemas.LeaveRequestResponse])
def list_leaves(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if current_user.role == "admin":
        return crud.get_leave_requests(db, status=status_filter)
    else:
        emp = crud.get_employee_by_user_id(db, current_user.id)
        if not emp:
            return []
        requests = crud.get_employee_leave_requests(db, emp.id)
        if status_filter:
            requests = [r for r in requests if r.status == status_filter]
        return requests

@app.put("/api/leaves/requests/{leave_id}/approve", response_model=schemas.LeaveRequestResponse)
def approve_leave_request(
    leave_id: int,
    approval: schemas.LeaveRequestApproval,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    if approval.status not in ["Approved", "Rejected"]:
        raise HTTPException(status_code=400, detail="Status must be Approved or Rejected")
        
    db_req = crud.update_leave_request_status(db, leave_id, approval.status, current_admin.id)
    if not db_req:
        raise HTTPException(status_code=404, detail="Leave request not found")
    return db_req

@app.get("/api/leaves/balances", response_model=List[schemas.LeaveBalanceResponse])
def get_balances(
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if current_user.role == "admin":
        if not employee_id:
            raise HTTPException(status_code=400, detail="employee_id query parameter is required for Admin")
        target_id = employee_id
    else:
        emp = crud.get_employee_by_user_id(db, current_user.id)
        if not emp:
            raise HTTPException(status_code=404, detail="Employee profile not found")
        target_id = emp.id
        
    return crud.get_leave_balances(db, target_id)


# --- PAYROLL ENDPOINTS ---

@app.post("/api/payroll/process", response_model=List[schemas.PayrollRecordResponse])
def process_payroll_for_month(
    req: schemas.PayrollProcessRequest,
    employee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    # Fetch employees to process
    if employee_id:
        employees = [crud.get_employee(db, employee_id)]
        if not employees[0]:
            raise HTTPException(status_code=404, detail="Employee not found")
    else:
        employees = crud.get_employees(db)
        
    records = []
    for emp in employees:
        # Check if record already exists for the month
        existing = crud.get_payroll_by_employee_and_month(db, emp.id, req.month)
        if existing:
            # Overwrite/Delete it and re-calculate
            crud.delete_payroll_by_id(db, existing.id)
            
        # Compute payroll details
        try:
            calcs = payroll_calculator.calculate_employee_payroll(
                db=db,
                employee_id=emp.id,
                month=req.month,
                working_days=req.working_days
            )
            
            db_record = models.PayrollRecord(
                employee_id=emp.id,
                month=req.month,
                working_days=calcs["working_days"],
                present_days=calcs["present_days"],
                absent_days=calcs["absent_days"],
                base_salary=calcs["base_salary"],
                allowances=calcs["allowances"],
                deductions=calcs["deductions"],
                net_salary=calcs["net_salary"],
                status="Draft"
            )
            db.add(db_record)
            records.append(db_record)
        except Exception as e:
            # Continue with other employees if one fails
            print(f"Failed to calculate payroll for Employee ID {emp.id}: {e}")
            
    db.commit()
    # Refresh records
    for r in records:
        db.refresh(r)
    return records

@app.get("/api/payroll/records", response_model=List[schemas.PayrollRecordResponse])
def list_payroll_records(
    month: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    if current_user.role == "admin":
        return crud.get_payroll_records(db, month=month)
    else:
        emp = crud.get_employee_by_user_id(db, current_user.id)
        if not emp:
            return []
        records = crud.get_employee_payroll_records(db, emp.id)
        if month:
            records = [r for r in records if r.month == month]
        return records

@app.get("/api/payroll/records/{record_id}", response_model=schemas.PayrollRecordResponse)
def get_payroll_record_by_id(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    record = crud.get_payroll_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")
        
    if current_user.role != "admin":
        emp = crud.get_employee_by_user_id(db, current_user.id)
        if not emp or record.employee_id != emp.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this payroll record")
            
    return record

@app.delete("/api/payroll/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payroll_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    success = crud.delete_payroll_by_id(db, record_id)
    if not success:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@app.put("/api/payroll/records/{record_id}/pay", response_model=schemas.PayrollRecordResponse)
def mark_payroll_as_paid(
    record_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(auth.get_current_admin)
):
    record = crud.get_payroll_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    record.status = "Paid"
    db.commit()
    db.refresh(record)
    return record

@app.get("/api/payroll/records/{record_id}/payslip")
def download_payslip_pdf(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    record = crud.get_payroll_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Payroll record not found")
        
    if current_user.role != "admin":
        emp = crud.get_employee_by_user_id(db, current_user.id)
        if not emp or record.employee_id != emp.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this payslip")
            
    # Generate the PDF byte stream
    try:
        pdf_stream = payslip_generator.generate_payslip_pdf(record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not generate payslip: {e}")
        
    filename = f"payslip_{record.employee.first_name}_{record.employee.last_name}_{record.month}.pdf"
    
    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# --- FRONTEND STATIC FILES MOUNT ---
# StaticFiles is mounted at '/' using html=True, serving the front-end SPA dashboard.
# We check if static directory exists first.
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
