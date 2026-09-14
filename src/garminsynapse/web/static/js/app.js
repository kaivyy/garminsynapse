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

    const themeToggle = document.getElementById('theme-toggle');
    const themeIconSun = document.getElementById('theme-icon-sun');
    const themeIconMoon = document.getElementById('theme-icon-moon');

    const startDateInput = document.getElementById('start-date-input');
    const endDateInput = document.getElementById('end-date-input');
    const applyDateFilter = document.getElementById('apply-date-filter');
    const presetBtns = document.querySelectorAll('.preset-btn');

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

    const modalActName = document.getElementById('modal-act-name');
    const modalActType = document.getElementById('modal-act-type');
    const modalActTime = document.getElementById('modal-act-time');
    const modalActDuration = document.getElementById('modal-act-duration');
    const modalActDistance = document.getElementById('modal-act-distance');
    const modalActAvgHr = document.getElementById('modal-act-avghr');
    const modalActMaxHr = document.getElementById('modal-act-maxhr');
    const modalActCalories = document.getElementById('modal-act-calories');

    const activityTypeSelect = document.getElementById('activity-type-select');
    const applyTypeBtn = document.getElementById('apply-type-btn');
    const typeChangeStatus = document.getElementById('type-change-status');
    const previewCorrectionsBtn = document.getElementById('preview-corrections-btn');
    const correctionsStatus = document.getElementById('corrections-status');
    const correctionsFindingsEl = document.getElementById('corrections-findings');
    const applyCorrectionsRow = document.getElementById('apply-corrections-row');
    const applyCorrectionsBtn = document.getElementById('apply-corrections-btn');

    let currentActivityId = null;
    let activityTypesCache = null;

    let currentStartDate = '';
    let currentEndDate = '';

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
    setTheme(getStoredTheme());

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const current = document.documentElement.getAttribute('data-theme');
            setTheme(current === 'dark' ? 'light' : 'dark');
        });
    }

    function formatDate(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    }

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

    function renderDeviceCard(devData) {
        const modelElem = document.getElementById('device-model-name');
        const primaryTagElem = document.getElementById('device-primary-tag');
        const snElem = document.getElementById('device-sn-val');
        const unitIdElem = document.getElementById('device-unitid-val');
        const fwElem = document.getElementById('device-fw-val');
        const skuElem = document.getElementById('device-sku-badge');
        const sensorElem = document.getElementById('device-sensor-val');
        const badgeElem = document.getElementById('device-status-badge');
        const statusTextElem = document.getElementById('device-status-text');
        const statusSubtextElem = document.getElementById('device-status-subtext');

        if (!devData) return;

        let dev = null;
        if (devData.devices && devData.devices.length > 0) {
            dev = devData.devices[0];
        } else if (devData.primary && devData.primary.RegisteredDevices && devData.primary.RegisteredDevices.length > 0) {
            dev = devData.primary.RegisteredDevices[0];
        }

        if (dev) {
            const devName = dev.productDisplayName || dev.displayName || dev.deviceCategory || 'Garmin Watch';
            function maskIdentifier(val, prefixLen = 4) {
                if (!val || val === 'N/A') return 'N/A';
                const str = String(val);
                if (str.length <= prefixLen) return '••••';
                return str.substring(0, prefixLen) + '•'.repeat(Math.max(4, str.length - prefixLen));
            }

            const rawSn = dev.serialNumber || 'N/A';
            const maskedSn = maskIdentifier(rawSn, 4);
            if (snElem) {
                snElem.textContent = maskedSn;
                snElem.title = 'Click to reveal / hide serial number';
                snElem.style.cursor = 'pointer';
                snElem.onclick = () => {
                    snElem.textContent = (snElem.textContent === maskedSn) ? rawSn : maskedSn;
                };
            }

            const rawUnitId = dev.unitId ? String(dev.unitId) : 'N/A';
            const maskedUnitId = maskIdentifier(rawUnitId, 4);
            if (unitIdElem) {
                unitIdElem.textContent = maskedUnitId;
                unitIdElem.title = 'Click to reveal / hide unit ID';
                unitIdElem.style.cursor = 'pointer';
                unitIdElem.onclick = () => {
                    unitIdElem.textContent = (unitIdElem.textContent === maskedUnitId) ? rawUnitId : maskedUnitId;
                };
            }
            if (fwElem) fwElem.textContent = dev.currentFirmwareVersion ? `v${dev.currentFirmwareVersion}` : 'N/A';
            if (skuElem && dev.actualProductSku) skuElem.textContent = `SKU ${dev.actualProductSku}`;
            if (sensorElem) sensorElem.textContent = 'Elevate™ Gen 4';

            const isPrimary = Boolean(dev.primaryActivityTrackerIndicator || dev.isPrimaryUser || dev.primaryTrainingCapable);
            if (primaryTagElem) {
                primaryTagElem.style.display = isPrimary ? 'inline-flex' : 'none';
            }

            if (badgeElem) {
                badgeElem.className = 'link-status-badge link-status-badge--connected';
            }
            if (statusTextElem) statusTextElem.textContent = 'Connected';
            if (statusSubtextElem) statusSubtextElem.textContent = 'Garmin Connect Active';
        } else {
            if (modelElem) modelElem.textContent = 'No Garmin Device Found';
            if (snElem) snElem.textContent = '--';
            if (unitIdElem) unitIdElem.textContent = '--';
            if (fwElem) fwElem.textContent = '--';
            if (skuElem) skuElem.textContent = 'SKU --';
            if (sensorElem) sensorElem.textContent = '--';
            if (primaryTagElem) primaryTagElem.style.display = 'none';
            if (badgeElem) {
                badgeElem.className = 'link-status-badge link-status-badge--disconnected';
            }
            if (statusTextElem) statusTextElem.textContent = 'Not Paired';
            if (statusSubtextElem) statusSubtextElem.textContent = 'No tracker detected';
        }
    }

    async function loadDeviceInfo() {
        try {
            const devRes = await fetch('/api/v1/devices');
            if (devRes.ok) {
                const devData = await devRes.json();
                renderDeviceCard(devData);
            }
        } catch (devErr) {
            console.warn('Could not load device info:', devErr);
        }
    }

    if (closeActModal) {
        closeActModal.addEventListener('click', () => {
            activityModal.classList.add('hidden');
        });
    }
    if (activityModal) {
        activityModal.addEventListener('click', (e) => {
            if (e.target === activityModal) activityModal.classList.add('hidden');
        });
    }

    function resetCorrectionsPanel() {
        correctionsStatus.textContent = '';
        correctionsFindingsEl.innerHTML = '';
        correctionsFindingsEl.classList.add('hidden');
        applyCorrectionsRow.classList.add('hidden');
        typeChangeStatus.textContent = '';
    }

    async function populateActivityTypeSelect(currentTypeKey) {
        try {
            if (!activityTypesCache) {
                const res = await fetch('/api/v1/activity-types');
                if (!res.ok) throw new Error('Failed to load activity types');
                const data = await res.json();
                activityTypesCache = data.types || [];
            }
            activityTypeSelect.innerHTML = '';
            activityTypesCache.forEach(t => {
                const opt = document.createElement('option');
                opt.value = t.typeKey;
                opt.textContent = t.typeKey;
                if (t.typeKey === currentTypeKey) opt.selected = true;
                activityTypeSelect.appendChild(opt);
            });
        } catch (err) {
            console.error('Failed to load activity types:', err);
            activityTypeSelect.innerHTML = '<option value="">(unavailable)</option>';
        }
    }

    if (applyTypeBtn) {
        applyTypeBtn.addEventListener('click', async () => {
            if (!currentActivityId) return;
            const typeKey = activityTypeSelect.value;
            if (!typeKey) return;
            typeChangeStatus.textContent = 'Saving…';
            try {
                const res = await fetch(`/api/v1/activity/${currentActivityId}/type`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type_key: typeKey })
                });
                if (res.ok) {
                    typeChangeStatus.textContent = '✅ Type updated.';
                    modalActType.textContent = typeKey;
                } else {
                    const err = await res.json().catch(() => ({}));
                    typeChangeStatus.textContent = `❌ ${err.detail || 'Failed to update type.'}`;
                }
            } catch (err) {
                typeChangeStatus.textContent = `❌ ${err.message}`;
            }
        });
    }

    let lastCorrectionsFindings = [];

    function renderFindings(findings) {
        correctionsFindingsEl.innerHTML = '';
        if (!findings || findings.length === 0) {
            correctionsFindingsEl.classList.add('hidden');
            applyCorrectionsRow.classList.add('hidden');
            correctionsStatus.textContent = '✅ No outliers detected.';
            return;
        }
        findings.forEach(f => {
            const li = document.createElement('li');
            li.textContent = `[${f.detector}] index ${f.index} (${f.field}): ${f.reason}`;
            correctionsFindingsEl.appendChild(li);
        });
        correctionsFindingsEl.classList.remove('hidden');
        applyCorrectionsRow.classList.remove('hidden');
        correctionsStatus.textContent = `⚠️ ${findings.length} outlier(s) found.`;
    }

    if (previewCorrectionsBtn) {
        previewCorrectionsBtn.addEventListener('click', async () => {
            if (!currentActivityId) return;
            correctionsStatus.textContent = 'Scanning…';
            correctionsFindingsEl.classList.add('hidden');
            applyCorrectionsRow.classList.add('hidden');
            try {
                const res = await fetch(`/api/v1/activity/${currentActivityId}/corrections/preview`);
                if (!res.ok) throw new Error('Preview request failed');
                const data = await res.json();
                lastCorrectionsFindings = data.findings || [];
                renderFindings(lastCorrectionsFindings);
            } catch (err) {
                correctionsStatus.textContent = `❌ ${err.message}`;
            }
        });
    }

    if (applyCorrectionsBtn) {
        applyCorrectionsBtn.addEventListener('click', async () => {
            if (!currentActivityId || lastCorrectionsFindings.length === 0) return;
            const confirmed = window.confirm(
                'This will DELETE the original activity and upload a corrected replacement ' +
                '(new activity ID; kudos/comments will be lost). The original FIT file is backed up ' +
                'locally first. Continue?'
            );
            if (!confirmed) return;
            correctionsStatus.textContent = 'Applying fix…';
            try {
                const res = await fetch(`/api/v1/activity/${currentActivityId}/corrections/apply`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ confirm: true })
                });
                const data = await res.json();
                if (res.ok && data.applied) {
                    correctionsStatus.textContent = `✅ Corrected activity uploaded. Backup saved to ${data.backup_path}.`;
                    applyCorrectionsRow.classList.add('hidden');
                } else {
                    correctionsStatus.textContent = `❌ ${data.detail || data.reason || 'Failed to apply corrections.'}`;
                }
            } catch (err) {
                correctionsStatus.textContent = `❌ ${err.message}`;
            }
        });
    }

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

    const passwordGroup = document.getElementById('password-group');
    const mfaGroup = document.getElementById('mfa-group');
    const passwordInput = document.getElementById('password');
    const mfaInput = document.getElementById('mfa-code');
    let awaitingMfa = false;
    let pendingEmail = null;

    function resetLoginForm() {
        awaitingMfa = false;
        pendingEmail = null;
        passwordGroup.classList.remove('hidden');
        mfaGroup.classList.add('hidden');
        passwordInput.value = '';
        mfaInput.value = '';
        loginBtnText.textContent = 'Authenticate & Sync';
    }

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const email = document.getElementById('email').value.trim();

        loginError.classList.add('hidden');
        loginSpinner.classList.remove('hidden');

        try {
            let body;
            if (awaitingMfa) {
                const mfaCode = mfaInput.value.trim();
                if (!mfaCode) {
                    loginError.textContent = 'Please enter the MFA code.';
                    loginError.classList.remove('hidden');
                    return;
                }
                loginBtnText.textContent = 'Verifying...';
                body = { email: pendingEmail, mfa_code: mfaCode };
            } else {
                const password = passwordInput.value.trim();
                if (!password) {
                    loginError.textContent = 'Please enter your password.';
                    loginError.classList.remove('hidden');
                    return;
                }
                loginBtnText.textContent = 'Authenticating...';
                body = { email, password };
            }

            const res = await fetch('/api/v1/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            const data = await res.json();

            if (res.ok && data.status === 'success') {
                resetLoginForm();
                showDashboard();
                setPreset('today');
            } else if (res.ok && data.status === 'mfa_required') {
                awaitingMfa = true;
                pendingEmail = email;
                passwordGroup.classList.add('hidden');
                mfaGroup.classList.remove('hidden');
                loginBtnText.textContent = 'Verify Code';
                mfaInput.focus();
            } else {
                loginError.textContent = data.detail || data.message || 'Invalid email or password.';
                loginError.classList.remove('hidden');
                loginBtnText.textContent = awaitingMfa ? 'Verify Code' : 'Authenticate & Sync';
            }
        } catch (err) {
            loginError.textContent = 'Connection error. Please try again.';
            loginError.classList.remove('hidden');
        } finally {
            loginSpinner.classList.add('hidden');
        }
    });

    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await fetch('/api/v1/auth/logout', { method: 'POST' });
            resetLoginForm();
            showLogin();
        });
    }

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

            await loadDeviceInfo();

            const summaryRes = await fetch(summaryUrl);
            if (summaryRes.ok) {
                const summary = await summaryRes.json();
                const isRange = summary.is_range || false;

                const stepsTitle = document.getElementById('steps-card-title');
                const stepsSubtext = document.getElementById('steps-subtext');
                const hrSubtext = document.getElementById('hr-subtext');
                const sleepSubtext = document.getElementById('sleep-subtext');
                const stressSubtext = document.getElementById('stress-subtext');
                const batterySubtext = document.getElementById('battery-subtext');

                const stepsNum = summary.steps || 0;
                stepsVal.textContent = stepsNum.toLocaleString();

                if (isRange) {
                    if (stepsTitle) stepsTitle.textContent = 'Total Steps';
                    if (stepsSubtext) {
                        const avg = summary.avg_steps ? summary.avg_steps.toLocaleString() : 0;
                        const dist = summary.total_distance_km ? `${summary.total_distance_km} km` : '';
                        stepsSubtext.textContent = `Avg ${avg} / day (${summary.days_count || 0} days)${dist ? ' • ' + dist : ''}`;
                    }
                    stepsBar.style.width = '100%';
                    if (hrSubtext) hrSubtext.textContent = `Avg Resting Heart Rate (${summary.days_count || 0} days)`;
                    if (sleepSubtext) sleepSubtext.textContent = `Avg Sleep Score (${summary.days_count || 0} days)`;
                    if (stressSubtext) stressSubtext.textContent = `Avg Stress (${summary.days_count || 0} days)`;
                    if (batterySubtext) batterySubtext.textContent = 'Avg Energy Reserve';
                } else {
                    if (stepsTitle) stepsTitle.textContent = 'Daily Steps';
                    if (stepsSubtext) stepsSubtext.textContent = 'Goal: 10,000 steps';
                    const pct = Math.min(100, Math.round((stepsNum / 10000) * 100));
                    stepsBar.style.width = `${pct}%`;
                    if (hrSubtext) hrSubtext.textContent = 'Resting Heart Rate';
                    if (sleepSubtext) sleepSubtext.textContent = 'Restorative Sleep';
                    if (stressSubtext) stressSubtext.textContent = 'Daily Stress Average';
                    if (batterySubtext) batterySubtext.textContent = 'Energy Reserve Level';
                }

                let finalHR = summary.resting_hr;
                hrVal.innerHTML = finalHR ? `${finalHR} <span class="unit">bpm</span>` : `-- <span class="unit">bpm</span>`;

                sleepScore.innerHTML = summary.sleep_score ? `${summary.sleep_score} <span class="unit">/ 100</span>` : `-- <span class="unit">/ 100</span>`;

                let finalBB = summary.body_battery;
                let finalStress = summary.stress_level;
                let stressSuffix = '';

                // Fetch live metrics for today if database records are empty.
                if (!startDate || startDate === formatDate(new Date())) {
                    try {
                        const liveRes = await fetch('/api/v1/live');
                        if (liveRes.ok) {
                            const liveData = await liveRes.json();
                            if (liveData.status === 'success') {
                                if (liveData.heart_rate !== null && liveData.heart_rate !== undefined && !finalHR) {
                                    finalHR = liveData.heart_rate;
                                    hrVal.innerHTML = `${finalHR} <span class="unit">bpm</span>`;
                                }
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
                                if (!summary.sleep_score) {
                                    if (liveData.sleep_score) {
                                        sleepScore.innerHTML = `${liveData.sleep_score} <span class="unit">/ 100</span>`;
                                    } else if (liveData.nap_duration_mins) {
                                        const h = Math.floor(liveData.nap_duration_mins / 60);
                                        const m = liveData.nap_duration_mins % 60;
                                        const napStr = (h > 0 ? `${h}h ` : '') + `${m}m`;
                                        sleepScore.innerHTML = `${napStr} <span class="unit">(Nap)</span>`;
                                    }
                                }
                            }
                        }
                    } catch (liveErr) {
                        console.warn('Could not fetch live metrics:', liveErr);
                    }
                }

                batteryVal.innerHTML = finalBB !== null && finalBB !== undefined ? `${finalBB} <span class="unit">%</span>` : `-- <span class="unit">%</span>`;
                stressVal.innerHTML = finalStress !== null && finalStress !== undefined ? `${finalStress} <span class="unit">/ 100${stressSuffix}</span>` : `-- <span class="unit">/ 100</span>`;

                hrvVal.innerHTML = summary.hrv_status ? `${summary.hrv_status} <span class="unit">ms</span>` : `-- <span class="unit">ms</span>`;

                respVal.innerHTML = summary.respiration_rate ? `${summary.respiration_rate} <span class="unit">brpm</span>` : `-- <span class="unit">brpm</span>`;

                const spo2Sub = document.getElementById('spo2-subtext');
                if (summary.spo2) {
                    spo2Val.innerHTML = `${summary.spo2} <span class="unit">%</span>`;
                    if (spo2Sub) spo2Sub.textContent = 'Blood Oxygen Saturation';
                } else {
                    spo2Val.innerHTML = `-- <span class="unit">%</span>`;
                    if (spo2Sub) spo2Sub.textContent = 'Sensor Off in Watch Settings';
                }

                try {
                    const readyUrl = (startDate && endDate && startDate === endDate)
                        ? `/api/v1/readiness?date=${startDate}`
                        : (endDate ? `/api/v1/readiness?date=${endDate}` : '/api/v1/readiness');
                    const readyRes = await fetch(readyUrl);
                    if (readyRes.ok) {
                        const readyData = await readyRes.json();
                        const readyVal = document.getElementById('readiness-value');
                        const readySub = document.getElementById('readiness-subtext');
                        if (readyData.status === 'success') {
                            const score = (readyData.score !== undefined && readyData.score !== null)
                                ? readyData.score
                                : (readyData.data ? (Array.isArray(readyData.data) ? readyData.data[0]?.score : readyData.data.score) : null);
                            if (score !== undefined && score !== null && readyVal) {
                                readyVal.innerHTML = `${score} <span class="unit">/ 100</span>`;
                            }
                            const feedback = readyData.feedback || (readyData.data ? (Array.isArray(readyData.data) ? readyData.data[0]?.feedbackShort : readyData.data.feedbackShort) : null);
                            if (feedback && readySub) {
                                readySub.textContent = String(feedback).replace(/_/g, ' ');
                            }
                        }
                    }
                } catch (readyErr) {
                    console.warn('Could not fetch training readiness:', readyErr);
                }
            }

            const actRes = await fetch(actUrl);
            if (actRes.ok) {
                const activities = await actRes.json();
                
                let totalDistKm = 0;
                let totalDurSec = 0;
                let totalCals = 0;
                activities.forEach(act => {
                    totalDistKm += parseFloat(act.distance) || 0;
                    totalDurSec += (act.duration_sec || 0);
                    totalCals += (act.calories || 0);
                });

                if (activities.length > 0) {
                    const durH = Math.floor(totalDurSec / 3600);
                    const durM = Math.floor((totalDurSec % 3600) / 60);
                    const durStr = durH > 0 ? `${durH}h ${durM}m` : `${durM}m`;
                    const distStr = totalDistKm > 0 ? ` • ${totalDistKm.toFixed(1)} km` : '';
                    const calsStr = totalCals > 0 ? ` • ${Math.round(totalCals).toLocaleString()} kcal` : '';
                    activityCount.textContent = `${activities.length} workouts${distStr} • ${durStr}${calsStr}`;
                } else {
                    activityCount.textContent = '0 workouts';
                }

                activityTableBody.innerHTML = '';

                if (activities.length === 0) {
                    activityTableBody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:40px; font-size:14px;">No device connected: no workouts logged for the selected range.</td></tr>`;
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
                        <td><span class="green-text">Synced</span></td>
                    `;
                    row.addEventListener('click', () => openActivityModal(act));
                    activityTableBody.appendChild(row);
                });
            }
        } catch (err) {
            console.error('Failed to fetch dashboard metrics:', err);
        }
    }

    async function openActivityModal(act) {
        try {
            currentActivityId = act.id;
            modalActName.textContent = act.name || 'Workout Details';
            modalActType.textContent = act.type || 'Activity';
            modalActTime.textContent = act.start_ts || '--';
            modalActDuration.textContent = act.duration ? `${act.duration}` : '--';
            modalActDistance.textContent = act.distance ? `${act.distance} km` : '--';
            modalActAvgHr.textContent = act.avg_hr ? `${act.avg_hr} bpm` : '--';
            modalActMaxHr.textContent = act.max_hr ? `${act.max_hr} bpm` : '--';
            modalActCalories.textContent = act.calories ? `${act.calories} kcal` : '--';
            activityModal.classList.remove('hidden');
            resetCorrectionsPanel();
            populateActivityTypeSelect(act.type);

            const splitsContainer = document.getElementById('splits-container');
            const splitsTableBody = document.getElementById('splits-table-body');
            splitsTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center;">Loading splits...</td></tr>';
            splitsContainer.style.display = 'block';

            const res = await fetch(`/api/v1/activities/${act.id}/splits`);
            if (res.ok) {
                const data = await res.json();
                splitsTableBody.innerHTML = '';
                
                if (data.splits && data.splits.length > 0) {
                    data.splits.forEach(split => {
                        const tr = document.createElement('tr');
                        const speed = split.averageSpeed ? (1000 / split.averageSpeed / 60) : 0; // pace in min/km
                        const paceMin = Math.floor(speed);
                        const paceSec = Math.round((speed - paceMin) * 60).toString().padStart(2, '0');
                        const paceStr = speed > 0 ? `${paceMin}:${paceSec} /km` : '--';
                        
                        let timeStr = '--';
                        if (split.duration) {
                            const tMin = Math.floor(split.duration / 60);
                            const tSec = Math.round(split.duration % 60).toString().padStart(2, '0');
                            timeStr = `${tMin}:${tSec}`;
                        }
                        
                        const distKm = split.distance ? (split.distance / 1000).toFixed(2) : '--';
                        const distStr = split.distance ? `${distKm} km` : '--';
                        const elevStr = split.elevationGain !== undefined && split.elevationGain !== null ? `+${Math.round(split.elevationGain)}m` : '--';
                        const cadenceStr = split.averageRunCadence ? `${Math.round(split.averageRunCadence)} spm` : '--';
                        const hrStr = split.averageHR ? `${Math.round(split.averageHR)} bpm` : '--';
                        const hrMaxStr = split.maxHR ? ` <span style="color:var(--text-muted);font-size:0.8em">(${Math.round(split.maxHR)})</span>` : '';

                        tr.innerHTML = `
                            <td style="font-weight:600;">${split.splitIndex || split.lapIndex || '-'}</td>
                            <td>${distStr}</td>
                            <td style="font-weight: 500;">${timeStr}</td>
                            <td>${paceStr}</td>
                            <td>${hrStr}${hrMaxStr}</td>
                            <td>${cadenceStr}</td>
                            <td>${elevStr}</td>
                        `;
                        splitsTableBody.appendChild(tr);
                    });
                } else {
                    splitsTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--text-secondary);">No splits/laps data available.</td></tr>';
                }
            } else {
                splitsTableBody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: var(--alert-color);">Failed to load splits.</td></tr>';
            }
        } catch (err) {
            console.error('Failed to load activity details:', err);
        }
    }

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

    checkAuthStatus();
});
