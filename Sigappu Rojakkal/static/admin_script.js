// --- Page Setup & Data Loading ---
document.addEventListener('DOMContentLoaded', () => {
    loadEmployeeData();
});

async function loadEmployeeData() {
    const tbody = document.getElementById('employeeTableBody');
    tbody.innerHTML = `<tr><td colspan="4"><div class="loader-container"><div class="loader"></div></div></td></tr>`;
    try {
        const res = await fetch('/admin/employees', { credentials: 'include' });
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();
        
        tbody.innerHTML = '';
        if (data.success && data.employees.length > 0) {
            data.employees.forEach(emp => {
                tbody.innerHTML += `
                    <tr>
                        <td>${emp.id}</td>
                        <td>${emp.name || 'N/A'}</td>
                        <td>${emp.role_name || 'N/A'}</td>
                        <td>
                            <div class="table-actions">
                                <a href="/admin/ai_report/${emp.id}" class="report-btn"><i class="fas fa-robot"></i> Roadmap</a>
                                <button class="profile-agent-btn" onclick="runProfileAgent(${emp.id}, '${emp.name}')"><i class="fas fa-user-check"></i> Profile</button>
                                <button class="delete-action-btn" onclick="deleteEmployee(${emp.id})"><i class="fas fa-trash-alt"></i></button>
                            </div>
                        </td>
                    </tr>`;
            });
        } else {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 2rem;">No employees found.</td></tr>';
        }
    } catch (err) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 2rem; color: var(--danger-color);">Failed to load data.</td></tr>';
        console.error(err);
    }
}

// --- Modal Handling ---
function openModal(modalId) { document.getElementById(modalId).classList.add('show'); }
function closeModal(modalId) { document.getElementById(modalId).classList.remove('show'); }

// --- Profile Agent ---
async function runProfileAgent(empId, empName) {
    const resultContainer = document.getElementById('profileAgentResult');
    document.getElementById('profileModalTitle').textContent = `AI Profile Agent Analysis for ${empName}`;
    
    openModal('profileAgentModal');
    resultContainer.innerHTML = '<div class="loader-container"><div class="loader"></div><p>Agent is analyzing profile...</p></div>';

    try {
        const res = await fetch(`/admin/api/profile_agent/${empId}`, { credentials: 'include' });
        const result = await res.json();
        
        if (result.success) {
            const data = result.data;
            let content = '<h4>Inferred Skill Vectors</h4><ul class="skill-vectors">';
            if (data.skill_vectors && data.skill_vectors.length > 0) {
                data.skill_vectors.forEach(v => {
                    content += `<li><strong>${v.skill}:</strong> ${v.level}</li>`;
                });
            } else {
                content += '<li>No skill vectors inferred.</li>';
            }
            content += '</ul><h4>History Logs</h4><ul class="history-logs">';
            if (data.history_logs && data.history_logs.length > 0) {
                data.history_logs.forEach(log => {
                    content += `<li>${log}</li>`;
                });
            } else {
                content += '<li>No history logs generated.</li>';
            }
            content += '</ul>';
            resultContainer.innerHTML = content;
        } else {
            resultContainer.innerHTML = `<p style="color: var(--danger-color);">${result.message}</p>`;
        }
    } catch (err) {
        resultContainer.innerHTML = `<p style="color: var(--danger-color);">An error occurred while contacting the agent.</p>`;
    }
}

