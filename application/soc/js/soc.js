/*
 * Cyber Hazard Lab - Security Operations Center
 * Core State & Polling Loop
 */

window.SOC = {
    state: {
        rules: [],
        alerts: [],
        incidents: [],
        hosts: {},
        telemetry: {}
    },
    metrics: {
        total_events: 0,
        last_event_time: null,
        history: []
    },
    pollInterval: null
};

async function apiRequest(method, endpoint, body = null) {
    const options = {
        method: method,
        headers: { "Content-Type": "application/json" }
    };
    if (body) {
        options.body = JSON.stringify(body);
    }
    const response = await fetch(endpoint, options);
    if (!response.ok) {
        console.error(`API Error: ${method} ${endpoint} - ${response.statusText}`);
        return null;
    }
    return await response.json();
}

async function loadSOCState() {
    const data = await apiRequest("GET", "/api/soc/state");
    if (data && !data.error) {
        if (data.rules) window.SOC.state.rules = data.rules;
        if (data.alerts) window.SOC.state.alerts = data.alerts;
        if (data.incidents) window.SOC.state.incidents = data.incidents;
    }
}

async function saveSOCState() {
    await apiRequest("POST", "/api/soc/state", {
        rules: window.SOC.state.rules,
        alerts: window.SOC.state.alerts,
        incidents: window.SOC.state.incidents
    });
}

function updateOverviewMetrics(events, telemetry, devices) {
    // Hosts
    let totalHosts = 0;
    let onlineHosts = 0;
    if (devices && Array.isArray(devices)) { 
        // /api/ntm/devices returns a list
        const devs = devices;
        totalHosts = devs.length;
        onlineHosts = devs.filter(d => d.status === "ONLINE").length;
    }

    const hostTotalEl = document.getElementById("metric-hosts-total");
    const hostOnlineEl = document.getElementById("metric-hosts-online");
    if (hostTotalEl) hostTotalEl.textContent = totalHosts;
    if (hostOnlineEl) hostOnlineEl.textContent = `${onlineHosts} ONLINE`;

    // Events
    window.SOC.metrics.total_events = events.length;
    const evtTotalEl = document.getElementById("metric-events-total");
    if (evtTotalEl) evtTotalEl.textContent = window.SOC.metrics.total_events;

    window.SOC.metrics.history.push({ time: Date.now(), count: events.length });
    if (window.SOC.metrics.history.length > 5) window.SOC.metrics.history.shift();

    let rate = 0;
    if (window.SOC.metrics.history.length > 1) {
        const first = window.SOC.metrics.history[0];
        const last = window.SOC.metrics.history[window.SOC.metrics.history.length - 1];
        const timeDiffMins = (last.time - first.time) / 60000;
        const countDiff = last.count - first.count;
        if (timeDiffMins > 0) {
            rate = countDiff / timeDiffMins;
        }
    }
    const evtRateEl = document.getElementById("metric-events-rate");
    if (evtRateEl) evtRateEl.textContent = `+${rate.toFixed(2)} / MIN`;

    // Alerts
    const totalAlerts = window.SOC.state.alerts.length;
    const criticalAlerts = window.SOC.state.alerts.filter(a => a.severity === "CRITICAL").length;
    
    const alertTotalEl = document.getElementById("metric-alerts-total");
    const alertCritEl = document.getElementById("metric-alerts-critical");
    if (alertTotalEl) alertTotalEl.textContent = totalAlerts;
    if (alertCritEl) alertCritEl.textContent = `${criticalAlerts} CRITICAL`;
    
    // Clear network linear graph placeholder for now
    
    // Render Network Activity Mini-Map based on recent events
    const nwPlaceholder = document.querySelector(".network-placeholder");
    if (nwPlaceholder) {
        // Collect latest 3 unique source->destination paths
        const paths = [];
        const seen = new Set();
        
        for (let i = events.length - 1; i >= 0 && paths.length < 9; i--) {
            const e = events[i];
            if (e.source === "SYSTEM" || e.destination === "SYSTEM" || e.source === "API") continue;
            if (e.protocol === "ETHERNET") continue; // Exclude pure MAC frames
            const key = e.source + "->" + e.destination;
            if (!seen.has(key)) {
                seen.add(key);
                paths.push(e);
            }
        }
        
        if (paths.length === 0) {
            nwPlaceholder.innerHTML = '<div style="color: #666; text-align: center; padding: 2rem;">Awaiting Network Traffic...</div>';
        } else {
            nwPlaceholder.innerHTML = '<div style="display: flex; flex-wrap: wrap; gap: 1.5rem; padding: 1rem; justify-content: center;">' + paths.map(p => {
                const isAlert = (p.severity === 'HIGH' || p.severity === 'CRITICAL');
                const nodeColor = isAlert ? '#ef4444' : '#3b82f6';
                const linkColor = isAlert ? '#ef4444' : '#1e293b';
                
                return `
                <div style="display: flex; align-items: center; justify-content: center; gap: 1rem;">
                    <div style="background: rgba(15,23,42,0.8); border: 1px solid ${nodeColor}; padding: 0.5rem 1rem; border-radius: 4px; color: white;">${p.source}</div>
                    <div style="width: 100px; height: 2px; background: ${linkColor}; position: relative; margin: 0 0.5rem;">
                        <div style="position: absolute; top: -18px; left: 50%; transform: translateX(-50%); font-size: 0.75rem; color: #8b9bb4; background: #0f172a; padding: 0 4px; white-space: nowrap;">${p.protocol || 'SYS'}</div>
                    </div>
                    <div style="background: rgba(15,23,42,0.8); border: 1px solid ${nodeColor}; padding: 0.5rem 1rem; border-radius: 4px; color: white;">${p.destination}</div>
                </div>
                `;
            }).join('') + '</div>';
        }
    }

    
    // Render Activity Feed (Last 15 events)
    renderActivityFeed(events.slice(-15).reverse());
}

function renderActivityFeed(recentEvents) {
    const list = document.getElementById("activity-list");
    if (!list) return;
    
    list.innerHTML = "";
    recentEvents.forEach(e => {
        const row = document.createElement("div");
        row.className = "activity-row";
        if (e.severity === "HIGH" || e.severity === "CRITICAL" || e.severity === "WARNING") {
            row.classList.add("alert-row");
        }
        
        const time = new Date(e.timestamp).toLocaleTimeString();
        
        // Remember exact schema:
        row.innerHTML = `
            <span class="activity-time">${time}</span>
            <span class="activity-type">${(e.protocol || e.type).replace(/_/g, " ")}</span>
            <span class="activity-message">${e.type.replace(/_/g, " ")}: ${e.source} &rarr; ${e.destination}</span>
        `;
        list.appendChild(row);
    });
}


function renderRules() {
    const list = document.getElementById("rules-list");
    if (!list) return;
    
    list.innerHTML = "";
    if (window.SOC.state.rules.length === 0) {
        list.innerHTML = '<div style="color: #666; font-style: italic;">No rules defined.</div>';
        return;
    }
    
    window.SOC.state.rules.forEach((rule, idx) => {
        const item = document.createElement("div");
        item.style = "background: rgba(15,23,42,0.8); padding: 0.75rem; margin-bottom: 0.5rem; border-left: 3px solid " + (rule.severity === 'CRITICAL' ? '#ef4444' : '#3b82f6') + "; display: flex; justify-content: space-between;";
        item.innerHTML = `
            <div>
                <strong style="color: white;">${rule.name}</strong> <span style="font-size: 0.8rem; color: #8b9bb4;">[${rule.severity}]</span><br>
                <code style="font-size: 0.8rem; color: #10b981;">${rule.condition}</code>
            </div>
            <button onclick="deleteRule(${idx})" style="background: transparent; border: 1px solid #ef4444; color: #ef4444; padding: 0.2rem 0.5rem; cursor: pointer;">DELETE</button>
        `;
        list.appendChild(item);
    });
}

