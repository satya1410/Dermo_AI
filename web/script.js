
const API_URL = "http://127.0.0.1:8000";

// --- NAVIGATION & MODALS ---
function openModal(tab) {
    document.getElementById('auth-modal').style.display = 'flex';
    switchTab(tab);
}

function closeModal() {
    document.getElementById('auth-modal').style.display = 'none';
}

function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.auth-form').forEach(f => f.classList.add('hidden'));

    if (tab === 'login') {
        document.querySelector('.auth-tabs button:first-child').classList.add('active');
        document.getElementById('login-form').classList.remove('hidden');
    } else {
        document.querySelector('.auth-tabs button:last-child').classList.add('active');
        document.getElementById('register-form').classList.remove('hidden');
    }
}

function toggleDoctorFields(show) {
    const fields = document.getElementById('doctor-fields');
    if (show) fields.classList.remove('hidden');
    else fields.classList.add('hidden');
}

// --- AUTHENTICATION ---
document.getElementById('register-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    const role = document.querySelector('input[name="role"]:checked').value;
    const specialty = document.getElementById('reg-specialty')?.value;
    const achievement = document.getElementById('reg-achievement')?.value;
    const msgBox = document.getElementById('auth-msg');

    try {
        const res = await fetch(`${API_URL}/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password, role, specialty, achievement })
        });

        if (res.ok) {
            msgBox.innerHTML = '<span style="color:#4ade80">Registered! Please Log in.</span>';
            setTimeout(() => switchTab('login'), 1500);
        } else {
            const data = await res.json();
            msgBox.innerHTML = `<span style="color:#ef4444">Error: ${data.detail}</span>`;
        }
    } catch (err) {
        msgBox.innerHTML = `<span style="color:#ef4444">Connection Error</span>`;
    }
});

document.getElementById('login-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const msgBox = document.getElementById('auth-msg');

    try {
        const formData = new FormData();
        formData.append('username', email);
        formData.append('password', password);

        const res = await fetch(`${API_URL}/auth/login`, {
            method: 'POST',
            body: formData
        });

        const data = await res.json();
        if (res.ok) {
            localStorage.setItem('token', data.access_token);
            window.location.href = 'dashboard.html';
        } else {
            msgBox.innerHTML = `<span style="color:#ef4444">${data.detail}</span>`;
        }
    } catch (err) {
        msgBox.innerHTML = `<span style="color:#ef4444">Connection Error</span>`;
    }
});

// --- DASHBOARD LOGIC ---
async function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
        window.location.href = 'index.html';
        return;
    }

    try {
        const res = await fetch(`${API_URL}/users/me`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!res.ok) throw new Error("Unauthorized");

        const user = await res.json();
        document.getElementById('user-email').textContent = user.email;
        document.getElementById('prof-email').textContent = user.email;
        document.getElementById('user-role-badge').textContent = user.role.charAt(0).toUpperCase() + user.role.slice(1);
        document.getElementById('prof-role').textContent = user.role;
        document.getElementById('prof-date').textContent = new Date(user.created_at).toLocaleDateString();

        // Role-based visibility
        if (user.role === 'doctor') {
            document.querySelectorAll('.patient-only').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.doctor-only').forEach(el => el.classList.remove('hidden'));
            document.getElementById('prof-specialty-row').classList.remove('hidden');
            document.getElementById('prof-achievement-row').classList.remove('hidden');
            document.getElementById('prof-specialty').textContent = user.specialty || 'N/A';
            document.getElementById('prof-achievement').textContent = user.achievement || 'N/A';
            loadPendingCases();
        } else {
            document.querySelectorAll('.doctor-only').forEach(el => el.classList.add('hidden'));
            document.querySelectorAll('.patient-only').forEach(el => el.classList.remove('hidden'));
            loadDoctors();
        }

        loadHistory();
        loadNotifications();
    } catch (err) {
        localStorage.removeItem('token');
        window.location.href = 'index.html';
    }
}

function showSection(id) {
    document.querySelectorAll('.glass-sidebar li').forEach(li => li.classList.remove('active'));
    event.currentTarget.classList.add('active');

    document.querySelectorAll('.dashboard-content section').forEach(sec => {
        sec.classList.remove('active-section');
        sec.classList.add('hidden-section');
    });

    const sec = document.getElementById(`${id}-section`);
    sec.classList.remove('hidden-section');
    sec.classList.add('active-section');
}

// --- CORE FUNCTIONS ---

async function loadHistory() {
    const token = localStorage.getItem('token');
    try {
        const res = await fetch(`${API_URL}/history`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const history = await res.json();
        const tbody = document.getElementById('history-list');
        tbody.innerHTML = '';
        history.forEach(item => {
            tbody.innerHTML += `<tr>
                <td>${new Date(item.date).toLocaleDateString()}</td>
                <td>${item.diagnosis}</td>
                <td><span class="status-tag ${item.status}">${item.status}</span></td>
                <td><button class="btn-sm btn-glass" onclick="viewReport('${item.id}')">View Report</button></td>
            </tr>`;
        });
    } catch (err) { }
}

async function loadNotifications() {
    const token = localStorage.getItem('token');
    try {
        const res = await fetch(`${API_URL}/notifications`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const notifs = await res.json();
        const list = document.getElementById('notifications-list');
        list.innerHTML = '';
        document.getElementById('notif-count').textContent = notifs.length || '';

        notifs.forEach(n => {
            list.innerHTML += `<div class="notif-item glass-card">
                <i class="fa-solid fa-info-circle"></i>
                <div class="notif-content">
                    <p>${n.message}</p>
                    <span>${new Date(n.created_at).toLocaleString()}</span>
                </div>
            </div>`;
        });
    } catch (err) { }
}

// --- APPOINTMENT SCHEDULING ---

let allDoctors = [];
let currentScheduleDocId = null;
let currentScheduleSlots = [];
let selectedSlot = null;

async function loadDoctors() {
    try {
        const res = await fetch(`${API_URL}/doctors`);
        const doctors = await res.json();
        allDoctors = doctors; // Store globally
        const list = document.getElementById('doctors-list');
        list.innerHTML = '';
        doctors.forEach(d => {
            list.innerHTML += `<div class="doctor-card glass-card">
                <div class="doctor-icon"><i class="fa-solid fa-user-doctor"></i></div>
                <h3>${d.email.split('@')[0]}</h3>
                <p class="specialty">${d.specialty || 'General Dermatologist'}</p>
                <p class="achievement">${d.achievement || 'Expert analysis'}</p>
                <button class="btn-primary" onclick="scheduleMeet('${d.id}')">Schedule Meetup</button>
            </div>`;
        });
    } catch (err) { }
}

function scheduleMeet(docId) {
    const doc = allDoctors.find(d => d.id == docId);
    if (!doc) return;

    currentScheduleDocId = docId;
    document.getElementById('schedule-doc-name').textContent = 'Dr. ' + doc.email.split('@')[0];
    document.getElementById('schedule-doc-specialty').textContent = doc.specialty || 'Specialist';

    document.getElementById('schedule-modal').style.display = 'flex';
    loadSlots(docId);
}

function closeScheduleModal() {
    document.getElementById('schedule-modal').style.display = 'none';
    selectedSlot = null;
    document.getElementById('confirm-booking-btn').disabled = true;
}

async function loadSlots(docId) {
    const datesContainer = document.getElementById('schedule-dates');
    const slotsContainer = document.getElementById('schedule-slots-grid');

    datesContainer.innerHTML = '<p>Loading dates...</p>';
    slotsContainer.innerHTML = '';

    try {
        const token = localStorage.getItem('token');
        const res = await fetch(`${API_URL}/doctors/${docId}/slots`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        currentScheduleSlots = data;

        renderDateTabs(0); // Select first day by default
    } catch (err) {
        datesContainer.innerHTML = '<p style="color:red">Failed to load slots</p>';
    }
}

function renderDateTabs(activeIndex) {
    const container = document.getElementById('schedule-dates');
    container.innerHTML = '';

    currentScheduleSlots.forEach((day, index) => {
        const tab = document.createElement('div');
        tab.className = `date-tab ${index === activeIndex ? 'active' : ''}`;

        // Format date: "Mon, Oct 10"
        const d = new Date(day.date);
        const dateStr = d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

        tab.innerHTML = `<strong>${day.day}</strong><br><small>${d.getDate()}</small>`;
        tab.onclick = () => {
            renderDateTabs(index);
            renderSlots(index);
            selectedSlot = null;
            document.getElementById('confirm-booking-btn').disabled = true;
        };
        container.appendChild(tab);
    });

    renderSlots(activeIndex);
}

function renderSlots(dayIndex) {
    const container = document.getElementById('schedule-slots-grid');
    container.innerHTML = '';

    const dayData = currentScheduleSlots[dayIndex];
    if (!dayData || !dayData.slots) return;

    dayData.slots.forEach(slot => {
        const btn = document.createElement('div');
        btn.className = `slot-btn ${slot.status === 'booked' ? 'booked' : ''}`;
        btn.textContent = slot.time;

        if (slot.status === 'available') {
            btn.onclick = () => {
                // Deselect others
                document.querySelectorAll('.slot-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                selectedSlot = {
                    date: dayData.date,
                    time: slot.time
                };
                document.getElementById('confirm-booking-btn').disabled = false;
            };
        } else {
            btn.title = "Not Available";
        }

        container.appendChild(btn);
    });
}

async function confirmAppointment() {
    if (!selectedSlot || !currentScheduleDocId) return;

    const btn = document.getElementById('confirm-booking-btn');
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Booking...';

    const token = localStorage.getItem('token');
    try {
        const res = await fetch(`${API_URL}/appointments`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({
                doctor_id: currentScheduleDocId,
                date: selectedSlot.date,
                time: selectedSlot.time
            })
        });

        if (res.ok) {
            alert("Appointment Scheduled Successfully!");
            closeScheduleModal();
            loadHistory(); // Refresh dashboard
        } else {
            const data = await res.json();
            alert("Booking Failed: " + data.detail);
        }
    } catch (err) {
        alert("Connection Error");
    } finally {
        btn.disabled = false;
        btn.textContent = 'Confirm Booking';
    }
}

// --- FILE UPLOAD HANDLING ---
// ... (rest of file)

document.addEventListener('DOMContentLoaded', () => {
    // ... existing initialization ...
    // Start notification poller
    setInterval(loadNotifications, 30000); // Check every 30s
});

async function loadPendingCases() {
    const token = localStorage.getItem('token');
    try {
        const res = await fetch(`${API_URL}/cases/pending`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const cases = await res.json();
        const tbody = document.getElementById('pending-cases-list');
        tbody.innerHTML = '';
        cases.forEach(c => {
            tbody.innerHTML += `<tr>
                <td>Patient #${c.user_id}</td>
                <td>${c.diagnosis}</td>
                <td>
                    <button class="btn-sm btn-primary" onclick="acceptCase('${c.id}')">Accept Case</button>
                    <button class="btn-sm btn-glass" onclick="viewCaseFile('${c.id}')">View File</button>
                </td>
            </tr>`;
        });
    } catch (err) { }
}

async function acceptCase(id) {
    const token = localStorage.getItem('token');
    try {
        const res = await fetch(`${API_URL}/cases/${id}/accept`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });
        if (res.ok) {
            alert("Case Accepted! The patient has been notified.");
            loadPendingCases();
            loadHistory();
        }
    } catch (err) { }
}

// Store current analysis data for report
let currentAnalysisData = null;

async function analyzeImage() {
    const btn = document.getElementById('analyze-btn');
    const selectedFile = document.getElementById('file-input').files[0];
    if (!selectedFile) return;

    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Analyzing...';
    btn.disabled = true;

    const token = localStorage.getItem('token');
    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('token', token);

    try {
        const res = await fetch(`${API_URL}/predict`, {
            method: 'POST',
            body: formData
        });
        const data = await res.json();

        // Store data for report modal
        currentAnalysisData = data;

        document.getElementById('result-container').classList.remove('hidden');
        document.getElementById('res-diagnosis').textContent = data.diagnosis;
        document.getElementById('res-report').innerHTML = data.report.replace(/\n/g, '<br>');

        if (data.heatmap_base64) {
            document.getElementById('res-heatmap').src = `data:image/png;base64,${data.heatmap_base64}`;
        }
        loadHistory();
    } catch (err) {
        alert("Analysis failed.");
    } finally {
        btn.innerHTML = 'Analyze Image <i class="fa-solid fa-bolt"></i>';
        btn.disabled = false;
    }
}

// --- HOSPITAL REPORT MODAL FUNCTIONS ---

function openReportModal(data) {
    const modal = document.getElementById('report-modal');

    // Generate report ID
    const reportId = 'DMC-' + new Date().getFullYear() + '-' + Math.floor(Math.random() * 10000).toString().padStart(4, '0');

    // Set date
    const now = new Date();
    const dateStr = now.toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' });
    const timeStr = now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

    document.getElementById('report-id').textContent = reportId;
    document.getElementById('report-date').textContent = dateStr;
    document.getElementById('report-timestamp').textContent = `${dateStr} at ${timeStr}`;

    // Set patient info
    const userEmail = document.getElementById('user-email')?.textContent || 'Anonymous';
    document.getElementById('report-patient-id').textContent = userEmail.split('@')[0].toUpperCase();

    // Set diagnosis - Binary classification
    const diagnosisName = data.diagnosis; // "Benign" or "Malignant"
    document.getElementById('report-diagnosis-name').textContent = diagnosisName;

    // Determine diagnosis styling
    const isMalignant = diagnosisName.toLowerCase() === 'malignant';
    const diagnosisBadge = document.getElementById('report-diagnosis-badge');

    if (isMalignant) {
        diagnosisBadge.textContent = 'High Risk - Requires Urgent Evaluation';
        diagnosisBadge.className = 'diagnosis-badge malignant';

        // Show priority alert for malignant cases
        document.getElementById('rec-priority').style.display = 'flex';
        document.getElementById('rec-priority-text').innerHTML =
            '<strong>URGENT ATTENTION REQUIRED:</strong> This screening indicates a potentially malignant lesion. ' +
            'Please schedule an appointment with a dermatologist or oncologist within 48-72 hours for immediate evaluation and possible biopsy.';
    } else {
        diagnosisBadge.textContent = 'Low Risk - Standard Follow-up Recommended';
        diagnosisBadge.className = 'diagnosis-badge benign';

        // Hide priority alert for benign cases
        document.getElementById('rec-priority').style.display = 'none';
    }

    // Set medical analysis (from LLM report)
    const analysisDiv = document.getElementById('report-medical-analysis');
    // Format the report text with proper HTML
    const formattedReport = data.report
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>') // Bold text
        .replace(/\n\n/g, '</p><p>') // Paragraphs
        .replace(/\n/g, '<br>') // Line breaks
        .replace(/^\d+\.\s/gm, '<br><strong>$&</strong>'); // Number lists

    analysisDiv.innerHTML = '<p>' + formattedReport + '</p>';

    // Set heatmap if available
    if (data.heatmap_base64) {
        document.getElementById('report-heatmap').src = `data:image/png;base64,${data.heatmap_base64}`;
        document.getElementById('report-heatmap').style.display = 'block';
    } else {
        document.getElementById('report-heatmap').style.display = 'none';
    }

    // Show modal
    modal.style.display = 'flex';
}

function closeReportModal() {
    document.getElementById('report-modal').style.display = 'none';
}

function printReport() {
    window.print();
}

function viewReport(id) {
    // Always fetch from API to ensure we get the correct history item
    /*
    if (currentAnalysisData) {
        openReportModal(currentAnalysisData);
        return;
    }
    */

    // Otherwise fetch from API
    const token = localStorage.getItem('token');
    fetch(`${API_URL}/history/${id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
    })
        .then(res => res.json())
        .then(data => {
            openReportModal({
                diagnosis: data.diagnosis,
                report: data.report_text || 'Report data not available.',
                heatmap_base64: null
            });
        })
        .catch(err => {
            alert('Could not load report.');
        });
}

// --- FILE UPLOAD HANDLING ---

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('file-input');
    const dropZone = document.getElementById('drop-zone');
    const analyzeBtn = document.getElementById('analyze-btn');
    const previewContainer = document.getElementById('preview-container');
    const imagePreview = document.getElementById('image-preview');

    if (fileInput) {
        // Handle file selection
        fileInput.addEventListener('change', handleFileSelect);

        // Handle Drag & Drop
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, preventDefaults, false);
        });

        function preventDefaults(e) {
            e.preventDefault();
            e.stopPropagation();
        }

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, highlight, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, unhighlight, false);
        });

        function highlight(e) {
            dropZone.classList.add('highlight');
        }

        function unhighlight(e) {
            dropZone.classList.remove('highlight');
        }

        dropZone.addEventListener('drop', handleDrop, false);

        function handleDrop(e) {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                fileInput.files = files;
                handleFileSelect();
            }
        }
    }

    function handleFileSelect() {
        if (fileInput.files && fileInput.files[0]) {
            const reader = new FileReader();
            reader.onload = function (e) {
                imagePreview.src = e.target.result;
                previewContainer.classList.remove('hidden');
                dropZone.classList.add('hidden');
                analyzeBtn.disabled = false;
            }
            reader.readAsDataURL(fileInput.files[0]);
        }
    }
});

function clearImage() {
    document.getElementById('file-input').value = '';
    document.getElementById('preview-container').classList.add('hidden');
    document.getElementById('drop-zone').classList.remove('hidden');
    document.getElementById('analyze-btn').disabled = true;
    document.getElementById('result-container').classList.add('hidden');
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = 'index.html';
}
