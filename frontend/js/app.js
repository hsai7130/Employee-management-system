// ========================================== //
//          API HELPER & STATE STATE          //
// ========================================== //

const API_BASE = window.location.origin;

const state = {
    token: localStorage.getItem('ems_token'),
    user: null,
    employee: null,
    employeesList: [] // Cache for dropdown select elements
};

// Global Headers Configuration
function getHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${state.token}`
    };
}

// Global API Request Wrapper with Auto Login Checks
async function apiRequest(endpoint, options = {}) {
    options.headers = { ...getHeaders(), ...options.headers };
    
    try {
        const response = await fetch(`${API_BASE}${endpoint}`, options);
        
        if (response.status === 401) {
            // Unauthenticated - Log out and reset
            logout();
            showToast("Session expired. Please log in again.", "error");
            throw new Error("Unauthorized");
        }
        
        if (response.status === 204) {
            return true;
        }
        
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "Something went wrong");
        }
        return data;
    } catch (err) {
        if (err.message !== "Unauthorized") {
            showToast(err.message, "error");
        }
        throw err;
    }
}

// Helper to show modern toast notifications
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    let iconClass = 'fa-circle-info';
    if (type === 'success') iconClass = 'fa-circle-check';
    if (type === 'error') iconClass = 'fa-circle-exclamation';
    if (type === 'warning') iconClass = 'fa-triangle-exclamation';
    
    toast.innerHTML = `<i class="fa-solid ${iconClass}"></i> <span>${message}</span>`;
    container.appendChild(toast);
    
    // Auto remove
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4500);
}

// ========================================== //
//          ON WINDOW INITIAL LOAD            //
// ========================================== //

window.addEventListener('DOMContentLoaded', () => {
    initClock();
    
    // Auth Check
    if (state.token) {
        verifyAuthSession();
    } else {
        showLoginView();
    }
    
    // Form Submissions Registration
    document.getElementById('login-form').addEventListener('submit', handleLoginSubmit);
    document.getElementById('employee-form').addEventListener('submit', handleEmployeeFormSubmit);
    document.getElementById('manual-attendance-form').addEventListener('submit', handleManualAttendanceSubmit);
    document.getElementById('leave-request-form').addEventListener('submit', handleLeaveRequestSubmit);
    document.getElementById('payroll-generate-form').addEventListener('submit', handlePayrollGenerateSubmit);
    
    // Modal buttons bindings
    document.getElementById('btn-add-employee').addEventListener('click', () => showEmployeeModal());
    document.querySelectorAll('.btn-close-modal').forEach(btn => {
        btn.addEventListener('click', hideEmployeeModal);
    });
    
    // Logout binding
    document.getElementById('btn-logout').addEventListener('click', logout);
    
    // Sidebar items bindings
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetSection = item.getAttribute('data-target');
            switchSection(targetSection);
        });
    });
    
    // Clock-in & out punch binding
    document.getElementById('btn-clock-in').addEventListener('click', handleClockIn);
    document.getElementById('btn-clock-out').addEventListener('click', handleClockOut);
    
    // Filter click handlers
    document.getElementById('btn-fetch-attendance').addEventListener('click', loadAttendanceLogs);
    document.getElementById('btn-fetch-payroll').addEventListener('click', loadPayrollRecords);
});

// ========================================== //
//            CLOCK & DIGITAL TIMER           //
// ========================================== //

function initClock() {
    const formatTime = (date) => {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    };
    
    // Top Bar Clock
    setInterval(() => {
        const now = new Date();
        const clockEl = document.getElementById('digital-clock');
        if (clockEl) clockEl.innerText = formatTime(now);
        
        // Large dashboard clock (Employee clock card)
        const largeClock = document.getElementById('large-clock');
        const largeAmPm = document.getElementById('large-clock-ampm');
        if (largeClock) {
            const timeParts = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }).split(' ');
            largeClock.innerText = timeParts[0];
            largeAmPm.innerText = timeParts[1] || '';
        }
    }, 1000);
}

// ========================================== //
//          AUTH FLOW & VIEW SWAPS            //
// ========================================== //

async function verifyAuthSession() {
    try {
        const userData = await apiRequest('/api/auth/me');
        state.user = userData;
        
        document.getElementById('display-username').innerText = state.user.username;
        document.getElementById('display-role').innerText = state.user.role.toUpperCase();
        
        const roleIcon = document.getElementById('user-role-icon');
        if (state.user.role === 'admin') {
            roleIcon.className = 'fa-solid fa-user-shield';
            document.querySelectorAll('.admin-only').forEach(el => el.classList.remove('hidden'));
            document.querySelectorAll('.employee-only').forEach(el => el.classList.add('hidden'));
        } else {
            roleIcon.className = 'fa-solid fa-user';
            document.querySelectorAll('.admin-only').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.employee-only').forEach(el => el.classList.remove('hidden'));
            
            // Get employee profile for standard users
            const profile = await apiRequest('/api/employees/me');
            state.employee = profile;
        }
        
        showDashboardView();
        switchSection('dashboard');
        
    } catch (err) {
        logout();
    }
}

async function handleLoginSubmit(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    
    try {
        const data = await apiRequest('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ username, password })
        });
        
        localStorage.setItem('ems_token', data.access_token);
        state.token = data.access_token;
        
        showToast("Logged in successfully!", "success");
        verifyAuthSession();
    } catch (err) {
        // Error toast shown by API helper
    }
}

function logout() {
    localStorage.removeItem('ems_token');
    state.token = null;
    state.user = null;
    state.employee = null;
    
    // Clear forms
    document.getElementById('login-form').reset();
    showLoginView();
}

function showLoginView() {
    document.getElementById('login-container').classList.remove('hidden');
    document.getElementById('app-container').classList.add('hidden');
}

function showDashboardView() {
    document.getElementById('login-container').classList.add('hidden');
    document.getElementById('app-container').classList.remove('hidden');
}

// ========================================== //
//              SECTION MANAGER               //
// ========================================== //

function switchSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('.content-section').forEach(sec => sec.classList.add('hidden'));
    
    // Remove active class from menu items
    document.querySelectorAll('.sidebar-nav li').forEach(li => li.classList.remove('active'));
    
    // Show selected section
    const targetSection = document.getElementById(`section-${sectionId}`);
    if (targetSection) {
        targetSection.classList.remove('hidden');
    }
    
    // Set active class on menu list
    const activeMenuItem = document.querySelector(`.sidebar-nav li[data-target="${sectionId}"]`);
    if (activeMenuItem) {
        activeMenuItem.classList.add('active');
    }
    
    // Update titles
    const titleEl = document.getElementById('page-title');
    const subtitleEl = document.getElementById('page-subtitle');
    
    // Capitalize Section Title
    titleEl.innerText = sectionId.charAt(0).toUpperCase() + sectionId.slice(1);
    
    // Perform load events for specific pages
    if (sectionId === 'dashboard') {
        subtitleEl.innerText = "At-a-glance analytics and real-time status.";
        loadDashboardData();
    } else if (sectionId === 'employees') {
        subtitleEl.innerText = "Manage corporate employee directories and credentials.";
        loadEmployeesData();
    } else if (sectionId === 'attendance') {
        subtitleEl.innerText = "Track check-in times and work hours.";
        initAttendanceSection();
    } else if (sectionId === 'leaves') {
        subtitleEl.innerText = "Apply for leave and monitor balances.";
        loadLeavesSection();
    } else if (sectionId === 'payroll') {
        subtitleEl.innerText = "Process wages, compute deductions, and issue payslips.";
        initPayrollSection();
    }
}

// ========================================== //
//           DASHBOARD CONTROLLER             //
// ========================================== //

async function loadDashboardData() {
    if (state.user.role === 'admin') {
        try {
            const stats = await apiRequest('/api/admin/stats');
            document.getElementById('stat-total-employees').innerText = stats.total_employees;
            document.getElementById('stat-pending-leaves').innerText = stats.active_leaves_pending;
            document.getElementById('stat-present-today').innerText = stats.attendance_today_count;
            document.getElementById('stat-monthly-payout').innerText = `$${stats.monthly_payout.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;
        } catch (e) {}
    } else {
        // Employee dashboard clock widget
        loadEmployeePunchConsole();
        loadEmployeeLeaveBalances();
    }
    
    // Common: Today's Clocks List
    loadRecentClocks();
}

