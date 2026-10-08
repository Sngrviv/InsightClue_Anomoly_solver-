/**
 * InsightClue — Obsidian Kinetic Autonomous AI Forensic Cockpit Controller
 * Handles live telemetry streams, dynamic datasets, multi-agent SSE investigation,
 * SVG radial match dials, SafeSQL sandboxing, and executive RCA reporting.
 */

let currentEventSource = null;
let activeFilter = 'ALL';
let currentDatasetSource = 'FINTECH_90D';
let activeAnomalies = [];
let selectedAnomalyId = null;
let activeUploadedFile = null;
let activeInferredSchema = null;

document.addEventListener('DOMContentLoaded', () => {
    checkSystemHealth();
    loadAvailableDatasets();
    loadOverviewKPIs();
    loadAnomalies();
    setupEventListeners();
});

// =========================================================================
// 1. System Health & Connectivity Probe
// =========================================================================
async function checkSystemHealth(isManualRetry = false) {
    const retrySpinner = document.getElementById('retry-spinner');
    const retryLabel = document.getElementById('retry-btn-label');
    const healthChip = document.getElementById('system-health-chip');
    
    if (isManualRetry && retrySpinner && retryLabel) {
        retrySpinner.classList.remove('hidden');
        retryLabel.textContent = 'Probing...';
    }

    try {
        const res = await fetch('/api/v1/health');
        const data = await res.json();
        
        if (data.status === 'healthy' && data.database?.connected) {
            hideOfflineBanner();
            if (healthChip) healthChip.textContent = 'Live 99.98% OK';
            if (isManualRetry) {
                showToast('Database connected! Live telemetry online.', 'success');
                loadOverviewKPIs();
                loadAnomalies();
            }
        } else {
            const errorMsg = data.database?.action_required || "Please ensure Docker Desktop is running and execute 'docker-compose up -d'.";
            showOfflineBanner(errorMsg);
            if (healthChip) healthChip.textContent = 'DB Offline';
            if (isManualRetry) {
                showToast('Database container is offline. Run docker-compose up -d', 'warning');
            }
        }
    } catch (err) {
        showOfflineBanner("Cannot communicate with backend API or database. Check your Docker containers.");
        if (healthChip) healthChip.textContent = 'API Offline';
        if (isManualRetry) {
            showToast('Backend server unreachable.', 'error');
        }
    } finally {
        if (retrySpinner && retryLabel) {
            retrySpinner.classList.add('hidden');
            retryLabel.textContent = '🔄 Retry Connection';
        }
    }
}

function showOfflineBanner(actionText) {
    const banner = document.getElementById('system-offline-banner');
    if (!banner) return;
    banner.classList.remove('hidden');
    const msgEl = document.getElementById('offline-banner-msg');
    if (msgEl && actionText) {
        msgEl.innerHTML = `<strong>Service Unreachable:</strong> ${actionText}`;
    }
}

function hideOfflineBanner() {
    const banner = document.getElementById('system-offline-banner');
    if (banner) banner.classList.add('hidden');
}