window.deleteRule = async function(idx) {
    window.SOC.state.rules.splice(idx, 1);
    await saveSOCState();
    renderRules();
};

document.addEventListener("DOMContentLoaded", () => {
    const btnAddRule = document.getElementById("btn-add-rule");
    if (btnAddRule) {
        btnAddRule.addEventListener("click", async () => {
            const name = document.getElementById("rule-name").value;
            const severity = document.getElementById("rule-severity").value;
            const condition = document.getElementById("rule-condition").value;
            
            if (!name || !condition) {
                alert("Name and Condition are required.");
                return;
            }
            
            window.SOC.state.rules.push({
                id: Date.now().toString(),
                name,
                severity,
                condition
            });
            
            document.getElementById("rule-name").value = "";
            document.getElementById("rule-condition").value = "";
            
            await saveSOCState();
            renderRules();
        });
    }
});

function evaluateCondition(event, conditionStr) {
    try {
        // Evaluate the JS condition safely
        const func = new Function('event', `return (${conditionStr});`);
        return func(event);
    } catch (e) {
        console.error("Rule evaluation error", e);
        return false;
    }
}

function processNewEvents(events) {
    if (!window.SOC.state.rules || window.SOC.state.rules.length === 0) return;
    
    // We only process events that are NEW since last poll to avoid duplicate alerts
    // But events don't have IDs. We can track the total_events length.
    if (window.SOC.metrics.total_events === 0 && events.length > 0) {
        // Initial load, don't alert on past history
        return;
    }
    
    const newEventsCount = events.length - window.SOC.metrics.total_events;
    if (newEventsCount <= 0) return;
    
    const newEvents = events.slice(events.length - newEventsCount);
    let alertsGenerated = false;
    
    newEvents.forEach(event => {
        window.SOC.state.rules.forEach(rule => {
            if (evaluateCondition(event, rule.condition)) {
                // Generate Alert
                window.SOC.state.alerts.push({
                    id: Date.now().toString() + Math.random().toString(36).substr(2, 5),
                    rule_id: rule.id,
                    rule_name: rule.name,
                    severity: rule.severity,
                    event: event,
                    status: "NEW",
                    timestamp: new Date().toISOString()
                });
                alertsGenerated = true;
            }
        });
    });
    
    if (alertsGenerated) {
        saveSOCState();
        if (typeof renderAlerts === "function") renderAlerts();
    if (typeof updateAlertsPie === "function") updateAlertsPie();
    if (typeof renderIncidents === "function") renderIncidents();
    }
}


async function pollSOC() {
    const [events, telemetry, ntmData] = await Promise.all([
        apiRequest("GET", "/api/simulation/events"),
        apiRequest("GET", "/api/simulation/telemetry"),
        apiRequest("GET", "/api/ntm/devices")
    ]);

    if (events) {
        processNewEvents(events);
        window.SOC.metrics.events_cache = events;
    }
    
    if (telemetry) {
        window.SOC.state.telemetry = telemetry;
    }

    updateOverviewMetrics(events || [], telemetry || {}, ntmData || []);
    if (typeof updateTrafficView === "function") updateTrafficView(telemetry || {});
    if (typeof updateHostsView === "function") updateHostsView(ntmData || []);
    if (typeof renderPcap === "function") renderPcap(ntmData || []);
}

// Navigation logic
document.addEventListener("DOMContentLoaded", async () => {
    const navItems = document.querySelectorAll(".nav-item");
    const views = document.querySelectorAll(".soc-view");
    const viewButtons = document.querySelectorAll("[data-view-target]");

    function showView(viewName) {
        views.forEach((view) => view.classList.remove("active"));
        const targetView = document.getElementById(`view-${viewName}`);
        if (!targetView) return;
        targetView.classList.add("active");
        navItems.forEach((item) => {
            item.classList.toggle("active", item.dataset.view === viewName);
        });
    }

    navItems.forEach((item) => {
        item.addEventListener("click", () => {
            if (item.dataset.view) showView(item.dataset.view);
        });
    });

    viewButtons.forEach((button) => {
        button.addEventListener("click", () => {
            if (button.dataset.viewTarget) showView(button.dataset.viewTarget);
        });
    });
    
    initTrafficChartMain();
    // Init SOC
    await loadSOCState();
    renderRules();
    if (typeof renderAlerts === "function") renderAlerts();
    if (typeof updateAlertsPie === "function") updateAlertsPie();
    if (typeof renderIncidents === "function") renderIncidents();
    pollSOC();
    window.SOC.pollInterval = setInterval(pollSOC, 2000);
});


window.renderAlerts = function() {
    const list = document.getElementById("alerts-list");
    if (!list) return;
    
    list.innerHTML = "";
    if (!window.SOC.state.alerts || window.SOC.state.alerts.length === 0) {
        list.innerHTML = '<div style="color: #666; font-style: italic;">No active alerts.</div>';
        return;
    }
    
    // Sort newest first
    const sortedAlerts = [...window.SOC.state.alerts].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    sortedAlerts.forEach(alert => {
        const item = document.createElement("div");
        const color = alert.severity === 'CRITICAL' ? '#ef4444' : (alert.severity === 'HIGH' ? '#f97316' : '#3b82f6');
        item.style = `background: rgba(15,23,42,0.8); padding: 1rem; margin-bottom: 0.5rem; border-left: 4px solid ${color}; display: flex; justify-content: space-between; align-items: center;`;
        
        item.innerHTML = `
            <div>
                <strong style="color: white; font-size: 1.1rem;">${alert.rule_name}</strong> 
                <span style="font-size: 0.8rem; padding: 2px 6px; border-radius: 4px; background: rgba(255,255,255,0.1); margin-left: 0.5rem;">${alert.severity}</span>
                <span style="font-size: 0.8rem; color: #8b9bb4; margin-left: 0.5rem;">${new Date(alert.timestamp).toLocaleString()}</span>
                <div style="font-size: 0.9rem; color: #cbd5e1; margin-top: 0.5rem;">
                    Source: <span style="color: white;">${alert.event.source}</span> &rarr; Dest: <span style="color: white;">${alert.event.destination}</span>
                    <br><span style="color: #64748b; font-size: 0.8rem;">Trigger: ${alert.event.type}</span>
                </div>
            </div>
            <div>
                <select onchange="updateAlertStatus('${alert.id}', this.value)" style="background: #0f172a; border: 1px solid #1e293b; color: white; padding: 0.5rem;">
                    <option value="NEW" ${alert.status === 'NEW' ? 'selected' : ''}>NEW</option>
                    <option value="INVESTIGATING" ${alert.status === 'INVESTIGATING' ? 'selected' : ''}>INVESTIGATING</option>
                    <option value="RESOLVED" ${alert.status === 'RESOLVED' ? 'selected' : ''}>RESOLVED</option>
                </select>
                <button onclick="deleteAlert('${alert.id}')" style="background: transparent; border: 1px solid #ef4444; color: #ef4444; padding: 0.5rem; cursor: pointer; margin-left: 0.5rem;">DELETE</button>
            </div>
        `;
        list.appendChild(item);
    });
};

window.updateAlertStatus = async function(id, newStatus) {
    const alert = window.SOC.state.alerts.find(a => a.id === id);
    if (alert) {
        alert.status = newStatus;
        await saveSOCState();
    }
};

window.deleteAlert = async function(id) {
    window.SOC.state.alerts = window.SOC.state.alerts.filter(a => a.id !== id);
    await saveSOCState();
    renderAlerts();
    updateOverviewMetrics(window.SOC.metrics.events_cache || [], window.SOC.state.telemetry || {}, []); // Force update
};



let trafficChartMain = null;
const subCharts = {}; 
window.SOC.telemetryHistory = { "ALL": { tx: [], rx: [] }, labels: [] };
const MAX_HISTORY = 60; // 2 minutes at 2sec polls


