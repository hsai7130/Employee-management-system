from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
import models

def generate_payslip_pdf(payroll: models.PayrollRecord) -> BytesIO:
    """
    Generates a professional PDF payslip using ReportLab and returns it as a BytesIO stream.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'PayslipTitle',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=15,
        alignment=1 # Center
    )
    
    company_style = ParagraphStyle(
        'CompanyHeader',
        parent=styles['Normal'],
        fontSize=12,
        textColor=colors.HexColor('#475569'),
        spaceAfter=2,
        alignment=1 # Center
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading3'],
        fontSize=11,
        textColor=colors.HexColor('#1e293b'),
        spaceBefore=10,
        spaceAfter=5
    )
    
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#334155')
    )
    
    cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#0f172a')
    )
    
    story = []
    
    # --- HEADER ---
    story.append(Paragraph("CLOUD ENTERPRISE SOLUTIONS INC.", title_style))
    story.append(Paragraph("100 Tech Park, Suite 400, Cloud City, CA 94016", company_style))
    story.append(Paragraph("Email: payroll@cloudenterprise.com | Tel: +1-800-555-0199", company_style))
    story.append(Spacer(1, 15))
    
    # Divider Line
    line_data = [['']]
    line_table = Table(line_data, colWidths=[532], rowHeights=[2])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#3b82f6')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 15))
    
    story.append(Paragraph(f"PAY SLIP - {payroll.month}", ParagraphStyle('Subtitle', parent=title_style, fontSize=14, spaceAfter=10)))
    
    # --- EMPLOYEE DETAILS TABLE ---
    emp = payroll.employee
    emp_details = [
        [
            Paragraph("Employee ID:", cell_bold), Paragraph(str(emp.id), cell_style),
            Paragraph("Department:", cell_bold), Paragraph(emp.department or "N/A", cell_style)
        ],
        [
            Paragraph("Name:", cell_bold), Paragraph(f"{emp.first_name} {emp.last_name}", cell_style),
            Paragraph("Designation:", cell_bold), Paragraph(emp.designation or "N/A", cell_style)
        ],
        [
            Paragraph("Email:", cell_bold), Paragraph(emp.email, cell_style),
            Paragraph("Bank Account:", cell_bold), Paragraph(emp.bank_account or "N/A", cell_style)
        ],
        [
            Paragraph("Working Days:", cell_bold), Paragraph(str(payroll.working_days), cell_style),
            Paragraph("Days Present:", cell_bold), Paragraph(str(payroll.present_days), cell_style)
        ],
        [
            Paragraph("Days Absent:", cell_bold), Paragraph(str(payroll.absent_days), cell_style),
            Paragraph("Status:", cell_bold), Paragraph(payroll.status, cell_style)
        ]
    ]
    
    details_table = Table(emp_details, colWidths=[110, 156, 110, 156])
    details_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 20))
    
    # --- EARNINGS & DEDUCTIONS BREAKDOWN ---
    # Allowances are hra + ta
    # Deductions are pf + pt + unpaid leave deduction
    hra = payroll.base_salary * 0.10
    ta = payroll.base_salary * 0.05
    pf = payroll.base_salary * 0.12
    pt = 200.0 if payroll.base_salary >= 2000.0 else (payroll.base_salary * 0.05)
    lop = payroll.deductions - (pf + pt) # loss of pay (absent deductions)
    lop = max(0.0, round(lop, 2))
    
    salary_breakdown = [
        [
            Paragraph("Earnings", cell_bold), Paragraph("Amount", cell_bold),
            Paragraph("Deductions", cell_bold), Paragraph("Amount", cell_bold)
        ],
        [
            Paragraph("Basic Salary", cell_style), Paragraph(f"${payroll.base_salary:,.2f}", cell_style),
            Paragraph("Provident Fund (PF)", cell_style), Paragraph(f"${pf:,.2f}", cell_style)
        ],
        [
            Paragraph("House Rent Allowance (HRA)", cell_style), Paragraph(f"${hra:,.2f}", cell_style),
            Paragraph("Professional Tax (PT)", cell_style), Paragraph(f"${pt:,.2f}", cell_style)
        ],
        [
            Paragraph("Travel Allowance (TA)", cell_style), Paragraph(f"${ta:,.2f}", cell_style),
            Paragraph("Loss of Pay (LOP)", cell_style), Paragraph(f"${lop:,.2f}", cell_style)
        ],
        # Total line
        [
            Paragraph("Total Earnings", cell_bold), Paragraph(f"${(payroll.base_salary + payroll.allowances):,.2f}", cell_bold),
            Paragraph("Total Deductions", cell_bold), Paragraph(f"${payroll.deductions:,.2f}", cell_bold)
        ]
    ]
    
    breakdown_table = Table(salary_breakdown, colWidths=[150, 116, 150, 116])
    breakdown_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#e2e8f0')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#94a3b8')),
        ('LINEBELOW', (0,0), (-1,0), 1, colors.HexColor('#94a3b8')),
        ('LINEBELOW', (0,-1), (-1,-1), 1, colors.HexColor('#94a3b8')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(breakdown_table)
    story.append(Spacer(1, 20))
    
    # --- NET SALARY CARD ---
    net_salary_data = [
        [
            Paragraph("NET PAYABLE SALARY (Rounded)", ParagraphStyle('NetStyleBold', parent=cell_bold, fontSize=11, textColor=colors.HexColor('#1e3a8a'))),
            Paragraph(f"${payroll.net_salary:,.2f}", ParagraphStyle('NetAmtStyleBold', parent=cell_bold, fontSize=12, textColor=colors.HexColor('#1d4ed8'), alignment=2))
        ]
    ]
    net_table = Table(net_salary_data, colWidths=[350, 182])
    net_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#eff6ff')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#bfdbfe')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    story.append(net_table)
    story.append(Spacer(1, 40))
    
    # --- SIGNATURES ---
    sig_data = [
        [Paragraph("_____________________________<br/>Employee Signature", cell_style),
         Paragraph("_____________________________<br/>Authorized Signatory", ParagraphStyle('RightAlign', parent=cell_style, alignment=2))]
    ]
    sig_table = Table(sig_data, colWidths=[266, 266])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('TOPPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(sig_table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer
