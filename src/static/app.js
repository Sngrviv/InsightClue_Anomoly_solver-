/**
 * InsightClue Dashboard Application Logic
 * Supports Multi-Dataset Partitioning:
 * - FINTECH_90D: Synthetic 90-day FinTech transaction telemetry
 * - KAGGLE_CFPB: Real-world Kaggle Consumer Financial Protection Bureau complaint records
 */

let metricsChart = null;
let currentEventSource = null;
let activeFilter = 'ALL';
let currentDatasetSource = 'FINTECH_90D';

document.addEventListener('DOMContentLoaded', () => {
    loadOverviewKPIs();
    loadTimeseriesChart();
    loadAnomalies();
    setupEventListeners();
});

// Toast Notification Manager
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    if (type === 'error') icon = '❌';
    if (type === 'warning') icon = '⚠️';
    if (type === 'loading') icon = '⏳';

    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-msg">${message}</span>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('toast-fadeout');
        setTimeout(() => toast.remove(), 400);
    }, 4500);
}

function setupEventListeners() {
    // Dataset Mode Switcher
    const datasetSelect = document.getElementById('dataset-mode-select');
    if (datasetSelect) {
        datasetSelect.addEventListener('change', (e) => {
            currentDatasetSource = e.target.value;
            showToast(`Switched active view to: ${currentDatasetSource === 'KAGGLE_CFPB' ? '🏛️ CFPB Consumer Grievances' : '💳 90-Day FinTech Telemetry'}`, 'info');
            loadOverviewKPIs();
            loadTimeseriesChart();
            loadAnomalies();
        });
    }

    // Header Buttons
    const btnScan = document.getElementById('btn-scan-detect');
    if (btnScan) btnScan.addEventListener('click', runDetectionScan);

    const btnIngest = document.getElementById('btn-ingest-cfpb');
    if (btnIngest) btnIngest.addEventListener('click', triggerCFPBIngestion);

    // Interactive 4-Step Workflow Ribbon Navigation
    const step1 = document.getElementById('step-1');
    if (step1) {
        step1.addEventListener('click', () => {
            setWorkflowStep(1);
            runDetectionScan();
        });
    }

    const step2 = document.getElementById('step-2');
    if (step2) {
        step2.addEventListener('click', () => {
            setWorkflowStep(2);
            activeFilter = 'ALL';
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            const allBtn = document.querySelector('.filter-btn[data-filter="ALL"]');
            if (allBtn) allBtn.classList.add('active');
            loadAnomalies();
            document.getElementById('anomalies-container')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            showToast('Showing all detected anomalies in feed.', 'info');
        });
    }

    const step3 = document.getElementById('step-3');
    if (step3) {
        step3.addEventListener('click', () => {
            setWorkflowStep(3);
            document.getElementById('terminal-log')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
            showToast('Select an incident card from the feed or click "Investigate".', 'info');
        });
    }

    const step4 = document.getElementById('step-4');
    if (step4) {
        step4.addEventListener('click', () => {
            setWorkflowStep(4);
            document.getElementById('report-container')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
    }

    // Filter Buttons (using currentTarget for robust delegation)
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            const target = e.currentTarget;
            target.classList.add('active');
            activeFilter = target.dataset.filter || 'ALL';
            loadAnomalies();
            showToast(`Filtered incidents by: ${activeFilter}`, 'info');
        });
    });

    // Event Delegation on Anomaly Feed Container
    const feedContainer = document.getElementById('anomalies-container');
    if (feedContainer) {
        feedContainer.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-investigate');
            if (btn) {
                e.stopPropagation();
                const anomalyId = parseInt(btn.dataset.anomalyId, 10);
                if (anomalyId) {
                    startInvestigation(anomalyId);
                }
                return;
            }

            const card = e.target.closest('.anomaly-card');
            if (card && card.dataset.anomalyId) {
                const anomalyId = parseInt(card.dataset.anomalyId, 10);
                if (anomalyId) {
                    startInvestigation(anomalyId);
                }
            }
        });
    }
}

function setWorkflowStep(stepNumber) {
    document.querySelectorAll('.ribbon-step').forEach(s => s.classList.remove('active'));
    const current = document.getElementById(`step-${stepNumber}`);
    if (current) current.classList.add('active');
}

function setAgentStepperNode(activeNodeId) {
    document.querySelectorAll('.stepper-node').forEach(n => n.classList.remove('active'));
    if (activeNodeId) {
        const node = document.getElementById(activeNodeId);
        if (node) node.classList.add('active');
    }
}

// 1. Fetch Overview KPIs
async function loadOverviewKPIs() {
    try {
        const res = await fetch(`/api/v1/metrics/overview?dataset_source=${currentDatasetSource}`);
        if (!res.ok) throw new Error('Failed to fetch KPI overview');
        const data = await res.json();

        const isCFPB = currentDatasetSource === 'KAGGLE_CFPB';

        // Update KPI card text & labels dynamically
        const icon1 = document.getElementById('kpi-icon-1');
        const title1 = document.getElementById('kpi-title-1');
        const spendEl = document.getElementById('kpi-total-spend');
        const sub1 = document.getElementById('kpi-sub-1');

        const icon2 = document.getElementById('kpi-icon-2');
        const title2 = document.getElementById('kpi-title-2');
        const txEl = document.getElementById('kpi-total-tx');
        const sub2 = document.getElementById('kpi-sub-2');

        const icon3 = document.getElementById('kpi-icon-3');
        const title3 = document.getElementById('kpi-title-3');
        const srEl = document.getElementById('kpi-success-rate');
        const sub3 = document.getElementById('kpi-sub-3');

        const openEl = document.getElementById('kpi-open-anomalies');
        const critEl = document.getElementById('kpi-critical-anomalies');

        if (isCFPB) {
            if (icon1) icon1.textContent = '🏛️';
            if (title1) title1.textContent = 'Estimated Exposure';
            if (spendEl) spendEl.textContent = '$' + (data.total_spend_90d / 1000).toFixed(1) + 'k';
            if (sub1) sub1.textContent = 'Across 11 grievance categories';

            if (icon2) icon2.textContent = '🎫';
            if (title2) title2.textContent = 'CFPB Complaints Ingested';
            if (txEl) txEl.textContent = data.total_transactions.toLocaleString();
            if (sub2) sub2.textContent = 'Embedded in pgvector vector space';

            if (icon3) icon3.textContent = '⚖️';
            if (title3) title3.textContent = 'Non-Dispute Resolution Rate';
            if (srEl) srEl.textContent = data.avg_success_rate_pct.toFixed(1) + '%';
            if (sub3) sub3.textContent = 'Settled without consumer dispute';

            const chartTitle = document.getElementById('chart-panel-title');
            const chartSub = document.getElementById('chart-panel-subtitle');
            if (chartTitle) chartTitle.textContent = 'CFPB Daily Grievance Volume & Dispute Trends';
            if (chartSub) chartSub.textContent = 'Monitor consumer complaint surges and critical dispute escalations over time';
        } else {
            if (icon1) icon1.textContent = '💳';
            if (title1) title1.textContent = '90-Day Gross Volume';
            if (spendEl) spendEl.textContent = '$' + (data.total_spend_90d / 1000000).toFixed(2) + 'M';
            if (sub1) sub1.textContent = 'Across 4 regions & 5 products';

            if (icon2) icon2.textContent = '📊';
            if (title2) title2.textContent = 'Total Transactions';
            if (txEl) txEl.textContent = data.total_transactions.toLocaleString();
            if (sub2) sub2.textContent = '21,840 daily metric records';

            if (icon3) icon3.textContent = '✅';
            if (title3) title3.textContent = 'Avg Authorization Rate';
            if (srEl) srEl.textContent = data.avg_success_rate_pct.toFixed(2) + '%';
            if (sub3) sub3.textContent = 'Global baseline: 98.5%';

            const chartTitle = document.getElementById('chart-panel-title');
            const chartSub = document.getElementById('chart-panel-subtitle');
            if (chartTitle) chartTitle.textContent = '90-Day FinTech Spend & Authorization Trends';
            if (chartSub) chartSub.textContent = 'Monitor authorization rate dips and spend volume fluctuations';
        }

        if (openEl) openEl.textContent = data.open_anomalies_count;
        if (critEl) critEl.textContent = data.critical_anomalies_count;
    } catch (err) {
        console.error('KPI Error:', err);
    }
}