function initTrafficChartMain() {
    const ctx = document.getElementById('trafficChartMain');
    if (!ctx) return;
    
    trafficChartMain = new Chart(ctx, {
        type: 'line',
        data: {
            labels: window.SOC.telemetryHistory.labels,
            datasets: [
                { label: 'Total Events Generated', data: window.SOC.telemetryHistory["ALL"].tx, borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.2)', fill: true, tension: 0.4 },
                { label: 'Total Events Received', data: window.SOC.telemetryHistory["ALL"].rx, borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.2)', fill: true, tension: 0.4 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            scales: {
                x: { ticks: { color: '#8b9bb4' }, grid: { color: '#1e293b' } },
                y: { ticks: { color: '#8b9bb4' }, grid: { color: '#1e293b' }, beginAtZero: true }
            },
            plugins: {
                legend: { labels: { color: 'white' } }
            }
        }
    });
}

window.toggleSubChart = function(device) {
    const container = document.getElementById("sub-charts-container");
    if (!container) return;
    
    if (subCharts[device]) {
        subCharts[device].chart.destroy();
        delete subCharts[device];
        const el = document.getElementById(`subchart-wrap-${device.replace(/[^a-zA-Z0-9]/g, '')}`);
        if (el) el.remove();
    } else {
        const safeId = device.replace(/[^a-zA-Z0-9]/g, '');
        const wrap = document.createElement("div");
        wrap.id = `subchart-wrap-${safeId}`;
        wrap.style = "width: calc(50% - 0.5rem); height: 250px; background: rgba(0,0,0,0.2); border: 1px solid #2a3a5a; padding: 1rem; border-radius: 4px; box-sizing: border-box; display: flex; flex-direction: column;";
        wrap.innerHTML = `<h5 style="margin-top:0; margin-bottom: 1rem; color: white; display: flex; justify-content: space-between;">
            <span>${device} <span style="font-size:0.7rem; color:#64748b;">(Events / Min)</span></span>
            <span id="subchart-rate-${safeId}" style="font-size: 0.8rem; color: #8b9bb4; font-weight: normal; background: #0f172a; padding: 2px 6px; border-radius: 4px; border: 1px solid #1e293b;">TX: 0 B/s | RX: 0 B/s</span>
        </h5><div style="flex-grow:1; position:relative;"><canvas id="subchart-${safeId}"></canvas></div>`;
        container.appendChild(wrap);
        
        const ctx = document.getElementById(`subchart-${safeId}`);
        if (!window.SOC.telemetryHistory[device]) {
            const len = window.SOC.telemetryHistory.labels.length;
            window.SOC.telemetryHistory[device] = { tx: new Array(len).fill(0), rx: new Array(len).fill(0) };
        }
        
        subCharts[device] = {
            chart: new Chart(ctx, {
                type: 'line',
                data: {
                    labels: window.SOC.telemetryHistory.labels,
                    datasets: [
                        { label: 'Generated', data: window.SOC.telemetryHistory[device].tx, borderColor: '#3b82f6', backgroundColor: 'rgba(59, 130, 246, 0.2)', fill: true, tension: 0.4 },
                        { label: 'Received', data: window.SOC.telemetryHistory[device].rx, borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.2)', fill: true, tension: 0.4 }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    scales: {
                        x: { ticks: { color: '#8b9bb4' }, grid: { color: '#1e293b' } },
                        y: { ticks: { color: '#8b9bb4' }, grid: { color: '#1e293b' }, beginAtZero: true }
                    },
                    plugins: { legend: { display: false } }
                }
            })
        };
    }
};