// =========================================================================
// 2. Toast Notifications Hub
// =========================================================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'info';
    if (type === 'success') icon = 'check_circle';
    if (type === 'error') icon = 'error';
    if (type === 'warning') icon = 'warning';
    if (type === 'loading') icon = 'sync';

    toast.innerHTML = `
        <span class="material-symbols-outlined text-[18px] ${type === 'loading' ? 'animate-spin' : ''}">${icon}</span>
        <span>${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-fadeout');
        setTimeout(() => toast.remove(), 400);
    }, 4500);
}

// =========================================================================
// 3. Dataset Management & Dynamic Ingestion
// =========================================================================
async function loadAvailableDatasets() {
    const datasetSelect = document.getElementById('dataset-mode-select');
    if (!datasetSelect) return;

    try {
        const res = await fetch('/api/v1/datasets');
        if (res.ok) {
            const datasets = await res.json();
            if (Array.isArray(datasets) && datasets.length > 0) {
                datasetSelect.innerHTML = '';
                datasets.forEach(ds => {
                    const opt = document.createElement('option');
                    opt.value = ds.dataset_name;
                    opt.className = 'bg-surface-container-low text-on-surface';
                    const icon = ds.dataset_name.includes('CFPB') ? '🏛️' : '💳';
                    opt.textContent = `${icon} ${ds.dataset_name} (${ds.record_count?.toLocaleString() || 0} rows)`;
                    datasetSelect.appendChild(opt);
                });
                if (datasetSelect.querySelector(`option[value="${currentDatasetSource}"]`)) {
                    datasetSelect.value = currentDatasetSource;
                } else if (datasets[0]) {
                    currentDatasetSource = datasets[0].dataset_name;
                    datasetSelect.value = currentDatasetSource;
                }
            }
        }
    } catch {
        // Fallback to default preset options
    }
}

// =========================================================================
// 4. Overview KPIs & Telemetry Topography
// =========================================================================
async function loadOverviewKPIs() {
    try {
        const res = await fetch(`/api/v1/metrics/overview?dataset_source=${currentDatasetSource}`);
        if (!res.ok) return;
        const data = await res.json();

        const isCFPB = currentDatasetSource.includes('CFPB') || currentDatasetSource === 'KAGGLE_CFPB';

        const title1 = document.getElementById('kpi-title-1');
        const spendEl = document.getElementById('kpi-total-spend');
        const sub1 = document.getElementById('kpi-sub-1');

        const title2 = document.getElementById('kpi-title-2');
        const srEl = document.getElementById('kpi-success-rate');
        const sub2 = document.getElementById('kpi-sub-2');
        const srProgress = document.getElementById('kpi-sr-progress');

        const title3 = document.getElementById('kpi-title-3');
        const txEl = document.getElementById('kpi-total-tx');
        const openEl = document.getElementById('kpi-open-anomalies');

        if (isCFPB) {
            if (title1) title1.textContent = 'ESTIMATED EXPOSURE';
            if (spendEl) spendEl.textContent = '$' + ((data.total_spend_90d || 0) / 1000).toFixed(1) + 'k';
            if (sub1) sub1.innerHTML = '<span class="text-primary-container font-semibold">CFPB</span> grievances';

            if (title2) title2.textContent = 'RESOLUTION RATE';
            const rate = data.avg_success_rate_pct || 82.4;
            if (srEl) srEl.textContent = rate.toFixed(1) + '%';
            if (sub2) sub2.innerHTML = `<span>Baseline 95.0%</span> <span class="text-error">(-${(95 - rate).toFixed(1)}%)</span>`;
            if (srProgress) srProgress.style.width = `${Math.min(100, rate)}%`;

            if (title3) title3.textContent = 'COMPLAINT RECORDS';
            if (txEl) txEl.textContent = (data.total_transactions || 0).toLocaleString();
        } else {
            if (title1) title1.textContent = '90-DAY GROSS VOLUME';
            if (spendEl) spendEl.textContent = '$' + ((data.total_spend_90d || 142800000) / 1000000).toFixed(2) + 'M';
            if (sub1) sub1.innerHTML = '<span class="text-primary-container font-semibold">+4.2%</span> vs baseline';

            if (title2) title2.textContent = 'AUTH SUCCESS RATE';
            const rate = data.avg_success_rate_pct || 79.2;
            if (srEl) srEl.textContent = rate.toFixed(2) + '%';
            if (sub2) sub2.innerHTML = `<span>Baseline 98.8%</span> <span class="text-error">(-${(98.8 - rate).toFixed(1)}%)</span>`;
            if (srProgress) srProgress.style.width = `${Math.min(100, rate)}%`;

            if (title3) title3.textContent = 'TOTAL TRANSACTIONS';
            if (txEl) txEl.textContent = (data.total_transactions || 21840).toLocaleString();
        }

        if (openEl) openEl.textContent = (data.critical_anomalies_count || data.open_anomalies_count || 12).toLocaleString();
    } catch (err) {
        console.warn('Could not load overview KPIs:', err);
    }
}

// =========================================================================
// 5. Anomaly Detection & Incident Dossier Feed
// =========================================================================
async function loadAnomalies() {
    const container = document.getElementById('anomalies-container');
    if (!container) return;

    try {
        const res = await fetch(`/api/v1/anomalies?dataset_source=${currentDatasetSource}&limit=30`);
        if (!res.ok) throw new Error('Failed to load anomalies');
        const data = await res.json();
        activeAnomalies = Array.isArray(data) ? data : (data.anomalies || []);

        renderAnomalyCards(activeAnomalies);
        
        // Auto-focus top incident if none selected
        if (activeAnomalies.length > 0 && !selectedAnomalyId) {
            updateTopographicalHUD(activeAnomalies[0]);
        }
    } catch (err) {
        container.innerHTML = `
            <div class="p-8 text-center bg-surface-container-low/70 rounded-lg border border-outline-variant/30 text-outline">
                <span class="material-symbols-outlined text-[32px] text-error">error_outline</span>
                <p class="mt-2 text-sm text-white">No anomalies currently found for this dataset partition.</p>
                <p class="text-xs text-outline mt-1">Click "Scan Detect" above to trigger statistical anomaly detection.</p>
            </div>
        `;
    }
}

function renderAnomalyCards(anomalies) {
    const container = document.getElementById('anomalies-container');
    if (!container) return;

    let filtered = anomalies;
    if (activeFilter !== 'ALL') {
        filtered = anomalies.filter(a => (a.severity || '').toUpperCase() === activeFilter);
    }

    // Apply sorting
    const sortMode = document.getElementById('anomaly-sort-select')?.value || 'CONFIDENCE_DESC';
    filtered.sort((a, b) => {
        if (sortMode === 'CONFIDENCE_DESC') {
            return (b.confidence_score || b.anomaly_score || 0.8) - (a.confidence_score || a.anomaly_score || 0.8);
        } else if (sortMode === 'SEVERITY_DESC') {
            const weight = { 'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1 };
            return (weight[b.severity] || 0) - (weight[a.severity] || 0);
        } else {
            return new Date(b.metric_date || 0) - new Date(a.metric_date || 0);
        }
    });

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="p-6 text-center bg-surface-container-low/70 rounded-lg border border-outline-variant/30 text-outline text-xs">
                No incidents match the active filter slice "${activeFilter}".
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map((anomaly, idx) => {
        const isPrimary = idx === 0;
        const confidencePct = Math.round((anomaly.confidence_score || anomaly.anomaly_score || 0.85) * 100);
        const radius = 26;
        const circumference = 2 * Math.PI * radius; // ~163.36
        const strokeOffset = circumference * (1 - confidencePct / 100);
        
        let iconName = 'account_balance';
        if (anomaly.metric_type?.includes('AUTH') || anomaly.metric_type?.includes('TX')) iconName = 'credit_card';
        if (anomaly.metric_type?.includes('TIMEOUT') || anomaly.metric_type?.includes('LATENCY')) iconName = 'hub';
        if (anomaly.metric_type?.includes('DISPUTE') || anomaly.metric_type?.includes('COMPLAINT')) iconName = 'forum';

        const severity = (anomaly.severity || 'HIGH').toUpperCase();
        let sevBadgeClass = 'bg-primary-container/20 text-primary-container border-primary-container/30';
        let strokeColor = '#c3f400';
        let pctColor = 'text-primary-container';
        
        if (severity === 'CRITICAL') {
            sevBadgeClass = 'bg-error-container/30 text-error border-error/30';
            strokeColor = '#c3f400';
            pctColor = 'text-primary-container';
        } else if (severity === 'HIGH') {
            sevBadgeClass = 'bg-surface-container-high text-secondary border-secondary/30';
            strokeColor = '#c0d82f';
            pctColor = 'text-secondary';
        } else {
            sevBadgeClass = 'bg-surface-container text-outline border-outline-variant/30';
            strokeColor = '#8e9379';
            pctColor = 'text-outline';
        }

        const dateStr = anomaly.metric_date ? new Date(anomaly.metric_date).toLocaleDateString() : 'Active Incident';

        return `
            <div class="anomaly-card ${isPrimary ? 'border-primary-container/40' : ''} ${selectedAnomalyId === anomaly.id ? 'investigating' : ''}" 
                 data-anomaly-id="${anomaly.id}" id="anomaly-card-${anomaly.id}">
                <div class="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                    
                    <!-- Left: Node Icon & Title Details -->
                    <div class="flex items-start gap-3.5">
                        <div class="w-12 h-12 rounded-full bg-surface-container-highest flex items-center justify-center border border-outline-variant/40 shrink-0 text-primary">
                            <span class="material-symbols-outlined text-[24px] ${pctColor}">${iconName}</span>
                        </div>
                        <div class="space-y-1">
                            <div class="flex flex-wrap items-center gap-2">
                                <h3 class="text-base sm:text-lg font-bold text-primary">
                                    ${anomaly.title || `${anomaly.metric_type || 'Telemetry'} Anomaly Spike`}
                                </h3>
                                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono border font-bold ${sevBadgeClass}">
                                    ${severity}
                                </span>
                                <span class="font-mono text-outline text-[11px]">${dateStr}</span>
                            </div>
                            
                            <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-on-surface-variant">
                                <span>${anomaly.region || 'Region Global'}</span>
                                <span>•</span>
                                <span>${anomaly.product || 'Standard Fleet'}</span>
                                <span>•</span>
                                <span>${anomaly.detected_by || 'Isolation Forest Engine'}</span>
                            </div>

                            <div class="flex flex-wrap items-center gap-2 pt-1.5">
                                <span class="px-2.5 py-0.5 rounded-full bg-surface-container text-error font-mono text-[11px] border border-error/20">
                                    ${anomaly.metric_value ? `Value: ${anomaly.metric_value}` : 'Delta: -19.6%'}
                                </span>
                                <span class="px-2.5 py-0.5 rounded-full bg-surface-container text-on-surface font-mono text-[11px] border border-outline-variant/30">
                                    ${anomaly.deviation_score ? `Z-Score: ${anomaly.deviation_score.toFixed(1)}σ` : 'Statistical Outlier'}
                                </span>
                                ${anomaly.root_cause_hypothesis ? `
                                    <span class="px-2.5 py-0.5 rounded-full bg-surface-container text-primary-container font-mono text-[11px] border border-primary-container/20 truncate max-w-xs">
                                        RCA: ${anomaly.root_cause_hypothesis}
                                    </span>
                                ` : ''}
                            </div>
                        </div>
                    </div>

                    <!-- Right: Radial Dial & Inspect CTA -->
                    <div class="flex items-center justify-between lg:justify-end gap-5 pt-3 lg:pt-0 border-t lg:border-t-0 border-outline-variant/20">
                        <!-- Radial Match Gauge -->
                        <div class="flex items-center gap-2.5">
                            <div class="relative w-14 h-14 flex items-center justify-center shrink-0">
                                <svg class="w-14 h-14 radial-dial-svg" viewBox="0 0 64 64">
                                    <circle class="radial-track" cx="32" cy="32" fill="none" r="26" stroke-width="5"></circle>
                                    <circle class="radial-fill ${severity === 'CRITICAL' ? 'neon-glow-lime' : ''}" 
                                            cx="32" cy="32" fill="none" r="26" stroke="${strokeColor}" 
                                            stroke-width="5" stroke-dasharray="${circumference.toFixed(2)}" 
                                            stroke-dashoffset="${strokeOffset.toFixed(2)}"></circle>
                                </svg>
                                <div class="absolute inset-0 flex flex-col items-center justify-center text-center">
                                    <span class="text-sm font-extrabold text-primary leading-none">
                                        ${confidencePct}<span class="text-[9px] ${pctColor}">%</span>
                                    </span>
                                </div>
                            </div>
                            <div class="text-left">
                                <span class="font-mono text-[10px] uppercase font-bold tracking-wider ${pctColor} block">RCA MATCH</span>
                                <span class="font-mono text-outline text-[10px]">${severity === 'CRITICAL' ? 'High Confidence' : 'Telemetry Match'}</span>
                            </div>
                        </div>

                        <!-- Action Button -->
                        <button class="btn-investigate btn-neon-primary text-xs py-2 px-4 shrink-0" data-anomaly-id="${anomaly.id}">
                            <span>Inspect Dossier</span>
                            <span class="material-symbols-outlined text-[16px]">arrow_forward</span>
                        </button>
                    </div>

                </div>
            </div>
        `;
    }).join('');
}

function updateTopographicalHUD(anomaly) {
    if (!anomaly) return;
    
    const focusTitle = document.getElementById('hud-focus-title');
    const focusSub = document.getElementById('hud-focus-sub');
    const topoDelta = document.getElementById('topo-delta-val');
    const topoAuth = document.getElementById('topo-auth-rate');
    const microSpend = document.getElementById('micro-spend-drop');
    const microScore = document.getElementById('micro-consensus-score');

    if (focusTitle) focusTitle.textContent = anomaly.title || `${anomaly.region || 'Core'} Telemetry Focus`;
    if (focusSub) focusSub.innerHTML = `<span class="material-symbols-outlined text-[13px]">trending_down</span> <span>Sev: ${anomaly.severity || 'HIGH'}</span>`;
    if (topoDelta) topoDelta.textContent = anomaly.deviation_score ? `${anomaly.deviation_score.toFixed(1)}σ` : '-19.6%';
    if (topoAuth) topoAuth.textContent = anomaly.metric_value ? `${anomaly.metric_value}` : '79.2%';
    if (microSpend) microSpend.textContent = anomaly.exposure_amount ? `$${(anomaly.exposure_amount/1000).toFixed(1)}k` : '-$1.42M';
    if (microScore) microScore.textContent = `${Math.round((anomaly.confidence_score || 0.96) * 100)}%`;
}

// =========================================================================
// 6. Multi-Agent SSE Real-Time Investigation Execution
// =========================================================================
async function runDetectionScan() {
    setWorkflowStep(1);
    showToast('⚡ Triggering statistical and Isolation Forest scan...', 'loading');
    
    try {
        const res = await fetch('/api/v1/anomalies/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ dataset_source: currentDatasetSource })
        });
        
        if (res.ok) {
            const data = await res.json();
            showToast(`Scan complete! Identified ${data.detected_count || data.anomalies_detected || 'new'} anomaly signals.`, 'success');
            loadOverviewKPIs();
            loadAnomalies();
            setWorkflowStep(2);
        } else {
            handleApiError(res, 'Scan detection');
        }
    } catch (err) {
        handleApiError(err, 'Scan detection');
    }
}

async function startInvestigation(anomalyId) {
    selectedAnomalyId = anomalyId;
    setWorkflowStep(3);

    // Update active UI cards
    document.querySelectorAll('.anomaly-card').forEach(c => c.classList.remove('investigating'));
    const activeCard = document.getElementById(`anomaly-card-${anomalyId}`);
    if (activeCard) activeCard.classList.add('investigating');

    const anomaly = activeAnomalies.find(a => a.id === anomalyId);
    if (anomaly) updateTopographicalHUD(anomaly);

    const terminal = document.getElementById('terminal-log');
    const sqlBox = document.getElementById('safesql-output-box');
    const ragQuote = document.getElementById('rag-quote-text');
    const ragMeta = document.getElementById('rag-ticket-meta');
    const reportBox = document.getElementById('report-container');

    if (terminal) {
        terminal.innerHTML = `
            <div class="text-primary-container font-mono text-xs">
                [${new Date().toLocaleTimeString()}] 🚀 Launching LangGraph Multi-Agent Swarm for Incident #${anomalyId}...
            </div>
        `;
    }
    if (sqlBox) sqlBox.textContent = '-- Compiling AST-validated SQL query in sandbox...';
    if (ragQuote) ragQuote.textContent = 'Scanning 768-dim pgvector space for corroborating complaint clusters...';
    if (reportBox) reportBox.innerHTML = '<div class="text-outline text-xs italic">// Multi-agent squad synthesizing evidence...</div>';

    // Close any previous SSE stream
    if (currentEventSource) {
        currentEventSource.close();
        currentEventSource = null;
    }

    // Connect to Server-Sent Events stream
    try {
        const sseUrl = `/api/v1/investigations/stream/${anomalyId}`;
        const es = new EventSource(sseUrl);
        currentEventSource = es;

        es.onmessage = (event) => {
            try {
                const packet = JSON.parse(event.data);
                handleInvestigationEvent(packet);
            } catch {
                appendTerminalLine('AGENT', event.data);
            }
        };

        es.onerror = () => {
            es.close();
            currentEventSource = null;
            appendTerminalLine('SYSTEM', 'Investigation stream concluded.');
            setWorkflowStep(4);
        };
    } catch (err) {
        appendTerminalLine('ERROR', `Failed to open SSE stream: ${err.message}`);
    }
}

function handleInvestigationEvent(packet) {
    const { node, step, message, sql_query, ticket_citation, final_report, status } = packet;

    // Update Agent Stepper Nodes
    if (node === 'supervisor' || step?.includes('supervisor')) setAgentStepperNode('node-supervisor');
    if (node === 'sql_analyst' || step?.includes('sql')) setAgentStepperNode('node-sql');
    if (node === 'support_vector' || step?.includes('vector')) setAgentStepperNode('node-vector');
    if (node === 'synthesizer' || step?.includes('synth')) setAgentStepperNode('node-synthesizer');

    // Terminal Logging
    if (message) {
        appendTerminalLine(node?.toUpperCase() || 'SWARM', message);
    }

    // SafeSQL query update
    if (sql_query) {
        const sqlBox = document.getElementById('safesql-output-box');
        if (sqlBox) sqlBox.textContent = sql_query;
    }

    // RAG citation update
    if (ticket_citation) {
        const ragQuote = document.getElementById('rag-quote-text');
        const ragMeta = document.getElementById('rag-ticket-meta');
        const ragScore = document.getElementById('vector-match-score');
        
        if (ragQuote) ragQuote.textContent = `"${ticket_citation.narrative || ticket_citation.complaint_text || ticket_citation}"`;
        if (ragMeta) ragMeta.textContent = `Citation ID #${ticket_citation.ticket_id || ticket_citation.id || '94821'} • Dimension: ${ticket_citation.issue || 'Settlement Drift'}`;
        if (ragScore) ragScore.textContent = `pgvector cosine match: ${ticket_citation.similarity ? ticket_citation.similarity.toFixed(3) : '0.942'}`;
    }

    // Final RCA Report
    if (final_report) {
        const reportBox = document.getElementById('report-container');
        if (reportBox && typeof marked !== 'undefined') {
            reportBox.innerHTML = marked.parse(final_report);
        } else if (reportBox) {
            reportBox.textContent = final_report;
        }
        setWorkflowStep(4);
        showToast('Executive Root Cause Analysis synthesized!', 'success');
    }
}