async function loadRecentClocks() {
    try {
        const list = await apiRequest('/api/attendance/today');
        const tbody = document.querySelector('#dashboard-recent-attendance tbody');
        tbody.innerHTML = '';
        
        if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">No attendance logs logged today.</td></tr>`;
            return;
        }
        
        list.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>EMP-${row.employee_id}</strong></td>
                <td><span class="badge badge-${row.status.toLowerCase().replace(' ', '-')}">${row.status}</span></td>
                <td><i class="fa-solid fa-arrow-right-to-bracket text-muted"></i> ${row.clock_in}</td>
                <td><i class="fa-solid fa-arrow-right text-muted"></i> ${row.clock_out || '--:--:--'}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {}
}

// ========================================== //
//        EMPLOYEE PUNCH CONSOLE (CLOCK)       //
// ========================================== //

async function loadEmployeePunchConsole() {
    try {
        const list = await apiRequest('/api/attendance/today');
        const clockInBtn = document.getElementById('btn-clock-in');
        const clockOutBtn = document.getElementById('btn-clock-out');
        const banner = document.getElementById('clock-status-banner');
        
        if (list.length > 0 && list[0]) {
            const record = list[0];
            banner.className = "status-banner clocked-in";
            
            if (record.clock_out) {
                banner.innerHTML = `<i class="fa-solid fa-circle-check"></i> Shift Finished! Clocks: ${record.clock_in} - ${record.clock_out} (${record.status})`;
                clockInBtn.disabled = true;
                clockOutBtn.disabled = true;
            } else {
                banner.innerHTML = `<i class="fa-solid fa-circle-play"></i> Active Shift Clocked-in: <strong>${record.clock_in}</strong>`;
                clockInBtn.disabled = true;
                clockOutBtn.disabled = false;
            }
        } else {
            banner.className = "status-banner";
            banner.innerText = "Ready to punch. Shift starts at 09:00 AM.";
            clockInBtn.disabled = false;
            clockOutBtn.disabled = true;
        }
    } catch (e) {}
}

