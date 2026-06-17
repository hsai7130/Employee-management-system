import sys
import os
from datetime import date, time, datetime

# Add the current directory to sys.path so we can import modules correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from database import Base, engine, SessionLocal
    import models
    import schemas
    import crud
    import auth
    import payroll_calculator
    import payslip_generator
    print("SUCCESS: All system files imported successfully without syntax/import errors!")
except Exception as e:
    print(f"FAILED: Import error: {e}")
    sys.exit(1)

def run_verification():
    # 1. Initialize clean database
    print("\n--- Step 1: Initializing Database Schema ---")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("SUCCESS: Database schema generated.")

    db = SessionLocal()
    try:
        # 2. Seed Default Admin User
        print("\n--- Step 2: Seeding Admin Account ---")
        admin_pwd = auth.get_password_hash("admin123")
        admin_user = models.User(
            username="admin",
            password_hash=admin_pwd,
            role="admin"
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        print(f"SUCCESS: Admin account created with ID: {admin_user.id}")

        # 3. Create a Test Employee
        print("\n--- Step 3: Enrolling Test Employee ---")
        emp_data = schemas.EmployeeCreate(
            username="johndoe",
            password="password123",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="+15551234567",
            department="Engineering",
            designation="Senior Developer",
            join_date=date(2026, 1, 1),
            base_salary=5000.0,
            bank_account="US-BOA-9876543210"
        )
        db_emp = crud.create_employee(db, emp_data)
        print(f"SUCCESS: Created Employee ID: {db_emp.id} (user_id: {db_emp.user_id})")

        # 4. Initialize and Verify Default Leave Balances
        print("\n--- Step 4: Verifying Leave Balances ---")
        balances = crud.get_leave_balances(db, db_emp.id)
        for b in balances:
            print(f"  - {b.leave_type} Leave: Allocated = {b.allocated}, Used = {b.used}")
        assert len(balances) == 3, "Employee should have 3 leave types initialized"
        print("SUCCESS: Default balances initialized correctly.")

        # 5. Log Attendance Clocks
        print("\n--- Step 5: Clocking Attendance Logs ---")
        # Clock in on time (09:00:00) on June 1st
        date1 = date(2026, 6, 1)
        time_in1 = time(9, 0, 0)
        time_out1 = time(17, 0, 0)
        att1 = crud.clock_in(db, db_emp.id, clock_in_time=time_in1, attendance_date=date1)
        att1 = crud.clock_out(db, db_emp.id, clock_out_time=time_out1, attendance_date=date1)
        print(f"  - Clocked Day 1: In {att1.clock_in}, Out {att1.clock_out}. Status: {att1.status}")
        assert att1.status == "Present"

        # Clock in late (09:45:00) on June 2nd
        date2 = date(2026, 6, 2)
        time_in2 = time(9, 45, 0)
        time_out2 = time(17, 0, 0)
        att2 = crud.clock_in(db, db_emp.id, clock_in_time=time_in2, attendance_date=date2)
        att2 = crud.clock_out(db, db_emp.id, clock_out_time=time_out2, attendance_date=date2)
        print(f"  - Clocked Day 2: In {att2.clock_in}, Out {att2.clock_out}. Status: {att2.status}")
        assert att2.status == "Late"

        # Clock in on time but clock out very early (11:00:00) on June 3rd (under 4 hours = Half-day)
        date3 = date(2026, 6, 3)
        time_in3 = time(9, 0, 0)
        time_out3 = time(11, 0, 0)
        att3 = crud.clock_in(db, db_emp.id, clock_in_time=time_in3, attendance_date=date3)
        att3 = crud.clock_out(db, db_emp.id, clock_out_time=time_out3, attendance_date=date3)
        print(f"  - Clocked Day 3: In {att3.clock_in}, Out {att3.clock_out}. Status: {att3.status}")
        assert att3.status == "Half-day"
        print("SUCCESS: Attendance check logs verified.")

        # 6. Apply and Approve Leaves
        print("\n--- Step 6: Requesting and Approving Leaves ---")
        # Apply for 3 days of Paid leave
        leave_req = schemas.LeaveRequestCreate(
            leave_type="Paid",
            start_date=date(2026, 6, 8),
            end_date=date(2026, 6, 10),
            reason="Family vacation"
        )
        db_leave = crud.create_leave_request(db, db_emp.id, leave_req)
        print(f"  - Leave requested: {db_leave.leave_type} from {db_leave.start_date} to {db_leave.end_date}. Status: {db_leave.status}")
        
        # Approve the leave as Admin
        db_leave = crud.update_leave_request_status(db, db_leave.id, "Approved", admin_user.id)
        print(f"  - Leave status updated to: {db_leave.status} by Admin ID {db_leave.approved_by}")
        assert db_leave.status == "Approved"
        
        # Verify leave balance was reduced
        balance = crud.get_leave_balance_by_type(db, db_emp.id, "Paid")
        print(f"  - Leave balance updated: Allocated = {balance.allocated}, Used = {balance.used}")
        assert balance.used == 3, "Leave balance used should be updated to 3"
        print("SUCCESS: Leave requests processed and balance adjusted.")

        # 7. Calculate Payroll Record
        print("\n--- Step 7: Calculating Payroll for June 2026 ---")
        # Standard: 22 working days in June
        # Employee was: Present on Day 1 (1.0), Late on Day 2 (1.0), Half-day on Day 3 (0.5). Total Present = 2.5 days.
        # Approved Leave = 3.0 days.
        # Total Paid Days = 2.5 + 3.0 = 5.5 days.
        # Unpaid days = 22 - 5.5 = 16.5 days.
        calcs = payroll_calculator.calculate_employee_payroll(
            db=db,
            employee_id=db_emp.id,
            month="2026-06",
            working_days=22
        )
        print(f"  - Base Salary: ${calcs['base_salary']:.2f}")
        print(f"  - Total Allowances: ${calcs['allowances']:.2f} (HRA + TA)")
        print(f"  - Total Deductions: ${calcs['deductions']:.2f} (PF + PT + LOP)")
        print(f"  - Net Payable: ${calcs['net_salary']:.2f}")
        
        # Save payroll record
        db_payroll = models.PayrollRecord(
            employee_id=db_emp.id,
            month=calcs["month"],
            working_days=calcs["working_days"],
            present_days=calcs["present_days"],
            absent_days=calcs["absent_days"],
            base_salary=calcs["base_salary"],
            allowances=calcs["allowances"],
            deductions=calcs["deductions"],
            net_salary=calcs["net_salary"],
            status="Draft"
        )
        db.add(db_payroll)
        db.commit()
        db.refresh(db_payroll)
        print(f"SUCCESS: Saved Payroll Record ID: {db_payroll.id}")

        # 8. Generate Payslip PDF
        print("\n--- Step 8: Generating Payslip PDF Stream ---")
        pdf_stream = payslip_generator.generate_payslip_pdf(db_payroll)
        pdf_bytes = pdf_stream.read()
        print(f"SUCCESS: Generated PDF payslip file stream. Size: {len(pdf_bytes)} bytes.")
        assert len(pdf_bytes) > 0, "PDF stream should not be empty"

        print("\n==============================================")
        print("VERIFICATION COMPLETED: ALL INTEGRITY TESTS PASSED!")
        print("==============================================")

    except Exception as e:
        print(f"\nFAILED: Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_verification()