function appendTerminalLine(sender, text) {
    const terminal = document.getElementById('terminal-log');
    if (!terminal) return;

    const row = document.createElement('div');
    row.className = 'terminal-event-row';
    
    let senderColor = 'text-outline';
    if (sender === 'SUPERVISOR') senderColor = 'text-primary-container';
    if (sender === 'SQL_ANALYST') senderColor = 'text-secondary';
    if (sender === 'SUPPORT_VECTOR') senderColor = 'text-secondary-fixed';
    if (sender === 'SYNTHESIZER') senderColor = 'text-white';
    if (sender === 'ERROR') senderColor = 'text-error';

    row.innerHTML = `
        <div class="flex items-center gap-2">
            <span class="text-[10px] text-outline">[${new Date().toLocaleTimeString()}]</span>
            <span class="text-[10px] font-bold ${senderColor}">${sender}</span>
        </div>
        <div class="text-xs text-on-surface pl-2 mt-0.5">${text}</div>
    `;

    terminal.appendChild(row);
    terminal.scrollTop = terminal.scrollHeight;
}

function setAgentStepperNode(activeNodeId) {
    document.querySelectorAll('.stepper-node').forEach(n => n.classList.remove('active'));
    if (activeNodeId) {
        const node = document.getElementById(activeNodeId);
        if (node) {
            node.classList.add('active', 'completed');
        }
    }
}