// 2. Fetch & Render Timeseries Chart
async function loadTimeseriesChart() {
    const canvas = document.getElementById('chart-timeseries');
    if (!canvas) return;

    try {
        const res = await fetch(`/api/v1/metrics/timeseries?dataset_source=${currentDatasetSource}`);
        if (!res.ok) throw new Error('Failed to fetch timeseries');
        const data = await res.json();

        const ctx = canvas.getContext('2d');
        
        if (metricsChart) {
            metricsChart.destroy();
        }

        const isCFPB = currentDatasetSource === 'KAGGLE_CFPB';
        const label1 = isCFPB ? 'Daily Grievance Count' : 'Daily Spend ($)';
        const color1 = isCFPB ? '#a855f7' : '#38bdf8';
        const bg1 = isCFPB ? 'rgba(168, 85, 247, 0.12)' : 'rgba(56, 189, 248, 0.08)';

        const label2 = isCFPB ? 'Dispute Escalation Rate (%)' : 'Authorization Rate (%)';
        const color2 = isCFPB ? '#f59e0b' : '#10b981';
        const data2 = isCFPB ? data.dispute_rate : data.success_rate;

        metricsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.dates,
                datasets: [
                    {
                        label: label1,
                        data: isCFPB ? data.transactions : data.spend,
                        borderColor: color1,
                        backgroundColor: bg1,
                        borderWidth: 2,
                        yAxisID: 'y',
                        tension: 0.25,
                        fill: true,
                        pointRadius: isCFPB ? 3 : 1,
                    },
                    {
                        label: label2,
                        data: data2,
                        borderColor: color2,
                        borderWidth: 2,
                        borderDash: [4, 4],
                        yAxisID: 'y1',
                        tension: 0.25,
                        pointRadius: isCFPB ? 3 : 1,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false,
                },
                plugins: {
                    legend: {
                        labels: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(148, 163, 184, 0.08)' },
                        ticks: { color: '#64748b', maxTicksLimit: 10, font: { family: 'Inter', size: 10 } }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: 'rgba(148, 163, 184, 0.08)' },
                        ticks: { color: color1, font: { family: 'Inter', size: 10 } }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { color: color2, font: { family: 'Inter', size: 10 } }
                    }
                }
            }
        });
    } catch (err) {
        console.error('Chart Error:', err);
    }
}