function updateTrafficView(telemetry) {
    if (!trafficChartMain) return;
    const currentDevices = Object.keys(telemetry);
    
    const dropdownList = document.getElementById("traffic-dropdown-list");
    if (dropdownList) {
        currentDevices.forEach(dev => {
            const safeId = dev.replace(/[^a-zA-Z0-9]/g, '');
            if (!document.getElementById(`cb-${safeId}`)) {
                const label = document.createElement("label");
                label.style = "display: block; color: white; cursor: pointer; margin-bottom: 0.2rem;";
                label.innerHTML = `<input type="checkbox" id="cb-${safeId}" value="${dev.replace(/"/g, '&quot;')}" style="margin-right: 0.5rem;"> ${dev}`;
                dropdownList.appendChild(label);
                
                const cb = label.querySelector('input');
                cb.addEventListener('change', (e) => {
                    toggleSubChart(e.target.value);
                });
            }
        });
    }
    
    if (!window.SOC.lastTelemetry) window.SOC.lastTelemetry = {};
    
    const now = new Date().toLocaleTimeString();
    window.SOC.telemetryHistory.labels.push(now);
    
    let allTxRate = 0, allRxRate = 0;
    
    currentDevices.forEach(dev => {
        let lastTx = 0, lastRx = 0;
        if (window.SOC.lastTelemetry[dev]) {
            lastTx = window.SOC.lastTelemetry[dev].tx_packets;
            lastRx = window.SOC.lastTelemetry[dev].rx_packets;
        }
        
        let deltaTx = telemetry[dev].tx_packets - lastTx;
        let deltaRx = telemetry[dev].rx_packets - lastRx;
        
        // Convert to per-minute rate approximation (assuming 2s polls = multiply by 30)
        let rateTx = deltaTx * 30;
        let rateRx = deltaRx * 30;
        
        if (!window.SOC.bytesHistory) window.SOC.bytesHistory = {};
        if (!window.SOC.bytesHistory[dev]) window.SOC.bytesHistory[dev] = { tx: [], rx: [] };
        
        window.SOC.bytesHistory[dev].tx.push(telemetry[dev].tx_bytes);
        window.SOC.bytesHistory[dev].rx.push(telemetry[dev].rx_bytes);
        
        // Keep up to 30 polls (60 seconds)
        if (window.SOC.bytesHistory[dev].tx.length > 30) {
            window.SOC.bytesHistory[dev].tx.shift();
            window.SOC.bytesHistory[dev].rx.shift();
        }
        
        let oldestTxB = window.SOC.bytesHistory[dev].tx[0];
        let oldestRxB = window.SOC.bytesHistory[dev].rx[0];
        
        let timeSpan = window.SOC.bytesHistory[dev].tx.length * 2; // in seconds
        if (timeSpan === 0) timeSpan = 2; // fallback
        
        let rateTxB = (telemetry[dev].tx_bytes - oldestTxB) / timeSpan;
        let rateRxB = (telemetry[dev].rx_bytes - oldestRxB) / timeSpan;
        
        const rateSpan = document.getElementById(`subchart-rate-${dev.replace(/[^a-zA-Z0-9]/g, '')}`);
        if (rateSpan) {
            const fmt = (b) => {
                if (b >= 1048576) return (b/1048576).toFixed(1) + ' MB/s';
                if (b >= 1024) return (b/1024).toFixed(1) + ' KB/s';
                return Math.round(b) + ' B/s';
            };
            rateSpan.textContent = `TX: ${fmt(rateTxB)} | RX: ${fmt(rateRxB)} (avg/min)`;
        }
        
        allTxRate += rateTx;
        allRxRate += rateRx;
        
        if (!window.SOC.telemetryHistory[dev]) {
            const len = Math.max(0, window.SOC.telemetryHistory.labels.length - 1);
            window.SOC.telemetryHistory[dev] = { tx: new Array(len).fill(0), rx: new Array(len).fill(0) };
        }
        window.SOC.telemetryHistory[dev].tx.push(rateTx);
        window.SOC.telemetryHistory[dev].rx.push(rateRx);
    });
    
    window.SOC.telemetryHistory["ALL"].tx.push(allTxRate);
    window.SOC.telemetryHistory["ALL"].rx.push(allRxRate);
    
    window.SOC.lastTelemetry = JSON.parse(JSON.stringify(telemetry));
    
    if (window.SOC.telemetryHistory.labels.length > MAX_HISTORY) {
        window.SOC.telemetryHistory.labels.shift();
        window.SOC.telemetryHistory["ALL"].tx.shift();
        window.SOC.telemetryHistory["ALL"].rx.shift();
        currentDevices.forEach(dev => {
            if (window.SOC.telemetryHistory[dev]) {
                window.SOC.telemetryHistory[dev].tx.shift();
                window.SOC.telemetryHistory[dev].rx.shift();
            }
        });
    }
    
    trafficChartMain.update();
    Object.values(subCharts).forEach(sub => sub.chart.update());
}