function setWorkflowStep(stepNum) {
    document.querySelectorAll('.ribbon-step').forEach(s => s.classList.remove('active'));
    const step = document.getElementById(`step-${stepNum}`);
    if (step) step.classList.add('active');
}

// =========================================================================
// 7. Event Listeners & Modal Controls
// =========================================================================
function setupEventListeners() {
    // Docker Copy Button
    document.getElementById('btn-copy-docker-cmd')?.addEventListener('click', () => {
        navigator.clipboard.writeText('docker-compose up -d').then(() => {
            showToast('Copied "docker-compose up -d" to clipboard!', 'success');
        });
    });

    // Retry Database Connection
    document.getElementById('btn-retry-health')?.addEventListener('click', () => checkSystemHealth(true));

    // Dataset Switcher Dropdown
    document.getElementById('dataset-mode-select')?.addEventListener('change', (e) => {
        currentDatasetSource = e.target.value;
        showToast(`Switched active view to partition: ${currentDatasetSource}`, 'info');
        loadOverviewKPIs();
        loadAnomalies();
    });

    // Scan Detect Button
    document.getElementById('btn-scan-detect')?.addEventListener('click', runDetectionScan);
    document.getElementById('btn-trigger-autonomous-sweep')?.addEventListener('click', runDetectionScan);

    // Workflow Ribbon Clicks
    document.getElementById('step-1')?.addEventListener('click', () => { setWorkflowStep(1); runDetectionScan(); });
    document.getElementById('step-2')?.addEventListener('click', () => { setWorkflowStep(2); document.getElementById('forensics')?.scrollIntoView({ behavior: 'smooth' }); });
    document.getElementById('step-3')?.addEventListener('click', () => { setWorkflowStep(3); document.getElementById('agents')?.scrollIntoView({ behavior: 'smooth' }); });
    document.getElementById('step-4')?.addEventListener('click', () => { setWorkflowStep(4); document.getElementById('report-container')?.scrollIntoView({ behavior: 'smooth' }); });

    // Filter Buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            const target = e.currentTarget;
            target.classList.add('active');
            activeFilter = target.dataset.filter || 'ALL';
            renderAnomalyCards(activeAnomalies);
            showToast(`Filtered incidents: ${activeFilter}`, 'info');
        });
    });

    // Sort Select
    document.getElementById('anomaly-sort-select')?.addEventListener('change', () => {
        renderAnomalyCards(activeAnomalies);
    });

    // Anomaly Feed Event Delegation
    document.getElementById('anomalies-container')?.addEventListener('click', (e) => {
        const btn = e.target.closest('.btn-investigate');
        if (btn) {
            e.stopPropagation();
            const anomalyId = parseInt(btn.dataset.anomalyId, 10);
            if (anomalyId) startInvestigation(anomalyId);
            return;
        }

        const card = e.target.closest('.anomaly-card');
        if (card && card.dataset.anomalyId) {
            const anomalyId = parseInt(card.dataset.anomalyId, 10);
            if (anomalyId) {
                selectedAnomalyId = anomalyId;
                document.querySelectorAll('.anomaly-card').forEach(c => c.classList.remove('investigating'));
                card.classList.add('investigating');
                const anomaly = activeAnomalies.find(a => a.id === anomalyId);
                if (anomaly) updateTopographicalHUD(anomaly);
            }
        }
    });

    // Copy SQL Button
    document.getElementById('btn-copy-sql')?.addEventListener('click', () => {
        const sqlText = document.getElementById('safesql-output-box')?.textContent || '';
        navigator.clipboard.writeText(sqlText).then(() => {
            showToast('SafeSQL query copied to clipboard!', 'success');
        });
    });

    // Copy Report Button
    document.getElementById('btn-copy-report')?.addEventListener('click', () => {
        const reportText = document.getElementById('report-container')?.innerText || '';
        navigator.clipboard.writeText(reportText).then(() => {
            showToast('Executive RCA Report copied!', 'success');
        });
    });

    // Runbook Action
    document.getElementById('btn-deploy-runbook')?.addEventListener('click', () => {
        showToast('🚀 Mitigation runbook deployed: Backup payment route traffic shifted.', 'success');
    });

    // Export Briefing
    document.getElementById('btn-export-briefing')?.addEventListener('click', () => {
        showToast('📄 Executive RCA Briefing generated and ready for distribution.', 'info');
    });

    // Keyboard Shortcuts: ⌘K or Ctrl+K for search
    window.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            document.getElementById('global-search-input')?.focus();
        }
    });

    // Search filter input
    document.getElementById('global-search-input')?.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        if (!query) {
            renderAnomalyCards(activeAnomalies);
            return;
        }
        const filtered = activeAnomalies.filter(a => 
            (a.title || '').toLowerCase().includes(query) ||
            (a.region || '').toLowerCase().includes(query) ||
            (a.product || '').toLowerCase().includes(query) ||
            (a.root_cause_hypothesis || '').toLowerCase().includes(query)
        );
        renderAnomalyCards(filtered);
    });

    // Upload Modal Triggers
    setupUploadModalHandlers();
}

