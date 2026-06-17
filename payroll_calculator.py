from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
import calendar
import models
import crud

def calculate_monthly_days(month_str: str):
    """
    Given 'YYYY-MM', returns (start_date, end_date, total_days_in_month)
    """
    year, month = map(int, month_str.split("-"))
    start_date = date(year, month, 1)
    _, total_days = calendar.monthrange(year, month)
    end_date = date(year, month, total_days)
    return start_date, end_date, total_days

def calculate_employee_payroll(db: Session, employee_id: int, month: str, working_days: int):
    """
    Queries attendance and leaves, calculates HRA, TA, PF, PT, and unpaid leave deductions.
    Returns a dict with calculations.
    """
    employee = crud.get_employee(db, employee_id)
    if not employee:
        raise ValueError("Employee not found")
        
    start_date, end_date, total_days = calculate_monthly_days(month)
    
    # 1. Calculate Present Days from Attendance
    attendance_records = db.query(models.Attendance).filter(
        models.Attendance.employee_id == employee_id,
        models.Attendance.date >= start_date,
        models.Attendance.date <= end_date
    ).all()
    
    present_days = 0.0
    for record in attendance_records:
        if record.status in ["Present", "Late"]:
            present_days += 1.0
        elif record.status == "Half-day":
            present_days += 0.5
            
    # 2. Calculate Approved Leave Days intersecting this month
    leave_requests = db.query(models.LeaveRequest).filter(
        models.LeaveRequest.employee_id == employee_id,
        models.LeaveRequest.status == "Approved",
        models.LeaveRequest.start_date <= end_date,
        models.LeaveRequest.end_date >= start_date
    ).all()
    
    approved_leave_days = 0.0
    for req in leave_requests:
        overlap_start = max(req.start_date, start_date)
        overlap_end = min(req.end_date, end_date)
        if overlap_start <= overlap_end:
            overlap_days = (overlap_end - overlap_start).days + 1
            approved_leave_days += overlap_days
            
    # Total paid days cannot exceed the total working days in the month
    paid_days = present_days + approved_leave_days
    paid_days = min(float(working_days), paid_days)
    
    # Absent (unpaid) days
    absent_days = max(0.0, float(working_days) - paid_days)
    
    # Salary calculations
    base_salary = employee.base_salary
    
    # Allowances: Housing (HRA) 10%, Transport (TA) 5%
    hra = base_salary * 0.10
    ta = base_salary * 0.05
    total_allowances = hra + ta
    
    # Deductions:
    # 1. Provident Fund (PF) 12% of base salary
    pf = base_salary * 0.12
    # 2. Professional Tax (PT) - flat $200 (capped if base salary is low)
    pt = 200.0 if base_salary >= 2000.0 else (base_salary * 0.05)
    # 3. Unpaid leave deduction
    unpaid_leave_deduction = 0.0
    if absent_days > 0 and working_days > 0:
        unpaid_leave_deduction = (base_salary / working_days) * absent_days
        
    total_deductions = pf + pt + unpaid_leave_deduction
    
    # Net Salary
    net_salary = (base_salary + total_allowances) - total_deductions
    net_salary = max(0.0, round(net_salary, 2))
    
    return {
        "employee_id": employee_id,
        "month": month,
        "working_days": working_days,
        "present_days": int(present_days),
        "absent_days": int(absent_days),
        "base_salary": round(base_salary, 2),
        "allowances": round(total_allowances, 2),
        "deductions": round(total_deductions, 2),
        "net_salary": net_salary
    }