let alertsPieChart = null;

window.updateAlertsPie = function() {
    const timeVal = document.getElementById("alerts-pie-time") ? document.getElementById("alerts-pie-time").value : "60";
    const ctx = document.getElementById("alertsPieChart");
    if (!ctx) return;
    
    const now = new Date();
    const filteredAlerts = window.SOC.state.alerts.filter(a => {
        if (timeVal === "all") return true;
        const diffMs = now - new Date(a.timestamp);
        const mins = diffMs / 60000;
        return mins <= parseInt(timeVal);
    });
    
    const counts = {};
    filteredAlerts.forEach(a => {
        counts[a.rule_name] = (counts[a.rule_name] || 0) + 1;
    });
    
    const labels = Object.keys(counts);
    const data = Object.values(counts);
    const bgColors = labels.map((_, i) => `hsl(${i * 137.5 % 360}, 70%, 50%)`);
    
    if (alertsPieChart) {
        alertsPieChart.data.labels = labels;
        alertsPieChart.data.datasets[0].data = data;
        alertsPieChart.data.datasets[0].backgroundColor = bgColors;
        alertsPieChart.update();
    } else {
        alertsPieChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: bgColors,
                    borderWidth: 1,
                    borderColor: '#0f172a'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { color: 'white' } }
                }
            }
        });
    }
};