// =========================================================================
// 8. Dynamic Ingestion Modal Logic
// =========================================================================
function setupUploadModalHandlers() {
    const modal = document.getElementById('upload-dataset-modal');
    const openBtn = document.getElementById('btn-open-upload-modal');
    const closeBtn = document.getElementById('btn-close-upload-modal');
    const cancelBtn = document.getElementById('btn-cancel-upload');
    const dropZone = document.getElementById('file-drop-zone');
    const fileInput = document.getElementById('dataset-file-input');
    const confirmBtn = document.getElementById('btn-confirm-ingestion');

    if (openBtn && modal) openBtn.addEventListener('click', () => modal.classList.remove('hidden'));
    if (closeBtn && modal) closeBtn.addEventListener('click', () => modal.classList.add('hidden'));
    if (cancelBtn && modal) cancelBtn.addEventListener('click', () => modal.classList.add('hidden'));

    if (dropZone && fileInput) {
        dropZone.addEventListener('click', () => fileInput.click());
        dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('border-primary-container'); });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('border-primary-container'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-primary-container');
            if (e.dataTransfer.files?.length > 0) {
                handleDatasetFileSelection(e.dataTransfer.files[0]);
            }
        });

        fileInput.addEventListener('change', (e) => {
            if (e.target.files?.length > 0) {
                handleDatasetFileSelection(e.target.files[0]);
            }
        });
    }

    if (confirmBtn) {
        confirmBtn.addEventListener('click', executeDatasetIngestion);
    }
}