// --- Add/Edit Employee ---
async function handleFormSubmit(event) {
    event.preventDefault();
    const submitBtn = document.getElementById('submitBtn');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    submitBtn.disabled = true;

    const data = {
        Name: document.getElementById('name').value, Password: document.getElementById('password').value,
        HTML: parseInt(document.getElementById('HTML').value) || 0, CSS: parseInt(document.getElementById('CSS').value) || 0,
        JAVASCRIPT: parseInt(document.getElementById('JAVASCRIPT').value) || 0, PYTHON: parseInt(document.getElementById('PYTHON').value) || 0,
        JAVA: parseInt(document.getElementById('JAVA').value) || 0, C: parseInt(document.getElementById('C').value) || 0,
        CPP: parseInt(document.getElementById('CPP').value) || 0, SQL_TESTING: parseInt(document.getElementById('SQL_TESTING').value) || 0,
        TOOLS_COURSE: parseInt(document.getElementById('TOOLS_COURSE').value) || 0,
    };

    try {
        const res = await fetch('/admin/employees', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data), credentials: 'include'
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            closeModal('employeeModal');
            document.getElementById('employeeForm').reset();
            loadEmployeeData();
        } else {
            showToast(result.message || "An error occurred.", 'error');
        }
    } catch (err) {
        showToast("Failed to connect to the server.", 'error');
    } finally {
        submitBtn.innerHTML = originalBtnText;
        submitBtn.disabled = false;
    }
}

// --- Delete Functionality ---
async function deleteEmployee(empId) {
    if (!confirm(`Are you sure you want to delete employee with ID ${empId}? This action cannot be undone.`)) {
        return;
    }
    try {
        const res = await fetch('/admin/employees/delete', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ emp_id: empId }), credentials: 'include'
        });
        const result = await res.json();
        if (result.success) {
            showToast(result.message, 'success');
            loadEmployeeData();
        } else {
            showToast(result.message || 'Error deleting employee.', 'error');
        }
    } catch (err) {
        showToast('Failed to connect to the server.', 'error');
    }
}

// --- Bulk Upload Functionality ---
const dropArea = document.getElementById("drop-area");
const fileElem = document.getElementById("fileElem");
const fileNameDisplay = document.getElementById("file-name");
const uploadBtn = document.getElementById("uploadBtn");
let selectedFile = null;

if (dropArea) {
    dropArea.addEventListener("click", () => fileElem.click());
    fileElem.addEventListener("change", (e) => updateFile(e.target.files[0]));
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => dropArea.addEventListener(eventName, (e) => { e.preventDefault(); e.stopPropagation(); }, false));
    ['dragenter', 'dragover'].forEach(eventName => dropArea.addEventListener(eventName, () => dropArea.classList.add('dragover'), false));
    ['dragleave', 'drop'].forEach(eventName => dropArea.addEventListener(eventName, () => dropArea.classList.remove('dragover'), false));
    dropArea.addEventListener('drop', (e) => updateFile(e.dataTransfer.files[0]), false);
    uploadBtn.addEventListener("click", uploadFile);
}


function updateFile(file) {
  selectedFile = file;
  if (selectedFile) {
    fileNameDisplay.textContent = selectedFile.name;
    uploadBtn.disabled = false;
  }
}

async function uploadFile() {
    if (!selectedFile) return;
    const formData = new FormData();
    formData.append("file", selectedFile);
    uploadBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    uploadBtn.disabled = true;

    try {
        const response = await fetch("/admin/employees/upload", { method: "POST", body: formData, credentials: 'include' });
        const result = await response.json();
        if (result.success) {
            showToast(result.message, 'success');
            closeModal('uploadModal');
            loadEmployeeData();
        } else {
            showToast(result.message, 'error');
        }
    } catch (err) {
        showToast('Upload failed due to a network error.', 'error');
    } finally {
        fileNameDisplay.textContent = "No file selected";
        uploadBtn.innerHTML = "Upload & Process";
        selectedFile = null;
    }
}

// --- Utilities (Toast, Logout) ---
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast`;
    toast.style.borderColor = type === 'success' ? 'var(--success-color)' : 'var(--danger-color)';
    const iconClass = type === 'success' ? 'fa-check-circle' : 'fa-times-circle';
    toast.innerHTML = `<i class="fas ${iconClass}" style="color: ${type === 'success' ? 'var(--success-color)' : 'var(--danger-color)'};"></i> <p>${message}</p>`;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        toast.addEventListener('transitionend', () => toast.remove());
    }, 5000);
}

async function logout(event) {
    event.preventDefault();
    await fetch("/logout", {method: "POST", credentials: "include"});
    window.location.href = "/";
}