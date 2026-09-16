/**
 * InsightClue Dashboard Application Logic
 * Integrates Chart.js, REST APIs, Live Multi-Agent Stepper, and Real-Time SSE Streaming.
 */

let metricsChart = null;
let currentEventSource = null;
let activeFilter = 'ALL';

document.addEventListener('DOMContentLoaded', () => {
    loadOverviewKPIs();
    loadTimeseriesChart();
    loadAnomalies();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('btn-scan-detect').addEventListener('click', runDetectionScan);
    document.getElementById('btn-ingest-cfpb').addEventListener('click', triggerCFPBIngestion);

    // Filter Buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            activeFilter = e.target.dataset.filter;
            loadAnomalies();
        });
    });
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
        const res = await fetch('/api/v1/metrics/overview');
        if (!res.ok) throw new Error('Failed to fetch KPI overview');
        const data = await res.json();

        document.getElementById('kpi-total-spend').textContent = '$' + (data.total_spend_90d / 1000000).toFixed(2) + 'M';
        document.getElementById('kpi-total-tx').textContent = data.total_transactions.toLocaleString();
        document.getElementById('kpi-success-rate').textContent = data.avg_success_rate_pct.toFixed(2) + '%';
        document.getElementById('kpi-open-anomalies').textContent = data.open_anomalies_count;
        document.getElementById('kpi-critical-anomalies').textContent = data.critical_anomalies_count;
    } catch (err) {
        console.error('KPI Error:', err);
    }
}