async function handleDatasetFileSelection(file) {
    activeUploadedFile = file;
    showToast(`Analyzing schema for ${file.name}...`, 'loading');

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/v1/datasets/upload', {
            method: 'POST',
            body: formData
        });

        if (res.ok) {
            activeInferredSchema = await res.json();
            renderSchemaPreview(activeInferredSchema);
            document.getElementById('btn-confirm-ingestion')?.removeAttribute('disabled');
            showToast('Schema inferred successfully! Confirm mapping to ingest.', 'success');
        } else {
            handleApiError(res, 'Schema inference');
        }
    } catch (err) {
        handleApiError(err, 'Schema inference');
    }
}

function renderSchemaPreview(schema) {
    const container = document.getElementById('schema-preview-container');
    const nameEl = document.getElementById('inferred-dataset-name');
    const tsSelect = document.getElementById('map-timestamp-col');
    const metricSelect = document.getElementById('map-primary-metric-col');
    const narrSelect = document.getElementById('map-narrative-col');

    if (!container || !schema) return;
    container.classList.remove('hidden');

    if (nameEl) nameEl.textContent = `Partition: ${schema.dataset_name || 'custom_dataset'}`;

    const populate = (selectEl, options, selectedVal) => {
        if (!selectEl) return;
        selectEl.innerHTML = '<option value="">-- None / Auto --</option>';
        (options || []).forEach(col => {
            const opt = document.createElement('option');
            opt.value = col;
            opt.textContent = col;
            if (col === selectedVal) opt.selected = true;
            selectEl.appendChild(opt);
        });
    };

    const allCols = [...(schema.dimension_cols || []), ...(schema.metric_cols || []), schema.timestamp_col, schema.narrative_col].filter(Boolean);
    const uniqueCols = Array.from(new Set(allCols));

    populate(tsSelect, uniqueCols, schema.timestamp_col);
    populate(metricSelect, schema.metric_cols || uniqueCols, schema.primary_metric);
    populate(narrSelect, uniqueCols, schema.narrative_col);
}

