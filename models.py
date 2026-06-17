from sqlalchemy import Column, Integer, String, Float, Date, Time, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="employee", nullable=False)  # "admin" or "employee"

    # Relationships
    employee_profile = relationship("Employee", back_populates="user", uselist=False)

class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone = Column(String, nullable=True)
    department = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    join_date = Column(Date, nullable=False)
    base_salary = Column(Float, nullable=False, default=0.0)
    bank_account = Column(String, nullable=True)

    # Relationships
    user = relationship("User", back_populates="employee_profile")
    attendance_records = relationship("Attendance", back_populates="employee", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="employee", cascade="all, delete-orphan")
    leave_balances = relationship("LeaveBalance", back_populates="employee", cascade="all, delete-orphan")
    payroll_records = relationship("PayrollRecord", back_populates="employee", cascade="all, delete-orphan")

class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(Date, nullable=False)
    clock_in = Column(Time, nullable=False)
    clock_out = Column(Time, nullable=True)
    status = Column(String, nullable=False)  # "Present", "Absent", "Late", "Half-day"

    # Relationship
    employee = relationship("Employee", back_populates="attendance_records")

    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uix_employee_date"),
    )

class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    leave_type = Column(String, nullable=False)  # "Sick", "Casual", "Paid"
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String, nullable=True)
    status = Column(String, default="Pending", nullable=False)  # "Pending", "Approved", "Rejected"
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    employee = relationship("Employee", back_populates="leave_requests")
    approver = relationship("User")

class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    leave_type = Column(String, nullable=False)  # "Sick", "Casual", "Paid"
    allocated = Column(Integer, default=0, nullable=False)
    used = Column(Integer, default=0, nullable=False)

    # Relationship
    employee = relationship("Employee", back_populates="leave_balances")

    __table_args__ = (
        UniqueConstraint("employee_id", "leave_type", name="uix_employee_leave_type"),
    )

class PayrollRecord(Base):
    __tablename__ = "payroll_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    month = Column(String, nullable=False)  # YYYY-MM
    working_days = Column(Integer, nullable=False)
    present_days = Column(Integer, nullable=False)
    absent_days = Column(Integer, nullable=False)
    base_salary = Column(Float, nullable=False)
    allowances = Column(Float, nullable=False, default=0.0)
    deductions = Column(Float, nullable=False, default=0.0)
    net_salary = Column(Float, nullable=False)
    status = Column(String, default="Draft", nullable=False)  # "Draft", "Paid"

    # Relationship
    employee = relationship("Employee", back_populates="payroll_records")

    __table_args__ = (
        UniqueConstraint("employee_id", "month", name="uix_employee_month"),
    )