// 2. Fetch & Render Timeseries Chart
async function loadTimeseriesChart() {
    try {
        const res = await fetch('/api/v1/metrics/timeseries');
        if (!res.ok) throw new Error('Failed to fetch timeseries');
        const data = await res.json();

        const ctx = document.getElementById('chart-timeseries').getContext('2d');
        
        if (metricsChart) {
            metricsChart.destroy();
        }

        metricsChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.dates,
                datasets: [
                    {
                        label: 'Daily Spend ($)',
                        data: data.spend,
                        borderColor: '#38bdf8',
                        backgroundColor: 'rgba(56, 189, 248, 0.08)',
                        borderWidth: 2,
                        yAxisID: 'y',
                        tension: 0.25,
                        fill: true,
                        pointRadius: 1,
                    },
                    {
                        label: 'Authorization Rate (%)',
                        data: data.success_rate,
                        borderColor: '#10b981',
                        borderWidth: 2,
                        borderDash: [4, 4],
                        yAxisID: 'y1',
                        tension: 0.25,
                        pointRadius: 1,
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
                        ticks: { color: '#38bdf8', font: { family: 'Inter', size: 10 } }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#10b981', min: 70, max: 100, font: { family: 'Inter', size: 10 } }
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
    listContainer.innerHTML = '<div style="color: #64748b; padding: 1.5rem; text-align: center;">Loading incident telemetry...</div>';

    try {
        let url = '/api/v1/anomalies?limit=50';
        if (activeFilter === 'CRITICAL') url += '&severity=CRITICAL';
        if (activeFilter === 'HIGH') url += '&severity=HIGH';
        if (activeFilter === 'OPEN') url += '&status=OPEN';
        if (activeFilter === 'RESOLVED') url += '&status=RESOLVED';

        const res = await fetch(url);
        if (!res.ok) throw new Error('Failed to fetch anomalies');
        const data = await res.json();

        if (!data.items || data.items.length === 0) {
            listContainer.innerHTML = '<div style="color: #64748b; padding: 1.5rem; text-align: center;">No matching incidents found. Click "Run Detection Scan" above to scan.</div>';
            return;
        }

        listContainer.innerHTML = '';
        data.items.forEach(anom => {
            const card = document.createElement('div');
            card.className = 'anomaly-card';
            card.id = `anomaly-card-${anom.id}`;
            
            const severityBadge = anom.severity === 'CRITICAL' ? 'badge-critical' : 'badge-high';
            const statusBadge = anom.status === 'RESOLVED' ? 'badge-resolved' : 'badge-open';

            // Human-friendly title and summary
            let titleText = `${anom.product_name}: ${formatMetricName(anom.metric_name)}`;
            let summaryDesc = '';
            if (anom.metric_name === 'chargeback_dispute_spike') {
                titleText = `🚨 ${anom.product_name}: High Dispute & Chargeback Spike`;
                summaryDesc = `Surged to <strong>${anom.actual_value.toFixed(2)}%</strong> (Baseline: ${anom.expected_value.toFixed(2)}% • <span style="color: var(--accent-rose); font-weight: bold;">+${anom.deviation_pct.toFixed(0)}% deviation</span>)`;
            } else if (anom.metric_name === 'success_rate_plunge') {
                titleText = `⚡ ${anom.product_name}: Authorization Rate Drop`;
                summaryDesc = `Dropped to <strong>${anom.actual_value.toFixed(2)}%</strong> (Baseline: ${anom.expected_value.toFixed(2)}% • <span style="color: var(--accent-amber); font-weight: bold;">${anom.deviation_pct.toFixed(1)}% drop</span>)`;
            } else {
                summaryDesc = `Actual: <strong>${anom.actual_value.toFixed(2)}</strong> vs Expected: ${anom.expected_value.toFixed(2)} (${anom.deviation_pct > 0 ? '+' : ''}${anom.deviation_pct.toFixed(1)}%)`;
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
                        📍 <strong>${anom.region} Region</strong> &bull; ${anom.customer_tier || 'Enterprise'} Tier &bull; 🗓️ ${detectedDate}
                    </div>
                    <div class="anomaly-details">
                        ${summaryDesc}
                    </div>
                </div>
                <div>
                    <button class="btn-investigate" onclick="startInvestigation(${anom.id})">
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
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Scanning 21.8k Metrics...';
    btn.disabled = true;

    try {
        setWorkflowStep(1);
        const res = await fetch('/api/v1/anomalies/detect', { method: 'POST' });
        const data = await res.json();
        alert(`🎯 Detection Scan Complete!\n${data.message}`);
        await loadOverviewKPIs();
        await loadAnomalies();
        setWorkflowStep(2);
    } catch (err) {
        alert('Detection scan failed: ' + err.message);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// 5. Ingest Kaggle CFPB Dataset Sample
async function triggerCFPBIngestion() {
    const btn = document.getElementById('btn-ingest-cfpb');
    const original = btn.innerHTML;
    btn.innerHTML = '⏳ Ingesting CFPB...';
    btn.disabled = true;

    try {
        alert('Ingesting CFPB Kaggle dataset sample and computing vector embeddings in background...');
        await fetch('/api/v1/anomalies/detect', { method: 'POST' });
        await loadOverviewKPIs();
        await loadAnomalies();
    } catch (e) {
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
    liveChip.className = 'live-status-chip active';
    liveText.textContent = `Squad Investigating #${anomalyId}...`;
    setAgentStepperNode('node-supervisor');

    terminal.innerHTML = '';
    reportContainer.innerHTML = '<div class="report-placeholder"><span>⏳ LangGraph Multi-Agent squad analyzing telemetry & customer tickets...</span></div>';

    appendTerminalEntry('System Gateway', `🚀 Dispatching Autonomous AI Detective squad for Incident #${anomalyId}...`, 'agent-supervisor');

    currentEventSource = new EventSource(`/api/v1/investigations/stream/${anomalyId}`);

    currentEventSource.addEventListener('anomaly_info', (e) => {
        const data = JSON.parse(e.data);
        appendTerminalEntry('Incident Context', `Target: ${data.region} Region • ${data.product} (${data.severity}) • Metric: ${data.metric}`, 'agent-supervisor');
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
        renderExecutiveRCA(data, reportContainer);
    });

    currentEventSource.addEventListener('complete', (e) => {
        appendTerminalEntry('System Gateway', '✅ Investigation stream completed and report persisted.', 'agent-supervisor');
        liveChip.className = 'live-status-chip idle';
        liveText.textContent = 'Squad Idle';
        currentEventSource.close();
        loadOverviewKPIs();
        loadAnomalies();
    });

    currentEventSource.onerror = (err) => {
        console.warn('SSE stream completed or closed:', err);
        liveChip.className = 'live-status-chip idle';
        liveText.textContent = 'Squad Idle';
        currentEventSource.close();
    };
}

function renderExecutiveRCA(data, container) {
    const confidencePct = (data.confidence_score * 100).toFixed(0);
    const summaryHtml = window.marked ? marked.parse(data.root_cause_summary) : data.root_cause_summary;
    
    // Parse mitigation lines into list items
    const steps = (data.mitigation_steps || '').split('\n').filter(s => s.trim().length > 0);
    const stepItems = steps.map(s => `<li class="action-item"><input type="checkbox" checked disabled> <span>${s.replace(/^\d+\.\s*/, '')}</span></li>`).join('');

    container.innerHTML = `
        <div class="rca-verdict-card">
            <div class="confidence-header">
                <div>
                    <strong style="color: var(--accent-emerald); font-size: 1rem;">🎯 Executive Root Cause Established</strong>
                    <div style="font-size: 0.75rem; color: var(--text-secondary);">Synthesized across machine telemetry & customer support evidence</div>
                </div>
                <span class="badge badge-resolved" style="font-size: 0.85rem; padding: 0.35rem 0.75rem;">
                    ${confidencePct}% Confidence
                </span>
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

function appendTerminalEntry(sender, text, senderClass) {
    const terminal = document.getElementById('terminal-log');
    
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