async function handleClockIn() {
    try {
        await apiRequest('/api/attendance/clock-in', { method: 'POST' });
        showToast("Successfully Clocked In!", "success");
        loadDashboardData();
    } catch (e) {}
}

async function handleClockOut() {
    try {
        await apiRequest('/api/attendance/clock-out', { method: 'POST' });
        showToast("Successfully Clocked Out!", "success");
        loadDashboardData();
    } catch (e) {}
}

async function loadEmployeeLeaveBalances() {
    try {
        const list = await apiRequest('/api/leaves/balances');
        const el = document.getElementById('emp-balances-list');
        el.innerHTML = '';
        
        list.forEach(b => {
            const item = document.createElement('div');
            item.className = 'balance-item';
            const available = b.allocated - b.used;
            
            item.innerHTML = `
                <span class="balance-label">${b.leave_type} Leave</span>
                <span class="balance-values">
                    <span>${available}</span> / ${b.allocated} Left
                </span>
            `;
            el.appendChild(item);
        });
    } catch (e) {}
}

// ========================================== //
//          EMPLOYEE DIRECTORY WORK           //
// ========================================== //

async function loadEmployeesData() {
    try {
        const list = await apiRequest('/api/employees');
        state.employeesList = list;
        
        const tbody = document.querySelector('#employees-table tbody');
        tbody.innerHTML = '';
        
        if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted">No employees registered. Add one to start.</td></tr>`;
            return;
        }
        
        list.forEach(e => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>EMP-${e.id}</strong></td>
                <td>${e.first_name} ${e.last_name}</td>
                <td>${e.department || 'N/A'}</td>
                <td>${e.designation || 'N/A'}</td>
                <td><strong>$${e.base_salary.toLocaleString()}</strong></td>
                <td>${e.email}</td>
                <td>
                    <button class="btn btn-secondary btn-small btn-edit-emp" data-id="${e.id}"><i class="fa-solid fa-pen"></i></button>
                    <button class="btn btn-danger btn-small btn-del-emp" data-id="${e.id}"><i class="fa-solid fa-trash"></i></button>
                </td>
            `;
            tbody.appendChild(tr);
        });
        
        // Register Event Listeners for actions
        document.querySelectorAll('.btn-edit-emp').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                const empObj = state.employeesList.find(x => x.id == id);
                showEmployeeModal(empObj);
            });
        });
        
        document.querySelectorAll('.btn-del-emp').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.getAttribute('data-id');
                if (confirm(`Are you sure you want to remove Employee ID: EMP-${id}?`)) {
                    try {
                        await apiRequest(`/api/employees/${id}`, { method: 'DELETE' });
                        showToast("Employee deleted successfully", "success");
                        loadEmployeesData();
                    } catch (err) {}
                }
            });
        });
        
    } catch (e) {}
}

function showEmployeeModal(empObj = null) {
    const modal = document.getElementById('employee-modal');
    const title = document.getElementById('employee-modal-title');
    const credSection = document.getElementById('account-credentials-section');
    
    // Clear Form
    document.getElementById('employee-form').reset();
    
    if (empObj) {
        title.innerText = "Edit Employee Profile";
        credSection.classList.add('hidden'); // Hide password fields for edit
        document.getElementById('employee-username').required = false;
        document.getElementById('employee-password').required = false;
        
        // Populate inputs
        document.getElementById('employee-id-hidden').value = empObj.id;
        document.getElementById('employee-firstname').value = empObj.first_name;
        document.getElementById('employee-lastname').value = empObj.last_name;
        document.getElementById('employee-email').value = empObj.email;
        document.getElementById('employee-phone').value = empObj.phone || '';
        document.getElementById('employee-dept').value = empObj.department || 'Engineering';
        document.getElementById('employee-desg').value = empObj.designation || '';
        document.getElementById('employee-join-date').value = empObj.join_date;
        document.getElementById('employee-salary').value = empObj.base_salary;
        document.getElementById('employee-bank').value = empObj.bank_account || '';
    } else {
        title.innerText = "Register New Employee";
        credSection.classList.remove('hidden');
        document.getElementById('employee-username').required = true;
        document.getElementById('employee-password').required = true;
        document.getElementById('employee-id-hidden').value = '';
    }
    
    modal.classList.remove('hidden');
}

function hideEmployeeModal() {
    document.getElementById('employee-modal').classList.add('hidden');
}

async function handleEmployeeFormSubmit(e) {
    e.preventDefault();
    
    const id = document.getElementById('employee-id-hidden').value;
    const isEdit = id !== '';
    
    const bodyData = {
        first_name: document.getElementById('employee-firstname').value,
        last_name: document.getElementById('employee-lastname').value,
        email: document.getElementById('employee-email').value,
        phone: document.getElementById('employee-phone').value || null,
        department: document.getElementById('employee-dept').value,
        designation: document.getElementById('employee-desg').value || null,
        join_date: document.getElementById('employee-join-date').value,
        base_salary: parseFloat(document.getElementById('employee-salary').value),
        bank_account: document.getElementById('employee-bank').value || null,
    };
    
    if (!isEdit) {
        bodyData.username = document.getElementById('employee-username').value;
        bodyData.password = document.getElementById('employee-password').value;
    }
    
    const endpoint = isEdit ? `/api/employees/${id}` : '/api/employees';
    const method = isEdit ? 'PUT' : 'POST';
    
    try {
        await apiRequest(endpoint, {
            method: method,
            body: JSON.stringify(bodyData)
        });
        
        showToast(isEdit ? "Profile updated successfully!" : "Employee registered successfully!", "success");
        hideEmployeeModal();
        loadEmployeesData();
    } catch (err) {}
}

// ========================================== //
//             ATTENDANCE SECTION             //
// ========================================== //

async function initAttendanceSection() {
    // Fill Date values
    document.getElementById('manual-att-date').value = new Date().toISOString().split('T')[0];
    
    if (state.user.role === 'admin') {
        await populateEmployeesDropdown();
        loadAttendanceLogs();
    } else {
        loadAttendanceLogs();
    }
}

async function populateEmployeesDropdown() {
    try {
        const list = await apiRequest('/api/employees');
        state.employeesList = list;
        
        document.querySelectorAll('.select-emp-list').forEach(select => {
            select.innerHTML = '';
            list.forEach(emp => {
                const opt = document.createElement('option');
                opt.value = emp.id;
                opt.innerText = `[EMP-${emp.id}] ${emp.first_name} ${emp.last_name}`;
                select.appendChild(opt);
            });
        });
    } catch (e) {}
}

async function loadAttendanceLogs() {
    let endpoint = '/api/attendance/history';
    
    if (state.user.role === 'admin') {
        const empId = document.getElementById('attendance-filter-emp').value;
        if (!empId) return;
        endpoint += `?employee_id=${empId}`;
    }
    
    try {
        const list = await apiRequest(endpoint);
        const tbody = document.querySelector('#attendance-history-table tbody');
        tbody.innerHTML = '';
        
        if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted">No attendance logs registered in this query.</td></tr>`;
            return;
        }
        
        list.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${row.date}</strong></td>
                <td>${row.clock_in}</td>
                <td>${row.clock_out || '--:--:--'}</td>
                <td><span class="badge badge-${row.status.toLowerCase().replace(' ', '-')}">${row.status}</span></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (e) {}
}