// 3. Load Anomalies Feed with Plain-English Human Titles
async function loadAnomalies() {
    const listContainer = document.getElementById('anomalies-container');
    if (!listContainer) return;

    listContainer.innerHTML = '<div style="color: #64748b; padding: 1.5rem; text-align: center;">Loading incident telemetry...</div>';

    try {
        let url = `/api/v1/anomalies?dataset_source=${currentDatasetSource}&limit=50`;
        if (activeFilter === 'CRITICAL') url += '&severity=CRITICAL';
        if (activeFilter === 'HIGH') url += '&severity=HIGH';
        if (activeFilter === 'OPEN') url += '&status=OPEN';
        if (activeFilter === 'RESOLVED') url += '&status=RESOLVED';

        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch anomalies');
        const data = await res.json();

        if (!data.items || data.items.length === 0) {
            listContainer.innerHTML = `<div style="color: #64748b; padding: 1.5rem; text-align: center;">No matching incidents found in ${currentDatasetSource === 'KAGGLE_CFPB' ? 'Kaggle CFPB Grievances' : 'FinTech Telemetry'}. Click "⚡ Run Detection Scan" above to scan.</div>`;
            return;
        }

        listContainer.innerHTML = '';
        data.items.forEach(anom => {
            const card = document.createElement('div');
            card.className = 'anomaly-card';
            card.id = `anomaly-card-${anom.id}`;
            card.dataset.anomalyId = anom.id;
            
            const severityBadge = anom.severity === 'CRITICAL' ? 'badge-critical' : 'badge-high';
            const statusBadge = anom.status === 'RESOLVED' ? 'badge-resolved' : 'badge-open';

            // Human-friendly title and summary
            let titleText = `${anom.product_name}: ${formatMetricName(anom.metric_name)}`;
            let summaryDesc = '';
            if (anom.metric_name === 'chargeback_dispute_spike') {
                titleText = `🚨 ${anom.product_name}: High Dispute Escalation Spike`;
                summaryDesc = `Surged to <strong>${anom.actual_value.toFixed(1)}%</strong> (Baseline: ${anom.expected_value.toFixed(1)}% • <span style="color: var(--accent-rose); font-weight: bold;">+${anom.deviation_pct.toFixed(0)}% deviation</span>)`;
            } else if (anom.metric_name === 'success_rate_plunge') {
                titleText = `⚡ ${anom.product_name}: Resolution Rate Drop`;
                summaryDesc = `Dropped to <strong>${anom.actual_value.toFixed(1)}%</strong> (Baseline: ${anom.expected_value.toFixed(1)}% • <span style="color: var(--accent-amber); font-weight: bold;">${anom.deviation_pct.toFixed(1)}% drop</span>)`;
            } else {
                summaryDesc = `Actual: <strong>${anom.actual_value.toFixed(1)}</strong> vs Expected: ${anom.expected_value.toFixed(1)} (${anom.deviation_pct > 0 ? '+' : ''}${anom.deviation_pct.toFixed(1)}%)`;
            }

            const detectedDate = new Date(anom.detected_at).toLocaleDateString();

            card.innerHTML = `
                <div class="anomaly-info">
                    <div class="anomaly-header">
                        <span class="anomaly-name">${titleText}</span>
                        <span class="badge ${severityBadge}">${anom.severity}</span>
                        <span class="badge ${statusBadge}">${anom.status}</span>
                    </div>
                    <div class="anomaly-details">
                        📍 <strong>${anom.region}</strong> &bull; ${anom.customer_tier || 'Retail'} Tier &bull; 🗓️ ${detectedDate}
                    </div>
                    <div class="anomaly-details">
                        ${summaryDesc}
                    </div>
                </div>
                <div>
                    <button class="btn-investigate" data-anomaly-id="${anom.id}">
                        🕵️ Investigate
                    </button>
                </div>
            `;
            listContainer.appendChild(card);
        });
    } catch (err) {
        listContainer.innerHTML = `<div style="color: #f43f5e; padding: 1rem;">Error: ${err.message}</div>`;
    }
}

