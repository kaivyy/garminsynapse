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

    // Theme Toggle
    const themeToggle = document.getElementById('theme-toggle');
    const themeIconSun = document.getElementById('theme-icon-sun');
    const themeIconMoon = document.getElementById('theme-icon-moon');

    // Date Filter Controls
    const startDateInput = document.getElementById('start-date-input');
    const endDateInput = document.getElementById('end-date-input');
    const applyDateFilter = document.getElementById('apply-date-filter');
    const presetBtns = document.querySelectorAll('.preset-btn');

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

    let currentStartDate = '';
    let currentEndDate = '';

    // ============================================================
    // Theme Toggle Logic
    // ============================================================
    function getStoredTheme() {
        return localStorage.getItem('garminsynapse-theme') || 'dark';
    }
    function setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('garminsynapse-theme', theme);
        if (theme === 'dark') {
            themeIconSun.classList.remove('hidden');
            themeIconMoon.classList.add('hidden');
        } else {
            themeIconSun.classList.add('hidden');
            themeIconMoon.classList.remove('hidden');
        }
    }
    // Initialize theme
    setTheme(getStoredTheme());

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme');
            setTheme(current === 'dark' ? 'light' : 'dark');
        });
    }

    // ============================================================
    // Helper
    // ============================================================
    function formatDate(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    }

    // ============================================================
    // Auth Status Check
    // ============================================================
    async function checkAuthStatus() {
        try {
            const res = await fetch('/api/v1/status');
            if (res.ok) {
                const data = await res.json();
                if (data.authenticated) {
                    showDashboard();
                    setPreset('today');
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
        loadDeviceInfo();
    }

    async function loadDeviceInfo() {
        const modelElem = document.getElementById('device-model-name');
        const infoElem = document.getElementById('device-extra-info');
        const badgeElem = document.getElementById('device-status-badge');
        try {
            const devRes = await fetch('/api/v1/devices');
            if (devRes.ok) {
                const devData = await devRes.json();
                if (devData.devices && devData.devices.length > 0) {
                    const dev = devData.devices[0];
                    const devName = dev.productDisplayName || dev.displayName || dev.deviceCategory || 'Garmin Watch';
                    const serial = dev.serialNumber ? `SN: ${dev.serialNumber}` : '';
                    const unitId = dev.unitId ? `Unit ID: ${dev.unitId}` : '';
                    const fw = dev.currentFirmwareVersion ? `Firmware v${dev.currentFirmwareVersion}` : '';
                    const infoText = [serial, unitId, fw].filter(Boolean).join(' • ');
                    
                    if (modelElem) modelElem.textContent = devName;
                    if (infoElem) infoElem.textContent = infoText || 'Device Connected';
                    if (badgeElem) {
                        badgeElem.textContent = '● Connected';
                        badgeElem.style.background = 'rgba(16, 185, 129, 0.15)';
                        badgeElem.style.color = '#10b981';
                    }
                } else if (devData.primary && devData.primary.RegisteredDevices && devData.primary.RegisteredDevices.length > 0) {
                    const reg = devData.primary.RegisteredDevices[0];
                    const devName = reg.displayName || 'Garmin Watch';
                    const serial = reg.serialNumber ? `SN: ${reg.serialNumber}` : '';
                    const fw = reg.currentFirmwareVersion ? `Firmware v${reg.currentFirmwareVersion}` : '';
                    const infoText = [serial, fw].filter(Boolean).join(' • ');
                    if (modelElem) modelElem.textContent = devName;
                    if (infoElem) infoElem.textContent = infoText || 'Device Connected';
                    if (badgeElem) {
                        badgeElem.textContent = '● Connected';
                        badgeElem.style.background = 'rgba(16, 185, 129, 0.15)';
                        badgeElem.style.color = '#10b981';
                    }
                } else {
                    if (modelElem) modelElem.textContent = 'No Garmin Device Found';
                    if (infoElem) infoElem.textContent = 'No registered watch or tracker detected on this Garmin account.';
                    if (badgeElem) {
                        badgeElem.textContent = '○ Not Paired';
                        badgeElem.style.background = 'rgba(239, 68, 68, 0.15)';
                        badgeElem.style.color = '#ef4444';
                    }
                }
            }
        } catch (devErr) {
            console.warn('Could not load device info:', devErr);
        }
    }


    // ============================================================
    // Activity Detail Modal
    // ============================================================
    if (closeActModal) {
        closeActModal.addEventListener('click', () => {
            activityModal.classList.add('hidden');
        });
    }
    // Close modal on backdrop click
    if (activityModal) {
        activityModal.addEventListener('click', (e) => {
            if (e.target === activityModal) activityModal.classList.add('hidden');
        });
    }

    // ============================================================
    // Date Range Presets
    // ============================================================
    presetBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            presetBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            setPreset(btn.dataset.preset);
        });
    });

    function setPreset(presetKey) {
        const today = new Date();
        if (presetKey === 'today') {
            currentStartDate = formatDate(today);
            currentEndDate = formatDate(today);
        } else if (presetKey === '7days') {
            const past = new Date();
            past.setDate(today.getDate() - 7);
            currentStartDate = formatDate(past);
            currentEndDate = formatDate(today);
        } else if (presetKey === '30days') {
            const past = new Date();
            past.setDate(today.getDate() - 30);
            currentStartDate = formatDate(past);
            currentEndDate = formatDate(today);
        } else if (presetKey === 'all') {
            currentStartDate = '';
            currentEndDate = '';
        }

        startDateInput.value = currentStartDate;
        endDateInput.value = currentEndDate;
        loadDashboardData(currentStartDate, currentEndDate);
    }

    if (applyDateFilter) {
        applyDateFilter.addEventListener('click', () => {
            presetBtns.forEach(b => b.classList.remove('active'));
            currentStartDate = startDateInput.value;
            currentEndDate = endDateInput.value;
            loadDashboardData(currentStartDate, currentEndDate);
        });
    }

    // ============================================================
    // Login Form
    // ============================================================
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
                setPreset('today');
            } else {
                loginError.textContent = data.detail || 'Invalid email or password.';
                loginError.classList.remove('hidden');
            }
        } catch (err) {
            loginError.textContent = 'Connection error. Please try again.';
            loginError.classList.remove('hidden');
        } finally {
            loginBtnText.textContent = 'Authenticate & Sync';
            loginSpinner.classList.add('hidden');
        }
    });

    // ============================================================
    // Logout
    // ============================================================
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await fetch('/api/v1/auth/logout', { method: 'POST' });
            showLogin();
        });
    }

    // ============================================================
    // Dashboard Data Loader
    // ============================================================
    async function loadDashboardData(startDate = '', endDate = '') {
        try {
            let summaryUrl = '/api/v1/summary';
            let actUrl = '/api/v1/activities';
            
            const params = new URLSearchParams();
            if (startDate) params.append('start_date', startDate);
            if (endDate) params.append('end_date', endDate);
            
            if (params.toString()) {
                summaryUrl += `?${params.toString()}`;
                actUrl += `?${params.toString()}`;
            }

            // Fetch Connected Device Info
            try {
                const devRes = await fetch('/api/v1/devices');
                if (devRes.ok) {
                    const devData = await devRes.json();
                    const modelElem = document.getElementById('device-model-name');
                    const infoElem = document.getElementById('device-extra-info');
                    const badgeElem = document.getElementById('device-status-badge');
                    
                    if (devData.devices && devData.devices.length > 0) {
                        const dev = devData.devices[0];
                        const devName = dev.productDisplayName || dev.displayName || dev.deviceCategory || 'Garmin Watch';
                        const serial = dev.serialNumber ? `SN: ${dev.serialNumber}` : '';
                        const unitId = dev.unitId ? `Unit ID: ${dev.unitId}` : '';
                        const fw = dev.currentFirmwareVersion ? `Firmware v${dev.currentFirmwareVersion}` : '';
                        const infoText = [serial, unitId, fw].filter(Boolean).join(' • ');
                        
                        if (modelElem) modelElem.textContent = devName;
                        if (infoElem) infoElem.textContent = infoText || 'Device Connected';
                        if (badgeElem) {
                            badgeElem.textContent = '● Connected';
                            badgeElem.style.background = 'rgba(16, 185, 129, 0.15)';
                            badgeElem.style.color = '#10b981';
                        }
                    } else {
                        if (modelElem) modelElem.textContent = 'No Garmin Device Found';
                        if (infoElem) infoElem.textContent = 'No registered watch or tracker detected on this Garmin account.';
                        if (badgeElem) {
                            badgeElem.textContent = '○ Not Paired';
                            badgeElem.style.background = 'rgba(239, 68, 68, 0.15)';
                            badgeElem.style.color = '#ef4444';
                        }
                    }
                }
            } catch (devErr) {
                console.warn('Could not load device info:', devErr);
            }

            // Summary
            const summaryRes = await fetch(summaryUrl);
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
                let finalBB = summary.body_battery;
                // Stress Level
                let finalStress = summary.stress_level;
                let stressSuffix = '';

                // Fetch Live Metrics for Today if DB is empty/partial
                if (!startDate || startDate === formatDate(new Date())) {
                    try {
                        const liveRes = await fetch('/api/v1/live');
                        if (liveRes.ok) {
                            const liveData = await liveRes.json();
                            if (liveData.status === 'success') {
                                if (liveData.body_battery !== null && !finalBB) {
                                    finalBB = liveData.body_battery;
                                }
                                if (liveData.stress_level !== null && !finalStress) {
                                    finalStress = liveData.stress_level;
                                    if (liveData.stress_status) stressSuffix = ` (${liveData.stress_status})`;
                                }
                                if (liveData.steps && !stepsNum) {
                                    stepsVal.textContent = liveData.steps.toLocaleString();
                                }
                            }
                        }
                    } catch (liveErr) {
                        console.warn('Could not fetch live metrics:', liveErr);
                    }
                }

                batteryVal.innerHTML = finalBB !== null && finalBB !== undefined ? `${finalBB} <span class="unit">%</span>` : `-- <span class="unit">%</span>`;
                stressVal.innerHTML = finalStress !== null && finalStress !== undefined ? `${finalStress} <span class="unit">/ 100${stressSuffix}</span>` : `-- <span class="unit">/ 100</span>`;

                // HRV
                hrvVal.innerHTML = summary.hrv_status ? `${summary.hrv_status} <span class="unit">ms</span>` : `-- <span class="unit">ms</span>`;

                // Respiration Rate
                respVal.innerHTML = summary.respiration_rate ? `${summary.respiration_rate} <span class="unit">brpm</span>` : `-- <span class="unit">brpm</span>`;

                // SpO2
                spo2Val.innerHTML = summary.spo2 ? `${summary.spo2} <span class="unit">%</span>` : `-- <span class="unit">%</span>`;
            }


            // Activities
            const actRes = await fetch(actUrl);
            if (actRes.ok) {
                const activities = await actRes.json();
                activityCount.textContent = `${activities.length} workouts`;
                activityTableBody.innerHTML = '';

                if (activities.length === 0) {
                    activityTableBody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:40px; font-size:14px;">No device connected — No workouts logged for the selected range.</td></tr>`;
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

    // ============================================================
    // Activity Detail Modal Opener
    // ============================================================
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

    // ============================================================
    // Manual Sync
    // ============================================================
    if (syncBtn) {
        syncBtn.addEventListener('click', async () => {
            syncBtn.disabled = true;
            syncBtn.querySelector('span').textContent = 'Syncing...';
            try {
                await fetch('/api/v1/sync', { method: 'POST' });
                await loadDashboardData(currentStartDate, currentEndDate);
            } catch (err) {
                console.error('Sync failed:', err);
            } finally {
                syncBtn.disabled = false;
                syncBtn.querySelector('span').textContent = 'Sync';
            }
        });
    }

    // ============================================================
    // Init
    // ============================================================
    checkAuthStatus();
});