async function handleManualAttendanceSubmit(e) {
    e.preventDefault();
    const data = {
        employee_id: parseInt(document.getElementById('manual-att-emp').value),
        date: document.getElementById('manual-att-date').value,
        clock_in: document.getElementById('manual-att-in').value,
        clock_out: document.getElementById('manual-att-out').value || null,
        status: document.getElementById('manual-att-status').value
    };
    
    try {
        await apiRequest('/api/attendance/manual', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        showToast("Attendance override saved successfully", "success");
        loadAttendanceLogs();
    } catch (e) {}
}

// ========================================== //
//               LEAVES SECTION               //
// ========================================== //

async function loadLeavesSection() {
    // Date fields setups
    const todayStr = new Date().toISOString().split('T')[0];
    document.getElementById('leave-start-date').value = todayStr;
    document.getElementById('leave-end-date').value = todayStr;
    
    // Title setups
    const listHeader = document.getElementById('leaves-list-header');
    if (state.user.role === 'admin') {
        listHeader.innerText = "Pending Leave Approvals";
    } else {
        listHeader.innerText = "Your Leave Request History";
    }
    
    loadLeaveBalancesSummary();
    loadLeaveRequestsList();
}

async function loadLeaveBalancesSummary() {
    try {
        // Balances widget on Leaves page
        let endpoint = '/api/leaves/balances';
        if (state.user.role === 'admin') {
            // Admin can view balance but it needs an employee selection
            // We'll hide balance summary container for admin entirely to avoid UI clutter
            document.querySelector('#section-leaves .leave-balances-widget').classList.add('hidden');
            return;
        } else {
            document.querySelector('#section-leaves .leave-balances-widget').classList.remove('hidden');
        }
        
        const list = await apiRequest(endpoint);
        const el = document.getElementById('leaves-balance-summary-list');
        el.innerHTML = '';
        
        list.forEach(b => {
            const item = document.createElement('div');
            item.className = 'balance-item';
            const available = b.allocated - b.used;
            item.innerHTML = `
                <span class="balance-label">${b.leave_type} Leave</span>
                <span class="balance-values">
                    <span>${available}</span> / ${b.allocated} Available
                </span>
            `;
            el.appendChild(item);
        });
    } catch (e) {}
}

async function loadLeaveRequestsList() {
    // Fetch Requests
    let endpoint = '/api/leaves/requests';
    if (state.user.role === 'admin') {
        endpoint += '?status=Pending'; // Admins only see Pending to action them
    }
    
    try {
        const list = await apiRequest(endpoint);
        const tbody = document.querySelector('#leaves-table-list tbody');
        tbody.innerHTML = '';
        
        if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No leave applications registered.</td></tr>`;
            return;
        }
        
        list.forEach(row => {
            const tr = document.createElement('tr');
            
            // Format dates count
            const days = Math.round((new Date(row.end_date) - new Date(row.start_date)) / (1000 * 60 * 60 * 24)) + 1;
            const empLabel = row.employee ? `[EMP-${row.employee_id}] ${row.employee.first_name} ${row.employee.last_name}` : `EMP-${row.employee_id}`;
            
            let actionHtml = '';
            if (state.user.role === 'admin' && row.status === 'Pending') {
                actionHtml = `
                    <button class="btn btn-success btn-small btn-approve-leave" data-id="${row.id}"><i class="fa-solid fa-check"></i></button>
                    <button class="btn btn-danger btn-small btn-reject-leave" data-id="${row.id}"><i class="fa-solid fa-xmark"></i></button>
                `;
            } else {
                actionHtml = `<span class="text-muted text-small">Processed</span>`;
            }
            
            tr.innerHTML = `
                <td>${state.user.role === 'admin' ? empLabel : 'You'}</td>
                <td><strong>${row.leave_type}</strong></td>
                <td>${row.start_date} to ${row.end_date}<br/><small class="text-muted">(${days} day${days > 1 ? 's' : ''})</small></td>
                <td style="max-width: 150px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">${row.reason || 'N/A'}</td>
                <td><span class="badge badge-${row.status.toLowerCase()}">${row.status}</span></td>
                <td>${actionHtml}</td>
            `;
            tbody.appendChild(tr);
        });
        
        // Listeners for approvals
        if (state.user.role === 'admin') {
            document.querySelectorAll('.btn-approve-leave').forEach(btn => {
                btn.addEventListener('click', () => handleLeaveAction(btn.getAttribute('data-id'), 'Approved'));
            });
            document.querySelectorAll('.btn-reject-leave').forEach(btn => {
                btn.addEventListener('click', () => handleLeaveAction(btn.getAttribute('data-id'), 'Rejected'));
            });
        }
    } catch (e) {}
}

async function handleLeaveAction(id, status) {
    try {
        await apiRequest(`/api/leaves/requests/${id}/approve`, {
            method: 'PUT',
            body: JSON.stringify({ status })
        });
        showToast(`Leave application successfully ${status}!`, "success");
        loadLeaveRequestsList();
    } catch (e) {}
}

async function handleLeaveRequestSubmit(e) {
    e.preventDefault();
    const data = {
        leave_type: document.getElementById('leave-type').value,
        start_date: document.getElementById('leave-start-date').value,
        end_date: document.getElementById('leave-end-date').value,
        reason: document.getElementById('leave-reason').value
    };
    
    try {
        await apiRequest('/api/leaves/request', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        showToast("Leave request submitted successfully", "success");
        document.getElementById('leave-request-form').reset();
        loadLeavesSection();
    } catch (e) {}
}

// ========================================== //
//              PAYROLL SECTION               //
// ========================================== //

async function initPayrollSection() {
    // Current Month formatted YYYY-MM
    const currentMonthStr = new Date().toISOString().substring(0, 7);
    document.getElementById('payroll-month').value = currentMonthStr;
    document.getElementById('payroll-filter-month').value = currentMonthStr;
    
    loadPayrollRecords();
}

async function handlePayrollGenerateSubmit(e) {
    e.preventDefault();
    const month = document.getElementById('payroll-month').value;
    const workingDays = parseInt(document.getElementById('payroll-working-days').value);
    
    try {
        await apiRequest(`/api/payroll/process`, {
            method: 'POST',
            body: JSON.stringify({ month, working_days: workingDays })
        });
        showToast(`Payroll processed successfully for ${month}!`, "success");
        loadPayrollRecords();
    } catch (e) {}
}

async function loadPayrollRecords() {
    const filterMonth = document.getElementById('payroll-filter-month').value;
    let url = '/api/payroll/records';
    if (filterMonth) {
        url += `?month=${filterMonth}`;
    }
    
    try {
        const list = await apiRequest(url);
        const tbody = document.querySelector('#payroll-table tbody');
        tbody.innerHTML = '';
        
        if (list.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">No payroll summaries found for selected query.</td></tr>`;
            return;
        }
        
        list.forEach(row => {
            const tr = document.createElement('tr');
            
            const empLabel = row.employee ? `<strong>[EMP-${row.employee_id}]</strong> ${row.employee.first_name} ${row.employee.last_name}` : `EMP-${row.employee_id}`;
            const presentAbsLabel = `${row.working_days} total (${row.present_days} Prs / ${row.absent_days} Abs)`;
            
            // Actions
            let actionsHtml = `<button class="btn btn-secondary btn-small btn-payslip-dl" data-id="${row.id}" title="Download Payslip PDF"><i class="fa-solid fa-file-pdf"></i> Download</button>`;
            
            if (state.user.role === 'admin') {
                if (row.status === 'Draft') {
                    actionsHtml += ` <button class="btn btn-success btn-small btn-payroll-pay" data-id="${row.id}" title="Mark as Paid"><i class="fa-solid fa-circle-dollar-to-slot"></i> Pay</button>`;
                }
                actionsHtml += ` <button class="btn btn-danger btn-small btn-payroll-del" data-id="${row.id}" title="Delete Calculation"><i class="fa-solid fa-trash"></i></button>`;
            }
            
            tr.innerHTML = `
                <td>${empLabel}</td>
                <td>${row.month}</td>
                <td>${presentAbsLabel}</td>
                <td>$${row.base_salary.toFixed(2)}</td>
                <td>$${row.allowances.toFixed(2)}</td>
                <td class="text-danger">-$${row.deductions.toFixed(2)}</td>
                <td class="font-bold">$${row.net_salary.toFixed(2)}</td>
                <td><span class="badge badge-${row.status.toLowerCase()}">${row.status}</span></td>
                <td>${actionsHtml}</td>
            `;
            tbody.appendChild(tr);
        });
        
        // Register actions listeners
        document.querySelectorAll('.btn-payslip-dl').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.getAttribute('data-id');
                downloadPayslip(id);
            });
        });
        
        if (state.user.role === 'admin') {
            document.querySelectorAll('.btn-payroll-pay').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = btn.getAttribute('data-id');
                    try {
                        await apiRequest(`/api/payroll/records/${id}/pay`, { method: 'PUT' });
                        showToast("Payroll record marked as paid", "success");
                        loadPayrollRecords();
                    } catch (e) {}
                });
            });
            
            document.querySelectorAll('.btn-payroll-del').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const id = btn.getAttribute('data-id');
                    if (confirm("Delete this payroll calculation?")) {
                        try {
                            await apiRequest(`/api/payroll/records/${id}`, { method: 'DELETE' });
                            showToast("Payroll calculation deleted", "success");
                            loadPayrollRecords();
                        } catch (e) {}
                    }
                });
            });
        }
    } catch (e) {}
}

async function downloadPayslip(recordId) {
    try {
        const response = await fetch(`${API_BASE}/api/payroll/records/${recordId}/payslip`, {
            headers: {
                'Authorization': `Bearer ${state.token}`
            }
        });
        
        if (!response.ok) {
            throw new Error("Could not download payslip file.");
        }
        
        const blob = await response.blob();
        
        // Find filename
        const contentDisposition = response.headers.get('Content-Disposition');
        let filename = `payslip_${recordId}.pdf`;
        if (contentDisposition) {
            const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(contentDisposition);
            if (matches != null && matches[1]) {
                filename = matches[1].replace(/['"]/g, '');
            }
        }
        
        const link = document.createElement('a');
        link.href = window.URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        showToast("Payslip downloaded successfully!", "success");
    } catch (e) {
        showToast(e.message, "error");
    }
}