function formatMetricName(metric) {
    if (!metric) return 'Anomaly Flag';
    return metric.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// 4. Trigger Detection Scan
async function runDetectionScan() {
    const btn = document.getElementById('btn-scan-detect');
    if (!btn) return;
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Scanning Telemetry...';
    btn.disabled = true;

    try {
        setWorkflowStep(1);
        showToast(`Running Statistical & Isolation Forest scan on ${currentDatasetSource}...`, 'loading');
        
        const res = await fetch(`/api/v1/anomalies/detect?dataset_source=${currentDatasetSource}`, { method: 'POST' });
        if (!res.ok) throw new Error(`Scan request failed (${res.status})`);
        const data = await res.json();
        
        showToast(`🎯 Scan Complete: ${data.new_anomalies_flagged} anomalies identified!`, 'success');
        await loadOverviewKPIs();
        await loadAnomalies();
        setWorkflowStep(2);
    } catch (err) {
        showToast('Detection scan failed: ' + err.message, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// 5. Ingest Kaggle CFPB Dataset Sample
async function triggerCFPBIngestion() {
    const btn = document.getElementById('btn-ingest-cfpb');
    if (!btn) return;
    const original = btn.innerHTML;
    btn.innerHTML = '⏳ Ingesting CFPB...';
    btn.disabled = true;

    try {
        showToast('Ingesting CFPB Kaggle complaints & generating vector embeddings...', 'loading');
        const res = await fetch('/api/v1/anomalies/ingest-cfpb?limit=250', { method: 'POST' });
        if (!res.ok) throw new Error(`Ingestion failed (${res.status})`);
        const data = await res.json();
        
        showToast(`📂 Ingestion Success: ${data.message}`, 'success');
        
        // Auto-switch to KAGGLE_CFPB mode
        currentDatasetSource = 'KAGGLE_CFPB';
        const select = document.getElementById('dataset-mode-select');
        if (select) select.value = 'KAGGLE_CFPB';

        await loadOverviewKPIs();
        await loadTimeseriesChart();
        await loadAnomalies();
    } catch (e) {
        showToast('CFPB Ingestion failed: ' + e.message, 'error');
        console.error(e);
    } finally {
        btn.innerHTML = original;
        btn.disabled = false;
    }
}

// 6. Start Live Multi-Agent Investigation Stream (SSE)
function startInvestigation(anomalyId) {
    setWorkflowStep(3);
    const terminal = document.getElementById('terminal-log');
    const reportContainer = document.getElementById('report-container');
    const liveChip = document.getElementById('live-indicator');
    const liveText = document.getElementById('live-status-text');
    
    // Highlight active card
    document.querySelectorAll('.anomaly-card').forEach(c => c.classList.remove('investigating'));
    const activeCard = document.getElementById(`anomaly-card-${anomalyId}`);
    if (activeCard) activeCard.classList.add('investigating');

    // Close previous stream
    if (currentEventSource) {
        currentEventSource.close();
    }

    // Set Live Status
    if (liveChip) liveChip.className = 'live-status-chip active';
    if (liveText) liveText.textContent = `Squad Investigating #${anomalyId}...`;
    setAgentStepperNode('node-supervisor');

    if (terminal) {
        terminal.innerHTML = '';
        terminal.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    if (reportContainer) {
        reportContainer.innerHTML = '<div class="report-placeholder"><span>⏳ LangGraph Multi-Agent squad analyzing telemetry & customer tickets...</span></div>';
    }

    appendTerminalEntry('System Gateway', `🚀 Dispatching Autonomous AI Detective squad for Incident #${anomalyId}...`, 'agent-supervisor');

    currentEventSource = new EventSource(`/api/v1/investigations/stream/${anomalyId}`);

    currentEventSource.addEventListener('anomaly_info', (e) => {
        const data = JSON.parse(e.data);
        appendTerminalEntry('Incident Context', `Target: ${data.region} • ${data.product} (${data.severity}) • Metric: ${data.metric}`, 'agent-supervisor');
    });

    currentEventSource.addEventListener('agent_thought', (e) => {
        const data = JSON.parse(e.data);
        let senderClass = 'agent-supervisor';
        let stepperNode = 'node-supervisor';

        if (data.agent.includes('SQL')) {
            senderClass = 'agent-sql';
            stepperNode = 'node-sql';
        } else if (data.agent.includes('RAG') || data.agent.includes('Vector')) {
            senderClass = 'agent-rag';
            stepperNode = 'node-rag';
        } else if (data.agent.includes('Synthesis') || data.agent.includes('RCA')) {
            senderClass = 'agent-synthesis';
            stepperNode = 'node-synthesis';
        }

        setAgentStepperNode(stepperNode);
        appendTerminalEntry(data.agent, data.thought, senderClass);
    });

    currentEventSource.addEventListener('sql_evidence', (e) => {
        const data = JSON.parse(e.data);
        setAgentStepperNode('node-sql');
        appendTerminalEntry('SQL Analytics Agent', `Executed Safe Sandbox Query:\n${data.query}\n📊 Results: Matched ${data.row_count} rows. ${data.explanation}`, 'agent-sql');
    });

    currentEventSource.addEventListener('ticket_evidence', (e) => {
        const data = JSON.parse(e.data);
        setAgentStepperNode('node-rag');
        appendTerminalEntry('Vector RAG Agent', `[pgvector Similarity: ${(data.similarity_score * 100).toFixed(0)}%] #${data.ticket_id}: "${data.complaint_text}"`, 'agent-rag');
    });

    currentEventSource.addEventListener('rca_report', (e) => {
        const data = JSON.parse(e.data);
        setAgentStepperNode('node-synthesis');
        setWorkflowStep(4);
        appendTerminalEntry('RCA Synthesis Agent', `Final Root Cause Analysis generated with ${(data.confidence_score * 100).toFixed(1)}% confidence.`, 'agent-synthesis');

        // Render Clean Executive RCA Card
        if (reportContainer) {
            renderExecutiveRCA(data, reportContainer);
        }
        showToast('🎯 Executive RCA verdict synthesized!', 'success');
    });

    currentEventSource.addEventListener('complete', (e) => {
        appendTerminalEntry('System Gateway', '✅ Investigation stream completed and report persisted.', 'agent-supervisor');
        if (liveChip) liveChip.className = 'live-status-chip idle';
        if (liveText) liveText.textContent = 'Squad Idle';
        currentEventSource.close();
        loadOverviewKPIs();
        loadAnomalies();
    });

    currentEventSource.onerror = (err) => {
        console.warn('SSE stream completed or closed:', err);
        if (liveChip) liveChip.className = 'live-status-chip idle';
        if (liveText) liveText.textContent = 'Squad Idle';
        currentEventSource.close();
    };
}

function renderExecutiveRCA(data, container) {
    const confidencePct = (data.confidence_score * 100).toFixed(0);
    const summaryHtml = window.marked ? marked.parse(data.root_cause_summary) : data.root_cause_summary;
    
    // Parse mitigation lines into list items
    const rawSteps = (data.mitigation_steps || '').split('\n').filter(s => s.trim().length > 0);
    const stepItems = rawSteps.map(s => `<li class="action-item"><input type="checkbox" checked disabled> <span>${s.replace(/^\d+\.\s*/, '')}</span></li>`).join('');

    container.innerHTML = `
        <div class="rca-verdict-card">
            <div class="confidence-header">
                <div>
                    <strong style="color: var(--accent-emerald); font-size: 1rem;">🎯 Executive Root Cause Established</strong>
                    <div style="font-size: 0.75rem; color: var(--text-secondary);">Synthesized across machine telemetry & customer support evidence</div>
                </div>
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <span class="badge badge-resolved" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">
                        ${confidencePct}% Confidence
                    </span>
                    <button class="btn btn-secondary btn-sm" id="btn-copy-rca" onclick="copyRCAPlan()">
                        📋 Copy Plan
                    </button>
                </div>
            </div>

            <div>
                <div class="rca-section-title">📌 Root Cause Narrative</div>
                <div style="color: #cbd5e1; font-size: 0.82rem; line-height: 1.5;">${summaryHtml}</div>
            </div>

            <div>
                <div class="rca-section-title">🛠️ Recommended Action Plan</div>
                <ul class="action-checklist">
                    ${stepItems || '<li class="action-item"><span>1. Failover to backup gateway switch.</span></li>'}
                </ul>
            </div>
        </div>
    `;
}

function copyRCAPlan() {
    const report = document.getElementById('report-container');
    if (!report) return;
    const text = report.innerText;
    navigator.clipboard.writeText(text).then(() => {
        showToast('📋 RCA action plan copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Could not copy to clipboard.', 'warning');
    });
}

function appendTerminalEntry(sender, text, senderClass) {
    const terminal = document.getElementById('terminal-log');
    if (!terminal) return;
    
    // Remove placeholder if present
    const placeholder = terminal.querySelector('.terminal-placeholder');
    if (placeholder) placeholder.remove();

    const entry = document.createElement('div');
    entry.className = 'terminal-entry';
    entry.innerHTML = `
        <div class="terminal-sender ${senderClass}">● [${sender}]</div>
        <div class="terminal-text">${text}</div>
    `;
    terminal.appendChild(entry);
    terminal.scrollTop = terminal.scrollHeight;
}

// Global scope bindings
window.startInvestigation = startInvestigation;
window.runDetectionScan = runDetectionScan;
window.triggerCFPBIngestion = triggerCFPBIngestion;
window.copyRCAPlan = copyRCAPlan;
window.showToast = showToast;