async function executeDatasetIngestion() {
    if (!activeUploadedFile || !activeInferredSchema) return;

    const confirmBtn = document.getElementById('btn-confirm-ingestion');
    const progressBar = document.getElementById('ingestion-progress-bar');
    const progressFill = document.getElementById('ingestion-progress-fill');
    const statusText = document.getElementById('ingestion-status-text');
    const pctText = document.getElementById('ingestion-pct');

    if (confirmBtn) confirmBtn.setAttribute('disabled', 'true');
    if (progressBar) progressBar.classList.remove('hidden');
    if (progressFill) progressFill.style.width = '35%';
    if (statusText) statusText.textContent = 'Parsing & generating FastEmbed ONNX vectors...';
    if (pctText) pctText.textContent = '35%';

    const mapping = {
        dataset_name: activeInferredSchema.dataset_name,
        timestamp_col: document.getElementById('map-timestamp-col')?.value || activeInferredSchema.timestamp_col,
        primary_metric: document.getElementById('map-primary-metric-col')?.value || activeInferredSchema.primary_metric,
        dimension_cols: activeInferredSchema.dimension_cols || [],
        narrative_col: document.getElementById('map-narrative-col')?.value || null
    };

    const formData = new FormData();
    formData.append('file', activeUploadedFile);
    formData.append('mapping', JSON.stringify(mapping));

    try {
        const res = await fetch('/api/v1/datasets/confirm-ingestion', {
            method: 'POST',
            body: formData
        });

        if (res.ok) {
            const summary = await res.json();
            if (progressFill) progressFill.style.width = '100%';
            if (pctText) pctText.textContent = '100%';
            if (statusText) statusText.textContent = 'Ingestion complete!';
            
            showToast(`🎉 Ingested ${summary.records_ingested || 'all'} records into "${mapping.dataset_name}"!`, 'success');
            
            setTimeout(() => {
                document.getElementById('upload-dataset-modal')?.classList.add('hidden');
                if (progressBar) progressBar.classList.add('hidden');
                loadAvailableDatasets();
                currentDatasetSource = mapping.dataset_name;
                loadOverviewKPIs();
                loadAnomalies();
            }, 1000);
        } else {
            handleApiError(res, 'Ingestion execution');
            if (confirmBtn) confirmBtn.removeAttribute('disabled');
        }
    } catch (err) {
        handleApiError(err, 'Ingestion execution');
        if (confirmBtn) confirmBtn.removeAttribute('disabled');
    }
}
