document.addEventListener('DOMContentLoaded', () => {
    const loginModal = document.getElementById('login-modal');
    const activityModal = document.getElementById('activity-modal');
    const dashboardContainer = document.getElementById('dashboard-container');
    const loginForm = document.getElementById('login-form');
    const loginBtnText = document.getElementById('login-btn-text');
    const loginSpinner = document.getElementById('login-spinner');
    const loginError = document.getElementById('login-error');
    const logoutBtn = document.getElementById('logout-btn');
    const syncBtn = document.getElementById('sync-btn');
    const closeActModal = document.getElementById('close-act-modal');

    // Health Card Elements
    const stepsVal = document.getElementById('steps-value');
    const stepsBar = document.getElementById('steps-bar');
    const hrVal = document.getElementById('hr-value');
    const sleepScore = document.getElementById('sleep-score');
    const batteryVal = document.getElementById('battery-value');
    const hrvVal = document.getElementById('hrv-value');
    const stressVal = document.getElementById('stress-value');
    const respVal = document.getElementById('resp-value');
    const spo2Val = document.getElementById('spo2-value');

    const activityTableBody = document.getElementById('activity-table-body');
    const activityCount = document.getElementById('activity-count');

    // Modal elements
    const modalActName = document.getElementById('modal-act-name');
    const modalActType = document.getElementById('modal-act-type');
    const modalActTime = document.getElementById('modal-act-time');
    const modalActDuration = document.getElementById('modal-act-duration');
    const modalActDistance = document.getElementById('modal-act-distance');
    const modalActAvgHr = document.getElementById('modal-act-avghr');
    const modalActMaxHr = document.getElementById('modal-act-maxhr');
    const modalActCalories = document.getElementById('modal-act-calories');

    // Check System & Auth Status
    async function checkAuthStatus() {
        try {
            const res = await fetch('/api/v1/status');
            if (res.ok) {
                const data = await res.json();
                if (data.authenticated) {
                    showDashboard();
                    loadDashboardData();
                } else {
                    showLogin();
                }
            } else {
                showLogin();
            }
        } catch (err) {
            console.error('Failed to check status:', err);
            showLogin();
        }
    }

    function showLogin() {
        loginModal.classList.remove('hidden');
        dashboardContainer.classList.add('hidden');
    }

    function showDashboard() {
        loginModal.classList.add('hidden');
        dashboardContainer.classList.remove('hidden');
    }

    if (closeActModal) {
        closeActModal.addEventListener('click', () => {
            activityModal.classList.add('hidden');
        });
    }

    // Handle Login Form Submission
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value.trim();

        loginError.classList.add('hidden');
        loginBtnText.textContent = 'Authenticating...';
        loginSpinner.classList.remove('hidden');

        try {
            const res = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password })
            });

            const data = await res.json();

            if (res.ok && data.status === 'success') {
                showDashboard();
                loadDashboardData();
            } else {
                loginError.textContent = data.detail || 'Invalid email or password.';
                loginError.classList.remove('hidden');
            }
        } catch (err) {
            loginError.textContent = 'Connection error. Please try again.';
            loginError.classList.remove('hidden');
        } finally {
            loginBtnText.textContent = 'Authenticate & Extract Data';
            loginSpinner.classList.add('hidden');
        }
    });

    // Handle Logout
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await fetch('/api/v1/auth/logout', { method: 'POST' });
            showLogin();
        });
    }

    // Load Dashboard Real Data
    async function loadDashboardData() {
        try {
            // Summary
            const summaryRes = await fetch('/api/v1/summary');
            if (summaryRes.ok) {
                const summary = await summaryRes.json();
                
                // Steps
                const stepsNum = summary.steps || 0;
                stepsVal.textContent = stepsNum.toLocaleString();
                const pct = Math.min(100, Math.round((stepsNum / 10000) * 100));
                stepsBar.style.width = `${pct}%`;

                // Resting HR
                hrVal.innerHTML = summary.resting_hr ? `${summary.resting_hr} <span class="unit">bpm</span>` : `-- <span class="unit">bpm</span>`;

                // Sleep Score
                sleepScore.innerHTML = summary.sleep_score ? `${summary.sleep_score} <span class="unit">/ 100</span>` : `-- <span class="unit">/ 100</span>`;

                // Body Battery
                batteryVal.innerHTML = summary.body_battery ? `${summary.body_battery} <span class="unit">%</span>` : `-- <span class="unit">%</span>`;

                // HRV
                hrvVal.innerHTML = summary.hrv_status ? `${summary.hrv_status} <span class="unit">ms</span>` : `-- <span class="unit">ms</span>`;

                // Stress Level
                stressVal.innerHTML = summary.stress_level ? `${summary.stress_level} <span class="unit">/ 100</span>` : `-- <span class="unit">/ 100</span>`;

                // Respiration Rate
                respVal.innerHTML = summary.respiration_rate ? `${summary.respiration_rate} <span class="unit">brpm</span>` : `-- <span class="unit">brpm</span>`;

                // SpO2
                spo2Val.innerHTML = summary.spo2 ? `${summary.spo2} <span class="unit">%</span>` : `-- <span class="unit">%</span>`;
            }

            // Activities
            const actRes = await fetch('/api/v1/activities');
            if (actRes.ok) {
                const activities = await actRes.json();
                activityCount.textContent = `${activities.length} workouts logged`;
                activityTableBody.innerHTML = '';

                if (activities.length === 0) {
                    activityTableBody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:#94a3b8; padding:30px;">No device connected / No workouts logged yet.</td></tr>`;
                    return;
                }

                activities.forEach(act => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td style="font-weight:600;">${act.name || 'Workout'}</td>
                        <td><span class="badge">${act.type || 'Activity'}</span></td>
                        <td>${act.start_ts || '--'}</td>
                        <td>${act.duration || '--'}</td>
                        <td>${act.distance || '--'} km</td>
                        <td>${act.avg_hr || '--'} bpm</td>
                        <td>${act.calories || '--'} kcal</td>
                        <td><span class="green-text">✓ Synced</span></td>
                    `;
                    row.addEventListener('click', () => openActivityModal(act.id));
                    activityTableBody.appendChild(row);
                });
            }
        } catch (err) {
            console.error('Failed to fetch dashboard metrics:', err);
        }
    }

    async function openActivityModal(activityId) {
        try {
            const res = await fetch(`/api/v1/activity/${activityId}`);
            if (res.ok) {
                const data = await res.json();
                modalActName.textContent = data.name || 'Workout Details';
                modalActType.textContent = data.type || 'Activity';
                modalActTime.textContent = data.start_ts || '--';
                modalActDuration.textContent = data.duration_sec ? `${Math.round(data.duration_sec / 60)} minutes` : '--';
                modalActDistance.textContent = data.distance_m ? `${(data.distance_m / 1000).toFixed(2)} km` : '--';
                modalActAvgHr.textContent = data.avg_hr ? `${data.avg_hr} bpm` : '--';
                modalActMaxHr.textContent = data.max_hr ? `${data.max_hr} bpm` : '--';
                modalActCalories.textContent = data.calories ? `${data.calories} kcal` : '--';
                activityModal.classList.remove('hidden');
            }
        } catch (err) {
            console.error('Failed to load activity details:', err);
        }
    }

    // Handle Manual Sync Button
    if (syncBtn) {
        syncBtn.addEventListener('click', async () => {
            syncBtn.disabled = true;
            syncBtn.innerHTML = '🔄 Syncing...';
            try {
                await fetch('/api/v1/sync', { method: 'POST' });
                await loadDashboardData();
            } catch (err) {
                console.error('Sync failed:', err);
            } finally {
                syncBtn.disabled = false;
                syncBtn.innerHTML = '<span class="btn-icon">🔄</span> Sync';
            }
        });
    }

    // Check status on load
    checkAuthStatus();
});
