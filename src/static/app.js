/**
 * InsightClue Dashboard Application Logic
 * Integrates Chart.js timeseries, REST APIs, and real-time SSE streaming.
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
                        borderColor: '#06b6d4',
                        backgroundColor: 'rgba(6, 182, 212, 0.1)',
                        borderWidth: 2,
                        yAxisID: 'y',
                        tension: 0.2,
                        fill: true,
                        pointRadius: 1,
                    },
                    {
                        label: 'Success Rate (%)',
                        data: data.success_rate,
                        borderColor: '#10b981',
                        borderWidth: 2,
                        borderDash: [4, 4],
                        yAxisID: 'y1',
                        tension: 0.2,
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
                        labels: { color: '#94a3b8' }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(148, 163, 184, 0.1)' },
                        ticks: { color: '#64748b', maxTicksLimit: 12 }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: 'rgba(148, 163, 184, 0.1)' },
                        ticks: { color: '#06b6d4' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { color: '#10b981', min: 70, max: 100 }
                    }
                }
            }
        });
    } catch (err) {
        console.error('Chart Error:', err);
    }
}

// 3. Load Anomalies Feed
async function loadAnomalies() {
    const listContainer = document.getElementById('anomalies-container');
    listContainer.innerHTML = '<div style="color: #64748b; padding: 1rem;">Loading incident telemetry...</div>';

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
            listContainer.innerHTML = '<div style="color: #64748b; padding: 1rem;">No matching incidents found.</div>';
            return;
        }

        listContainer.innerHTML = '';
        data.items.forEach(anom => {
            const item = document.createElement('div');
            item.className = 'anomaly-item';
            
            const severityClass = anom.severity === 'CRITICAL' ? 'badge-critical' : 'badge-high';
            const statusClass = anom.status === 'RESOLVED' ? 'badge-resolved' : 'badge-open';

            item.innerHTML = `
                <div class="anomaly-meta">
                    <div class="anomaly-title">
                        <span>#${anom.id} ${anom.product_name}</span>
                        <span class="badge ${severityClass}">${anom.severity}</span>
                        <span class="badge ${statusClass}">${anom.status}</span>
                    </div>
                    <div class="anomaly-desc">
                        ${anom.region} &bull; ${anom.metric_name} &bull; 
                        Actual: <strong>${anom.actual_value.toFixed(2)}%</strong> (Expected: ${anom.expected_value.toFixed(2)}%, Dev: ${anom.deviation_pct.toFixed(1)}%)
                    </div>
                </div>
                <div>
                    <button class="btn btn-secondary" onclick="startInvestigation(${anom.id})">
                        🕵️ Investigate
                    </button>
                </div>
            `;
            listContainer.appendChild(item);
        });
    } catch (err) {
        listContainer.innerHTML = `<div style="color: #f43f5e; padding: 1rem;">Error: ${err.message}</div>`;
    }
}

// 4. Trigger On-Demand Detection Scan
async function runDetectionScan() {
    const btn = document.getElementById('btn-scan-detect');
    const originalText = btn.innerHTML;
    btn.innerHTML = '⏳ Scanning...';
    btn.disabled = true;

    try {
        const res = await fetch('/api/v1/anomalies/detect', { method: 'POST' });
        const data = await res.json();
        alert(`Detection Scan Complete!\n${data.message}`);
        await loadOverviewKPIs();
        await loadAnomalies();
    } catch (err) {
        alert('Detection scan failed: ' + err.message);
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

// 5. Start Live Multi-Agent Investigation Stream (SSE)
function startInvestigation(anomalyId) {
    const terminal = document.getElementById('terminal-log');
    const reportContainer = document.getElementById('report-container');
    
    // Close existing event source if open
    if (currentEventSource) {
        currentEventSource.close();
    }

    terminal.innerHTML = '';
    reportContainer.innerHTML = '<div style="color: #64748b; font-style: italic;">Investigation in progress... Waiting for multi-agent synthesis.</div>';

    // Append Initial Banner
    appendTerminalEntry('System Gateway', `Connecting to live multi-agent squad for Incident #${anomalyId}...`, 'agent-supervisor');

    currentEventSource = new EventSource(`/api/v1/investigations/stream/${anomalyId}`);

    currentEventSource.addEventListener('anomaly_info', (e) => {
        const data = JSON.parse(e.data);
        appendTerminalEntry('Incident Context', `Target: ${data.region} | ${data.product} | ${data.severity} (${data.metric})`, 'agent-supervisor');
    });

    currentEventSource.addEventListener('agent_thought', (e) => {
        const data = JSON.parse(e.data);
        let senderClass = 'agent-supervisor';
        if (data.agent.includes('SQL')) senderClass = 'agent-sql';
        else if (data.agent.includes('RAG') || data.agent.includes('Vector')) senderClass = 'agent-rag';
        else if (data.agent.includes('Synthesis') || data.agent.includes('RCA')) senderClass = 'agent-synthesis';

        appendTerminalEntry(data.agent, data.thought, senderClass);
    });

    currentEventSource.addEventListener('sql_evidence', (e) => {
        const data = JSON.parse(e.data);
        appendTerminalEntry('SQL Analytics Agent (Query Output)', `Executed query: ${data.query}\nMatched ${data.row_count} records. Summary: ${data.explanation}`, 'agent-sql');
    });

    currentEventSource.addEventListener('ticket_evidence', (e) => {
        const data = JSON.parse(e.data);
        appendTerminalEntry('Vector RAG Agent (Ticket Match)', `[Sim: ${data.similarity_score.toFixed(2)}] #${data.ticket_id}: "${data.complaint_text}"`, 'agent-rag');
    });

    currentEventSource.addEventListener('rca_report', (e) => {
        const data = JSON.parse(e.data);
        appendTerminalEntry('RCA Synthesis Agent', `Final Root Cause Analysis generated with ${(data.confidence_score * 100).toFixed(1)}% confidence.`, 'agent-synthesis');

        // Render Markdown Report
        if (window.marked) {
            reportContainer.innerHTML = marked.parse(`
### 🔍 Final Root Cause Analysis Verdict
**Confidence Score**: ${(data.confidence_score * 100).toFixed(1)}%

#### 📌 Root Cause Summary
${data.root_cause_summary}

#### 🛠️ Recommended Action Plan
${data.mitigation_steps}
            `);
        } else {
            reportContainer.textContent = JSON.stringify(data, null, 2);
        }
    });

    currentEventSource.addEventListener('complete', (e) => {
        appendTerminalEntry('System Gateway', 'Investigation stream completed successfully.', 'agent-supervisor');
        currentEventSource.close();
        loadOverviewKPIs();
        loadAnomalies();
    });

    currentEventSource.onerror = (err) => {
        console.warn('SSE stream closed or error:', err);
        currentEventSource.close();
    };
}

function appendTerminalEntry(sender, text, senderClass) {
    const terminal = document.getElementById('terminal-log');
    const entry = document.createElement('div');
    entry.className = 'terminal-entry';
    entry.innerHTML = `
        <div class="terminal-sender ${senderClass}">● [${sender}]</div>
        <div class="terminal-text">${text}</div>
    `;
    terminal.appendChild(entry);
    terminal.scrollTop = terminal.scrollHeight;
}