// HOSTS TAB LOGIC
function updateHostsView(devices) {
    const tbody = document.getElementById("hosts-table-body");
    if (!tbody || !devices || !Array.isArray(devices)) return;
    
    tbody.innerHTML = "";
    devices.forEach(d => {
        const tr = document.createElement("tr");
        tr.style.borderBottom = "1px solid #1e293b";
        
        const statusColor = d.status === "ONLINE" ? "#10b981" : (d.status === "PAUSED" ? "#f59e0b" : "#ef4444");
        const threatColor = d.soc_threat_level === "Compromised" ? "#ef4444" : (d.soc_threat_level === "Suspicious" ? "#f97316" : "#10b981");
        
        tr.innerHTML = `
            <td style="padding: 0.5rem; color: white;">${d.name}</td>
            <td style="padding: 0.5rem; color: #cbd5e1; text-transform: uppercase;">${d.type}</td>
            <td style="padding: 0.5rem; color: ${statusColor}; font-weight: bold;">${d.status}</td>
            <td style="padding: 0.5rem;">
                <select onchange="updateDeviceThreat('${d.name.replace(/'/g, "\\'")}', this.value)" style="background: #0f172a; border: 1px solid ${threatColor}; color: ${threatColor}; padding: 0.2rem;">
                    <option value="Normal" ${d.soc_threat_level === 'Normal' ? 'selected' : ''}>Normal</option>
                    <option value="Suspicious" ${d.soc_threat_level === 'Suspicious' ? 'selected' : ''}>Suspicious</option>
                    <option value="Compromised" ${d.soc_threat_level === 'Compromised' ? 'selected' : ''}>Compromised</option>
                </select>
            </td>
            <td style="padding: 0.5rem;">
                <button onclick="containDevice('${d.name.replace(/'/g, "\\'")}', 'pause')" style="background: transparent; border: 1px solid #f59e0b; color: #f59e0b; padding: 0.2rem; cursor: pointer; margin-right: 0.5rem;">PAUSE</button>
                <button onclick="containDevice('${d.name.replace(/'/g, "\\'")}', 'isolate')" style="background: transparent; border: 1px solid #ef4444; color: #ef4444; padding: 0.2rem; cursor: pointer; margin-right: 0.5rem;">ISOLATE</button>
                <button onclick="containDevice('${d.name.replace(/'/g, "\\'")}', 'reconnect')" style="background: transparent; border: 1px solid #10b981; color: #10b981; padding: 0.2rem; cursor: pointer;">RECONNECT</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

window.updateDeviceThreat = async function(name, level) {
    await apiRequest("POST", `/api/soc/devices/${encodeURIComponent(name)}/threat_level`, { level });
};

window.containDevice = async function(name, action) {
    await apiRequest("POST", `/api/soc/devices/${encodeURIComponent(name)}/action`, { action });
};

// INCIDENTS TAB LOGIC
window.renderIncidents = function() {
    const list = document.getElementById("incidents-list");
    if (!list) return;
    
    list.innerHTML = "";
    if (!window.SOC.state.incidents || window.SOC.state.incidents.length === 0) {
        list.innerHTML = '<div style="color: #666; font-style: italic;">No active incidents.</div>';
        return;
    }
    
    window.SOC.state.incidents.forEach((inc, idx) => {
        const item = document.createElement("div");
        item.style = "background: rgba(15,23,42,0.8); padding: 1rem; margin-bottom: 0.5rem; border: 1px solid #3b82f6;";
        item.innerHTML = `
            <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                <strong style="color: white; font-size: 1.1rem;">${inc.title}</strong>
                <span style="color: #8b9bb4; font-size: 0.8rem;">${new Date(inc.timestamp).toLocaleString()}</span>
            </div>
            <div style="color: #cbd5e1; font-size: 0.9rem; margin-bottom: 0.5rem; white-space: pre-wrap;">${inc.notes}</div>
            <div style="text-align: right;">
                <button onclick="deleteIncident(${idx})" style="background: transparent; border: 1px solid #ef4444; color: #ef4444; padding: 0.2rem 0.5rem; cursor: pointer;">DELETE</button>
            </div>
        `;
        list.appendChild(item);
    });
};

window.createIncident = async function() {
    const title = document.getElementById("incident-title").value;
    const notes = document.getElementById("incident-notes").value;
    if (!title) return alert("Title is required");
    
    window.SOC.state.incidents.push({
        id: Date.now().toString(),
        title,
        notes,
        timestamp: new Date().toISOString()
    });
    
    document.getElementById("incident-title").value = "";
    document.getElementById("incident-notes").value = "";
    
    await saveSOCState();
    renderIncidents();
};

window.deleteIncident = async function(idx) {
    window.SOC.state.incidents.splice(idx, 1);
    await saveSOCState();
    renderIncidents();
};

// PCAP TAB LOGIC
window.renderPcap = function(devices) {
    const tbody = document.getElementById("pcap-table-body");
    if (!tbody || !devices) return;
    
    tbody.innerHTML = "";
    devices.forEach(d => {
        if (d.type === "switch") return; // exclude switches from PCAP tab
        if (!d.interfaces || d.interfaces.length === 0) return;
        
        d.interfaces.forEach(intf => {
            const tr = document.createElement("tr");
            tr.style.borderBottom = "1px solid #1e293b";
            
            const dlLink = `/api/ncm/devices/${encodeURIComponent(d.name)}/interfaces/${encodeURIComponent(intf.name)}/pcap`;
            
            tr.innerHTML = `
                <td style="padding: 0.5rem; color: white;">${d.name}</td>
                <td style="padding: 0.5rem; color: #cbd5e1;">${intf.name}</td>
                <td style="padding: 0.5rem;">
                    <a href="${dlLink}" download="${d.name}_${intf.name}.pcap" style="background: transparent; border: 1px solid #3b82f6; color: #3b82f6; padding: 0.2rem 0.5rem; text-decoration: none; cursor: pointer;">DOWNLOAD PCAP</a>
                </td>
            `;
            tbody.appendChild(tr);
        });
    });
};
