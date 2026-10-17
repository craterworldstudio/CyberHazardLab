/*
 * Cyber Hazard Lab - Security Operations Center
 * SIEM Core Architecture, Live Polling & UI Engine
 */

window.SOC = {
    state: {
        rules: [],
        alerts: [],
        incidents: [],
        settings: {},
        collector_status: {},
        hosts: {},
        telemetry: {},
        events: []
    },
    metrics: {
        total_events: 0,
        last_event_time: null,
        history: []
    },
    ui: {
        activeSeverityFilter: "ALL",
        activeStatusFilter: "ALL",
        searchTerm: "",
        selectedEvidenceIds: new Set(),
        selectedEvidenceObjects: new Map()
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
    try {
        const response = await fetch(endpoint, options);
        if (!response.ok) {
            console.error(`API Error: ${method} ${endpoint} - ${response.statusText}`);
            return null;
        }
        return await response.json();
    } catch (err) {
        console.error(`Network error: ${method} ${endpoint}`, err);
        return null;
    }
}

// ========================================================
// STATE SYNCHRONIZATION
// ========================================================

async function loadSOCState() {
    const data = await apiRequest("GET", "/api/soc/state");
    if (data && !data.error) {
        window.SOC.state.rules = data.rules || [];
        window.SOC.state.alerts = data.alerts || [];
        window.SOC.state.incidents = data.incidents || [];
        window.SOC.state.settings = data.settings || {};
        window.SOC.state.collector_status = data.collector_status || {};
        window.SOC.state.events = data.ingested_events || [];
        window.SOC.state.total_events_count = data.total_events_count !== undefined ? data.total_events_count : (data.ingested_events ? data.ingested_events.length : 0);
    }
}

async function saveSOCState() {
    await apiRequest("POST", "/api/soc/state", {
        rules: window.SOC.state.rules,
        alerts: window.SOC.state.alerts,
        incidents: window.SOC.state.incidents,
        settings: window.SOC.state.settings
    });
}

// ========================================================
// OVERVIEW TAB LOGIC
// ========================================================

function updateOverviewMetrics(events, telemetry, devices) {
    if (!devices || !Array.isArray(devices) || devices.length === 0) {
        devices = (window.SOC.cache && window.SOC.cache.ntmData) || Object.values(window.SOC.state.hosts || {});
    }

    // 1. Hosts
    let totalHosts = 0;
    let onlineHosts = 0;
    if (devices && Array.isArray(devices)) {
        totalHosts = devices.length;
        onlineHosts = devices.filter(d => d.status === "ONLINE").length;
    }
    const hostTotalEl = document.getElementById("metric-hosts-total");
    const hostOnlineEl = document.getElementById("metric-hosts-online");
    if (hostTotalEl) hostTotalEl.textContent = totalHosts;
    if (hostOnlineEl) hostOnlineEl.textContent = `${onlineHosts} ONLINE`;

    // 2. Events & Rate
    const totalCount = window.SOC.state.total_events_count !== undefined ? window.SOC.state.total_events_count : (events ? events.length : 0);
    window.SOC.metrics.total_events = totalCount;
    const evtTotalEl = document.getElementById("metric-events-total");
    if (evtTotalEl) evtTotalEl.textContent = totalCount;

    window.SOC.metrics.history.push({ time: Date.now(), count: totalCount });
    if (window.SOC.metrics.history.length > 8) window.SOC.metrics.history.shift();

    let rate = 0;
    if (window.SOC.metrics.history.length > 1) {
        const first = window.SOC.metrics.history[0];
        const last = window.SOC.metrics.history[window.SOC.metrics.history.length - 1];
        const timeDiffSec = (last.time - first.time) / 1000;
        const countDiff = last.count - first.count;
        if (timeDiffSec > 0) rate = (countDiff / timeDiffSec) * 60; // events / min
    }
    const evtRateEl = document.getElementById("metric-events-rate");
    if (evtRateEl) evtRateEl.textContent = `+${Math.max(0, rate).toFixed(1)} / MIN`;

    // 3. Alerts
    const alerts = window.SOC.state.alerts || [];
    const activeAlerts = alerts.filter(a => a.status !== "RESOLVED");
    const newAlerts = alerts.filter(a => a.status === "NEW");
    const criticalAlerts = activeAlerts.filter(a => a.severity === "CRITICAL");

    const alertTotalEl = document.getElementById("metric-alerts-total");
    const alertNewEl = document.getElementById("metric-alerts-new");
    const alertCritEl = document.getElementById("metric-alerts-critical");
    const sidebarCountEl = document.querySelector('.nav-item[data-view="alerts"] .nav-count');

    if (alertTotalEl) alertTotalEl.textContent = activeAlerts.length;
    if (alertNewEl) alertNewEl.textContent = `+${newAlerts.length} NEW`;
    if (alertCritEl) alertCritEl.textContent = criticalAlerts.length;
    if (sidebarCountEl) sidebarCountEl.textContent = activeAlerts.length;

    // 4. Live Activity Feed (last 12 events)
    renderActivityFeed(events.slice(-12).reverse());

    // 5. Overview Alerts Feed (top 4 recent alerts)
    renderOverviewAlerts(activeAlerts.slice(0, 4));

    // 6. Live Infrastructure Zones & Threat Posture Grid
    if (typeof renderInfrastructureZones === "function") {
        renderInfrastructureZones(devices, telemetry, activeAlerts);
    } else if (typeof renderOverviewNetworkActivity === "function") {
        renderOverviewNetworkActivity(devices, telemetry, activeAlerts);
    }
}

window.renderInfrastructureZones = async function(devices, telemetry, alerts) {
    const grid = document.getElementById("overview-zones-grid");
    if (!grid) return;

    if (!devices || devices.length === 0) {
        grid.innerHTML = '<div style="color: var(--text-muted); font-size: 0.85rem; font-style: italic; padding: 1.5rem; text-align: center; grid-column: 1/-1;">Awaiting Network Topology & Host Discovery...</div>';
        return;
    }

    // 1. Fetch dynamic zones from backend (or compute dynamic fallback)
    let zones = [];
    try {
        const res = await apiRequest("GET", "/api/simulation/zones");
        if (Array.isArray(res) && res.length > 0) {
            zones = res;
        }
    } catch (e) {
        zones = [];
    }

    // Client-side dynamic subnet grouping fallback if backend zones not returned
    if (!zones || zones.length === 0) {
        const subnetsMap = {};
        devices.forEach(d => {
            const intfs = d.interfaces || [];
            intfs.forEach(intf => {
                const ip = intf.ip;
                if (!ip || ip === "0.0.0.0") return;
                const parts = ip.split(".");
                if (parts.length === 4) {
                    const cidr = `${parts[0]}.${parts[1]}.${parts[2]}.0/24`;
                    if (!subnetsMap[cidr]) {
                        subnetsMap[cidr] = {
                            id: cidr.replace(/\./g, "-").replace(/\//g, "_"),
                            name: `Zone ${cidr}`,
                            cidr: cidr,
                            gateway: d.default_gateway || (intf.gateway || `${parts[0]}.${parts[1]}.${parts[2]}.1`),
                            icon: "🌐",
                            description: `Subnet ${cidr} Infrastructure`,
                            devices: []
                        };
                    }
                    if (!subnetsMap[cidr].devices.includes(d.name)) {
                        subnetsMap[cidr].devices.push(d.name);
                    }
                }
            });
        });
        zones = Object.values(subnetsMap);
    }

    window.SOC.dynamicZones = zones;

    const activeAlerts = (alerts && Array.isArray(alerts)) ? alerts.filter(a => a.status !== "RESOLVED") : [];
    const devMap = {};
    devices.forEach(d => { devMap[d.name] = d; });

    let overallElevatedZones = 0;
    let cardsHtml = "";

    zones.forEach(zone => {
        const zoneDevices = (zone.devices || []).map(name => devMap[name]).filter(Boolean);

        // Check threats dynamically from actual devices and live alerts
        const hasCompromised = zoneDevices.some(d => (d.soc_threat_level || "").toLowerCase() === "compromised");
        const hasSuspicious = zoneDevices.some(d => (d.soc_threat_level || "").toLowerCase() === "suspicious");

        const zoneNamesSet = new Set(zoneDevices.map(d => (d.name || "").toLowerCase()));
        const zoneIpsSet = new Set(zoneDevices.flatMap(d => (d.interfaces || []).map(i => i.ip)).filter(Boolean));

        const zoneAlerts = activeAlerts.filter(a => {
            const ev = a.event || {};
            const src = (ev.source || "").toLowerCase();
            const dst = (ev.destination || "").toLowerCase();
            return zoneNamesSet.has(src) || zoneNamesSet.has(dst) || zoneIpsSet.has(ev.source) || zoneIpsSet.has(ev.destination);
        });

        let posture = "SECURE";
        let postureColor = "var(--green)";
        let postureBg = "rgba(57, 217, 138, 0.1)";
        let postureBorder = "rgba(57, 217, 138, 0.35)";
        let cardGlow = "none";
        let cardBorder = "var(--border)";

        if (hasCompromised || zoneAlerts.some(a => a.severity === "CRITICAL" || a.severity === "HIGH")) {
            posture = "COMPROMISED";
            postureColor = "var(--red)";
            postureBg = "rgba(255, 77, 95, 0.15)";
            postureBorder = "var(--red)";
            cardGlow = "0 0 16px rgba(255, 77, 95, 0.25)";
            cardBorder = "rgba(255, 77, 95, 0.5)";
            overallElevatedZones++;
        } else if (hasSuspicious || zoneAlerts.length > 0) {
            posture = "SUSPICIOUS";
            postureColor = "var(--orange)";
            postureBg = "rgba(229, 139, 69, 0.15)";
            postureBorder = "var(--orange)";
            cardGlow = "0 0 12px rgba(229, 139, 69, 0.2)";
            cardBorder = "rgba(229, 139, 69, 0.4)";
            overallElevatedZones++;
        }

        const onlineCount = zoneDevices.filter(d => d.status === "ONLINE").length;

        // Device pills
        const pillsHtml = zoneDevices.map(d => {
            const threat = (d.soc_threat_level || "Normal").toLowerCase();
            let dotColor = "var(--green)";
            if (threat === "compromised") dotColor = "var(--red)";
            else if (threat === "suspicious") dotColor = "var(--orange)";
            else if (d.status === "OFFLINE") dotColor = "var(--text-muted)";

            const devIp = (d.interfaces && d.interfaces[0] && d.interfaces[0].ip) || "Layer-2";

            return `
                <div style="display: inline-flex; align-items: center; gap: 5px; background: rgba(255,255,255,0.04); border: 1px solid var(--border); border-radius: 3px; padding: 2px 6px; font-size: 0.68rem;" title="${d.name} (${devIp}) | Status: ${d.status} | Threat: ${d.soc_threat_level || 'Normal'}">
                    <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: ${dotColor};"></span>
                    <span style="color: ${threat === 'compromised' ? 'var(--red)' : '#fff'}; font-weight: 500;">${d.name}</span>
                </div>
            `;
        }).join("");

        cardsHtml += `
            <div class="zone-card" style="background: var(--bg-panel-alt); border: 1px solid ${cardBorder}; border-radius: 4px; padding: 1rem; box-shadow: ${cardGlow}; transition: transform 0.2s, box-shadow 0.2s; display: flex; flex-direction: column; justify-content: space-between; gap: 0.75rem;">
                <!-- Header -->
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 0.5rem; margin-bottom: 0.4rem;">
                        <div style="display: flex; align-items: center; gap: 8px;">
                            <span style="font-size: 1.25rem;">${zone.icon || '🌐'}</span>
                            <div>
                                <div style="font-weight: bold; color: white; font-size: 0.85rem; letter-spacing: 0.5px;">${zone.name}</div>
                                <div style="font-size: 0.68rem; color: var(--cyan); font-family: var(--font-mono);">${zone.cidr}</div>
                            </div>
                        </div>
                        <span style="font-size: 0.68rem; font-weight: bold; padding: 2px 7px; border-radius: 3px; background: ${postureBg}; color: ${postureColor}; border: 1px solid ${postureBorder}; white-space: nowrap; letter-spacing: 0.5px;">
                            ● ${posture}
                        </span>
                    </div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.5rem;">
                        ${zone.description} <span style="color: var(--text-dim);">| GW: ${zone.gateway || 'None'}</span>
                    </div>
                </div>

                <!-- Metrics & Pills -->
                <div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem; font-size: 0.72rem; color: var(--text-muted);">
                        <span>Monitored Assets: <strong style="color: white;">${zoneDevices.length}</strong> (${onlineCount} Online)</span>
                        ${zoneAlerts.length > 0 ? `<span style="color: ${postureColor}; font-weight: bold;">${zoneAlerts.length} Active Alert${zoneAlerts.length > 1 ? 's' : ''}</span>` : '<span style="color: var(--green);">0 Active Alerts</span>'}
                    </div>

                    <div style="display: flex; flex-wrap: wrap; gap: 4px; max-height: 52px; overflow-y: auto; padding: 2px 0;">
                        ${pillsHtml || '<span style="color: var(--text-muted); font-size: 0.68rem; font-style: italic;">No devices mapped</span>'}
                    </div>
                </div>

                <!-- Footer Jump -->
                <div style="display: flex; justify-content: flex-end; align-items: center; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 0.5rem; margin-top: 0.25rem;">
                    <button onclick="navigateToTopologyZone('${zone.id}')" style="background: transparent; border: none; color: var(--cyan); font-size: 0.7rem; cursor: pointer; display: flex; align-items: center; gap: 4px; padding: 0; font-family: inherit; font-weight: bold; letter-spacing: 0.5px;">
                        INSPECT ZONE ON MAP &rarr;
                    </button>
                </div>
            </div>
        `;
    });

    grid.innerHTML = cardsHtml;

    // Update the summary badge in the panel header if present
    const summaryBadge = document.getElementById("zone-summary-badge");
    if (summaryBadge) {
        if (overallElevatedZones > 0) {
            summaryBadge.textContent = `${overallElevatedZones} ZONE${overallElevatedZones > 1 ? 'S' : ''} ELEVATED RISK`;
            summaryBadge.style.color = "var(--red)";
            summaryBadge.style.borderColor = "var(--red)";
            summaryBadge.style.background = "rgba(255, 77, 95, 0.12)";
        } else {
            summaryBadge.textContent = `${zones.length} ZONES MONITORED / ALL SECURE`;
            summaryBadge.style.color = "var(--green)";
            summaryBadge.style.borderColor = "var(--green)";
            summaryBadge.style.background = "rgba(57, 217, 138, 0.12)";
        }
    }
};

window.navigateToTopologyZone = function(zoneId) {
    const nav = document.querySelector('.nav-item[data-view="network"]');
    if (nav) nav.click();

    if (zoneId) {
        setTimeout(() => {
            const dynamicZone = (window.SOC.dynamicZones || []).find(z => z.id === zoneId);
            const targets = dynamicZone ? (dynamicZone.devices || []) : [];
            document.querySelectorAll(".topology-node").forEach(node => {
                const name = node.dataset.deviceName;
                if (targets.includes(name)) {
                    node.style.filter = "drop-shadow(0 0 14px var(--cyan))";
                    const circle = node.querySelector("circle");
                    if (circle) {
                        circle.setAttribute("stroke", "var(--cyan)");
                        circle.setAttribute("stroke-width", "4");
                    }
                }
            });
        }, 150);
    }
};

// Backwards compatibility alias
window.renderOverviewNetworkActivity = function(devices, telemetry, alerts) {
    if (typeof window.renderInfrastructureZones === "function") {
        window.renderInfrastructureZones(devices, telemetry, alerts);
    }
};

function renderActivityFeed(recentEvents) {
    const list = document.getElementById("activity-list");
    if (!list) return;

    if (!recentEvents || recentEvents.length === 0) {
        list.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 1rem; text-align: center;">Awaiting telemetry...</div>';
        return;
    }

    list.innerHTML = "";
    recentEvents.forEach(e => {
        const row = document.createElement("div");
        row.className = "activity-row";
        if (e.severity === "HIGH" || e.severity === "CRITICAL" || e.severity === "WARNING") {
            row.classList.add("alert-row");
        }
        const time = e.timestamp && e.timestamp !== "LIVE" ? new Date(e.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
        const typeStr = (e.protocol || e.type || "SYS").replace(/_/g, " ");
        const srcDst = e.destination ? `${e.source} &rarr; ${e.destination}` : `${e.source}`;

        row.innerHTML = `
            <span class="activity-time">${time}</span>
            <span class="activity-type">${typeStr}</span>
            <span class="activity-message">${e.type || "EVENT"}: ${srcDst}</span>
        `;
        list.appendChild(row);
    });
}

function renderOverviewAlerts(activeAlerts) {
    const list = document.getElementById("overview-alerts-list");
    if (!list) return;

    if (!activeAlerts || activeAlerts.length === 0) {
        list.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 1rem; text-align: center;">No active security alerts.</div>';
        return;
    }

    list.innerHTML = "";
    activeAlerts.forEach(a => {
        const item = document.createElement("div");
        const sevClass = (a.severity || "info").toLowerCase();
        item.className = `alert-item ${sevClass}`;
        const time = a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : "";
        const srcDst = a.event ? `${a.event.source || "unknown"} &rarr; ${a.event.destination || "host"}` : "";

        item.innerHTML = `
            <div class="alert-severity">${a.severity}</div>
            <div class="alert-title">${a.rule_name || "Security Alert"}</div>
            <div class="alert-source">${srcDst}</div>
            <div class="alert-time">${time}</div>
        `;
        list.appendChild(item);
    });
}

// ========================================================
// ALERTS TAB LOGIC
// ========================================================

window.renderAlerts = function() {
    const list = document.getElementById("alerts-list");
    if (!list) return;

    let alerts = window.SOC.state.alerts || [];
    const sevFilter = window.SOC.ui.activeSeverityFilter;
    const statusFilter = window.SOC.ui.activeStatusFilter;
    const search = window.SOC.ui.searchTerm.toLowerCase().trim();

    if (sevFilter !== "ALL") {
        alerts = alerts.filter(a => (a.severity || "").toUpperCase() === sevFilter);
    }
    if (statusFilter !== "ALL") {
        alerts = alerts.filter(a => (a.status || "").toUpperCase() === statusFilter);
    }
    if (search) {
        alerts = alerts.filter(a => {
            const rule = (a.rule_name || "").toLowerCase();
            const src = (a.event?.source || "").toLowerCase();
            const dst = (a.event?.destination || "").toLowerCase();
            const type = (a.event?.type || "").toLowerCase();
            return rule.includes(search) || src.includes(search) || dst.includes(search) || type.includes(search);
        });
    }

    list.innerHTML = "";
    if (alerts.length === 0) {
        list.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 2rem; text-align: center;">No matching security alerts found.</div>';
        return;
    }

    alerts.forEach(alert => {
        const item = document.createElement("div");
        const color = alert.severity === 'CRITICAL' ? 'var(--red)' : (alert.severity === 'HIGH' ? 'var(--orange)' : (alert.severity === 'MEDIUM' ? 'var(--yellow)' : 'var(--cyan)'));
        item.style = `background: rgba(8, 12, 16, 0.85); padding: 1rem; margin-bottom: 0.75rem; border-left: 4px solid ${color}; border: 1px solid var(--border); border-left-width: 4px; border-radius: 4px; display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;`;

        const ev = alert.event || {};
        const metaStr = ev.metadata ? Object.entries(ev.metadata).map(([k, v]) => `${k}=${v}`).join(", ") : "";

        item.innerHTML = `
            <div style="flex: 1;">
                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem;">
                    <strong style="color: white; font-size: 1.05rem;">${alert.rule_name}</strong> 
                    <span style="font-size: 0.75rem; font-weight: bold; padding: 2px 6px; border-radius: 3px; background: rgba(255,255,255,0.08); color: ${color}; border: 1px solid ${color};">${alert.severity}</span>
                    <span style="font-size: 0.8rem; color: var(--text-muted); margin-left: 0.5rem;">${new Date(alert.timestamp).toLocaleString()}</span>
                </div>
                <div style="font-size: 0.85rem; color: var(--text-main); margin-top: 0.35rem;">
                    Source: <code style="color: var(--cyan);">${ev.source || "unknown"}</code> &rarr; Target: <code style="color: var(--cyan);">${ev.destination || "host"}</code>
                    <span style="color: var(--text-muted); margin-left: 1rem;">Protocol: <strong>${ev.protocol || "SYS"}</strong></span>
                </div>
                <div style="color: var(--text-muted); font-size: 0.8rem; margin-top: 0.25rem;">
                    Trigger Event: <span style="color: #cbd5e1;">${ev.type || "EVENT"}</span> ${metaStr ? `| ${metaStr}` : ""}
                </div>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center; flex-shrink: 0;">
                <select onchange="updateAlertStatus('${alert.id}', this.value)" style="background: var(--bg-main); border: 1px solid var(--border); color: white; padding: 0.35rem 0.6rem; border-radius: 3px; font-size: 0.8rem;">
                    <option value="NEW" ${alert.status === 'NEW' ? 'selected' : ''}>NEW</option>
                    <option value="INVESTIGATING" ${alert.status === 'INVESTIGATING' ? 'selected' : ''}>INVESTIGATING</option>
                    <option value="RESOLVED" ${alert.status === 'RESOLVED' ? 'selected' : ''}>RESOLVED</option>
                </select>
                <button onclick="chainAlertToIncident('${alert.id}')" style="background: rgba(0, 229, 255, 0.1); border: 1px solid var(--cyan); color: var(--cyan); padding: 0.35rem 0.65rem; border-radius: 3px; cursor: pointer; font-size: 0.8rem;">+ INCIDENT</button>
                <button onclick="deleteAlert('${alert.id}')" style="background: transparent; border: 1px solid var(--red); color: var(--red); padding: 0.35rem 0.65rem; border-radius: 3px; cursor: pointer; font-size: 0.8rem;">DELETE</button>
            </div>
        `;
        list.appendChild(item);
    });
};

window.updateAlertStatus = async function(id, newStatus) {
    await apiRequest("POST", `/api/soc/alerts/${encodeURIComponent(id)}/status`, { status: newStatus });
    const alert = window.SOC.state.alerts.find(a => a.id === id);
    if (alert) alert.status = newStatus;
    renderAlerts();
    updateOverviewMetrics(window.SOC.state.events, window.SOC.state.telemetry, Object.values(window.SOC.state.hosts));
};

window.deleteAlert = async function(id) {
    await apiRequest("DELETE", `/api/soc/alerts/${encodeURIComponent(id)}`);
    window.SOC.state.alerts = window.SOC.state.alerts.filter(a => a.id !== id);
    renderAlerts();
    renderEvidencePicker();
    updateOverviewMetrics(window.SOC.state.events, window.SOC.state.telemetry, Object.values(window.SOC.state.hosts));
};

window.chainAlertToIncident = function(alertId) {
    window.SOC.ui.selectedEvidenceIds.add(alertId);
    renderEvidencePicker();
    // Switch to incidents tab
    const incNav = document.querySelector('.nav-item[data-view="incidents"]');
    if (incNav) incNav.click();
};

// ========================================================
// THREAT POPUP & AUDIBLE WARNING ALERT SYSTEM
// ========================================================

window.SOC._seenAlertIds = window.SOC._seenAlertIds || new Set();
window.SOC._audioCtx = null;

function playAlertBeep(severity) {
    try {
        const storedBeep = localStorage.getItem("SOC_ALERT_BEEP");
        const settings = (window.SOC.state && window.SOC.state.settings) || {};
        const isBeepEnabled = storedBeep !== null ? (storedBeep === "true") : (settings.alert_beep !== false);
        if (!isBeepEnabled) return;

        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        if (!AudioContextClass) return;
        if (!window.SOC._audioCtx) {
            window.SOC._audioCtx = new AudioContextClass();
        }
        const ctx = window.SOC._audioCtx;
        if (ctx.state === "suspended") {
            ctx.resume();
        }

        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();

        osc.type = severity === "CRITICAL" ? "sawtooth" : "sine";
        // Frequency sweep from 880Hz (A5) to 440Hz (A4)
        const startFreq = severity === "CRITICAL" ? 950 : 800;
        const endFreq = severity === "CRITICAL" ? 440 : 520;
        osc.frequency.setValueAtTime(startFreq, now);
        osc.frequency.exponentialRampToValueAtTime(endFreq, now + 0.35);

        gain.gain.setValueAtTime(0.18, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.38);

        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now);
        osc.stop(now + 0.4);

        if (severity === "CRITICAL") {
            // Dual pulse for critical severity
            setTimeout(() => {
                try {
                    const ctx2 = window.SOC._audioCtx;
                    if (!ctx2) return;
                    const now2 = ctx2.currentTime;
                    const osc2 = ctx2.createOscillator();
                    const gain2 = ctx2.createGain();
                    osc2.type = "sawtooth";
                    osc2.frequency.setValueAtTime(1050, now2);
                    osc2.frequency.exponentialRampToValueAtTime(500, now2 + 0.3);
                    gain2.gain.setValueAtTime(0.2, now2);
                    gain2.gain.exponentialRampToValueAtTime(0.001, now2 + 0.32);
                    osc2.connect(gain2);
                    gain2.connect(ctx2.destination);
                    osc2.start(now2);
                    osc2.stop(now2 + 0.35);
                } catch (e) {}
            }, 180);
        }
    } catch (e) {
        console.warn("[SOC:AUDIO] Warning beep blocked by browser autoplay policy until user gesture", e);
    }
}

function showThreatPopup(alert) {
    const container = document.getElementById("soc-alert-toasts");
    if (!container) return;

    const isCrit = alert.severity === "CRITICAL";
    const color = isCrit ? "var(--red)" : "var(--orange)";
    const bg = isCrit ? "rgba(18, 5, 8, 0.95)" : "rgba(18, 12, 5, 0.95)";
    const border = isCrit ? "rgba(255, 77, 95, 0.85)" : "rgba(229, 139, 69, 0.85)";
    const glow = isCrit ? "0 0 25px rgba(255, 77, 95, 0.45)" : "0 0 18px rgba(229, 139, 69, 0.35)";

    const ev = alert.event || {};
    const toast = document.createElement("div");
    toast.style = `
        background: ${bg};
        border: 1.5px solid ${border};
        border-left: 5px solid ${color};
        box-shadow: ${glow};
        border-radius: 4px;
        padding: 12px 14px;
        color: white;
        pointer-events: auto;
        font-family: var(--font-ui);
        animation: toast-in 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        display: flex;
        flex-direction: column;
        gap: 6px;
    `;

    toast.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="background: ${color}; color: #0a0f18; font-weight: 900; font-size: 10px; padding: 2px 6px; border-radius: 3px; letter-spacing: 1px;">${alert.severity}</span>
                <span style="font-weight: bold; font-size: 13px; color: white;">SECURITY ALERT DETECTED</span>
            </div>
            <button onclick="this.closest('div').parentElement.remove()" style="background: transparent; border: none; color: #8a9ba8; cursor: pointer; font-size: 16px; line-height: 1; padding: 2px 4px;">&times;</button>
        </div>
        <div style="font-size: 12px; font-weight: bold; color: ${color}; margin-top: 2px;">${alert.rule_name}</div>
        <div style="font-size: 11px; color: #cbd5e1; font-family: monospace;">
            Source: <strong style="color: var(--cyan);">${ev.source || "unknown"}</strong> &rarr; Target: <strong style="color: var(--cyan);">${ev.destination || "network"}</strong>
        </div>
        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px;">
            <button onclick="document.querySelector('.nav-item[data-view=\\'alerts\\']').click(); this.closest('div').parentElement.remove();" style="background: rgba(0, 229, 255, 0.15); border: 1px solid var(--cyan); color: var(--cyan); font-family: monospace; font-size: 10px; font-weight: bold; padding: 4px 10px; cursor: pointer; border-radius: 2px;">[ VIEW IN ALERTS ]</button>
            <button onclick="this.closest('div').parentElement.remove()" style="background: rgba(255, 255, 255, 0.05); border: 1px solid var(--border); color: #8a9ba8; font-family: monospace; font-size: 10px; padding: 4px 8px; cursor: pointer; border-radius: 2px;">DISMISS</button>
        </div>
    `;

    container.appendChild(toast);

    // Auto-dismiss after 9 seconds
    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.opacity = "0";
            toast.style.transition = "opacity 0.4s";
            setTimeout(() => toast.remove(), 400);
        }
    }, 9000);
}

function checkNewThreatAlerts(alerts) {
    if (!alerts || !Array.isArray(alerts)) return;

    // First run initialize set without ringing historical alerts
    if (window.SOC._seenAlertIds.size === 0) {
        alerts.forEach(a => window.SOC._seenAlertIds.add(a.id));
        return;
    }

    const newThreats = [];
    alerts.forEach(a => {
        if (!window.SOC._seenAlertIds.has(a.id)) {
            window.SOC._seenAlertIds.add(a.id);
            if (a.status !== "RESOLVED" && (a.severity === "CRITICAL" || a.severity === "HIGH")) {
                newThreats.push(a);
            }
        }
    });

    if (newThreats.length > 0) {
        // Trigger popup & warning beep for the latest threat
        const topThreat = newThreats[0];
        playAlertBeep(topThreat.severity);
        newThreats.slice(0, 3).forEach(showThreatPopup);
    }
}


// ========================================================
// NETWORK TOPOLOGY TAB LOGIC (Clean Immutable Core View)
// ========================================================

window.renderNetworkTopology = function(devices, links, layout) {
    const container = document.getElementById("soc-topology-container");
    if (!container) return;

    if (!devices || devices.length === 0) {
        container.innerHTML = '<div style="color: var(--text-muted); padding: 3rem; text-align: center;">Awaiting Network Topology Discovery...</div>';
        return;
    }

    // Filter out laptops: Show only core devices up to Access Points (Routers, Switches, APs, Servers, PCs)
    const coreDevices = devices.filter(d => (d.type || "").toLowerCase() !== "laptop");

    const countEl = document.getElementById("network-devices-count");
    if (countEl) countEl.textContent = `${coreDevices.length} CORE NODES`;

    const width = container.clientWidth || 1000;
    const height = container.clientHeight || 720;

    const coreNames = new Set(coreDevices.map(d => d.name));
    const coreLinks = (Array.isArray(links) ? links : []).filter(link => coreNames.has(link.endpoint_a) && coreNames.has(link.endpoint_b));

    // Compute device coordinates: normalize from canvas layout with padding, or structured tiered layout
    const coords = {};
    const posMap = layout || {};

    const routers = coreDevices.filter(d => (d.type || "").toLowerCase() === "router");
    const switches = coreDevices.filter(d => (d.type || "").toLowerCase() === "switch" || (d.type || "").toLowerCase() === "accesspoint");
    const endpoints = coreDevices.filter(d => !routers.includes(d) && !switches.includes(d));

    // Calculate bounding box of existing layout coordinates
    const positioned = coreDevices.filter(d => posMap[d.name] && typeof posMap[d.name].x === "number" && typeof posMap[d.name].y === "number");
    if (positioned.length > 0) {
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        positioned.forEach(d => {
            const p = posMap[d.name];
            if (p.x < minX) minX = p.x;
            if (p.x > maxX) maxX = p.x;
            if (p.y < minY) minY = p.y;
            if (p.y > maxY) maxY = p.y;
        });

        const padX = 85;
        const padY = 75;
        const availW = Math.max(100, width - padX * 2);
        const availH = Math.max(100, height - padY * 2);
        const spanX = (maxX > minX) ? (maxX - minX) : 1;
        const spanY = (maxY > minY) ? (maxY - minY) : 1;

        coreDevices.forEach(d => {
            if (posMap[d.name] && typeof posMap[d.name].x === "number") {
                const normX = padX + ((posMap[d.name].x - minX) / spanX) * availW;
                const normY = padY + ((posMap[d.name].y - minY) / spanY) * availH;
                coords[d.name] = { x: Math.round(normX), y: Math.round(normY) };
            }
        });
    }

    // Auto fallback tiered layout for unpositioned devices
    coreDevices.forEach((d) => {
        if (!coords[d.name]) {
            if (routers.includes(d)) {
                const step = width / (routers.length + 1);
                coords[d.name] = { x: Math.round(step * (routers.indexOf(d) + 1)), y: 120 };
            } else if (switches.includes(d)) {
                const step = width / (switches.length + 1);
                coords[d.name] = { x: Math.round(step * (switches.indexOf(d) + 1)), y: 340 };
            } else {
                const step = width / (endpoints.length + 1);
                coords[d.name] = { x: Math.round(step * (endpoints.indexOf(d) + 1)), y: 560 };
            }
        }
    });

    let svgHtml = `<svg width="${width}" height="${height}" style="width: 100%; height: 100%; display: block;">`;

    // 1. Draw Links
    coreLinks.forEach(link => {
        const p1 = coords[link.endpoint_a];
        const p2 = coords[link.endpoint_b];
        if (p1 && p2) {
            svgHtml += `<line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" stroke="rgba(0, 229, 255, 0.3)" stroke-width="2.5" stroke-dasharray="5,3" />`;
        }
    });

    // 2. Draw Nodes
    coreDevices.forEach(d => {
        const pt = coords[d.name] || { x: width / 2, y: height / 2 };
        const type = (d.type || "pc").toUpperCase();
        const threat = d.soc_threat_level || "Normal";
        const isCompromised = (threat === "Compromised");
        const ringColor = isCompromised ? "var(--red)" : (threat === "Suspicious" ? "var(--orange)" : (d.status === "ONLINE" ? "var(--green)" : "var(--text-muted)"));
        const fillBg = isCompromised ? "rgba(239, 68, 68, 0.22)" : "#080c10";
        const strokeW = isCompromised ? "3.5" : "2.8";
        const glowStyle = isCompromised ? 'style="filter: drop-shadow(0 0 10px rgba(239, 68, 68, 0.9)); cursor: pointer;"' : 'style="cursor: pointer;"';
        const labelColor = isCompromised ? "var(--red)" : "#00e5ff";

        let iconSymbol = "🖥";
        if (type === "ROUTER") iconSymbol = "⬡";
        else if (type === "SWITCH") iconSymbol = "⊞";
        else if (type === "ACCESSPOINT") iconSymbol = "📡";
        else if (type === "SERVER" || type === "NAS") iconSymbol = "🖳";

        svgHtml += `
            <g class="topology-node" data-device-name="${d.name.replace(/"/g, '&quot;')}" ${glowStyle}>
                <circle cx="${pt.x}" cy="${pt.y}" r="24" fill="${fillBg}" stroke="${ringColor}" stroke-width="${strokeW}" />
                <text x="${pt.x}" y="${pt.y + 5}" font-size="15" text-anchor="middle" fill="${isCompromised ? '#ff8888' : '#d5ebf2'}" pointer-events="none">${iconSymbol}</text>
                <text x="${pt.x}" y="${pt.y + 38}" font-size="11" font-family="Courier New, monospace" text-anchor="middle" fill="${labelColor}" font-weight="bold" pointer-events="none">${d.name}</text>
            </g>
        `;
    });

    svgHtml += `</svg>`;
    container.innerHTML = svgHtml;

    // Attach Hover Tooltip Handlers
    const tooltip = document.getElementById("soc-node-tooltip");
    const nodeElements = container.querySelectorAll(".topology-node");

    nodeElements.forEach(el => {
        el.addEventListener("mouseenter", (e) => {
            const devName = el.dataset.deviceName;
            const dev = coreDevices.find(x => x.name === devName);
            if (!dev || !tooltip) return;

            const intfs = dev.interfaces || [];
            let intfHtml = intfs.map(i => `
                <div style="font-size: 0.75rem; margin-top: 3px; background: rgba(0,0,0,0.25); padding: 2px 6px; border-radius: 2px;">
                    <strong style="color: var(--cyan);">${i.name}:</strong> IP: <span style="color: #fff;">${i.ip || "None"}</span>${i.subnet_mask ? `/${i.subnet_mask}` : ""} | MAC: <span style="color: #94a3b8;">${i.mac || "-"}</span>
                </div>
            `).join("");

            let svcHtml = '<span style="color: var(--text-muted); font-style: italic;">None active</span>';
            if (dev.services && dev.services.length) {
                svcHtml = dev.services.map(s => {
                    if (typeof s === "object") {
                        const name = s.name || "SVC";
                        const isRun = (s.status || "").toLowerCase() === "running";
                        const dotColor = isRun ? "var(--green)" : "var(--yellow)";
                        const portStr = s.port ? ` <span style="opacity: 0.75; font-size: 0.7rem;">(${s.protocol || 'TCP'}/${s.port})</span>` : "";
                        return `<span style="background: rgba(255,255,255,0.06); border: 1px solid rgba(255,255,255,0.12); padding: 2px 6px; border-radius: 3px; font-size: 0.72rem; color: #d5ebf2; display: inline-block; margin-right: 4px; margin-top: 2px;">
                            <span style="color: ${dotColor}; margin-right: 4px;">●</span><strong>${name}</strong>${portStr}
                        </span>`;
                    }
                    return `<span style="background: rgba(255,255,255,0.06); padding: 2px 6px; border-radius: 3px; font-size: 0.72rem; color: #d5ebf2; display: inline-block; margin-right: 4px; margin-top: 2px;">${s}</span>`;
                }).join(" ");
            }

            const threatBadge = dev.soc_threat_level === "Compromised" ? `<span style="color: var(--red); font-weight: bold;">COMPROMISED</span>` : (dev.soc_threat_level === "Suspicious" ? `<span style="color: var(--orange); font-weight: bold;">SUSPICIOUS</span>` : `<span style="color: var(--green);">NORMAL</span>`);

            tooltip.innerHTML = `
                <div style="font-size: 1rem; font-weight: bold; color: white; border-bottom: 1px solid var(--border); padding-bottom: 0.35rem; margin-bottom: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
                    <span>${dev.name}</span>
                    <span style="font-size: 0.72rem; color: var(--cyan); background: rgba(0,229,255,0.1); padding: 1px 6px; border-radius: 2px;">${dev.type.toUpperCase()}</span>
                </div>
                <div style="font-size: 0.8rem; margin-bottom: 0.25rem;">Status: <strong style="color: ${dev.status === 'ONLINE' ? 'var(--green)' : 'var(--red)'};">${dev.status}</strong></div>
                <div style="font-size: 0.8rem; margin-bottom: 0.4rem;">Threat Posture: ${threatBadge}</div>
                <div style="margin-bottom: 0.5rem;">
                    <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 2px;">Interfaces (${intfs.length}):</div>
                    ${intfHtml || '<div style="font-size: 0.75rem; color: var(--text-muted); font-style: italic;">No interfaces configured</div>'}
                </div>
                <div>
                    <div style="font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; margin-bottom: 2px;">Active Daemons / Services:</div>
                    <div style="line-height: 1.5;">${svcHtml}</div>
                </div>
            `;
            tooltip.style.display = "block";
        });

        el.addEventListener("mousemove", (e) => {
            if (!tooltip) return;
            const tipWidth = tooltip.offsetWidth || 300;
            const tipHeight = tooltip.offsetHeight || 220;
            let left = e.clientX + 16;
            let top = e.clientY + 16;
            
            // Boundary-aware auto-flip if approaching viewport edges
            if (left + tipWidth > window.innerWidth - 12) {
                left = e.clientX - tipWidth - 16;
            }
            if (top + tipHeight > window.innerHeight - 12) {
                top = e.clientY - tipHeight - 16;
            }
            tooltip.style.left = `${Math.max(10, left)}px`;
            tooltip.style.top = `${Math.max(10, top)}px`;
        });

        el.addEventListener("mouseleave", () => {
            if (tooltip) tooltip.style.display = "none";
        });
    });
};

// ========================================================
// INCIDENTS TAB LOGIC (Chaining & Reporting)
// ========================================================

function renderEvidencePicker() {
    const picker = document.getElementById("incident-evidence-picker");
    const countEl = document.getElementById("incident-selected-count");
    if (!picker) return;

    const alerts = window.SOC.state.alerts || [];
    const events = window.SOC.state.events || [];
    const selectedIds = window.SOC.ui.selectedEvidenceIds || new Set();
    const selectedObjs = window.SOC.ui.selectedEvidenceObjects || new Map();

    if (alerts.length === 0 && events.length === 0 && selectedIds.size === 0) {
        picker.innerHTML = '<div style="color: var(--text-muted); font-style: italic;">No active security alerts or telemetry events to chain.</div>';
        if (countEl) countEl.textContent = `0 events selected for evidence timeline`;
        return;
    }

    let pickerHtml = "";

    // 1. PINNED / SELECTED EVIDENCE ITEMS (Preserved across all polls)
    if (selectedIds.size > 0) {
        pickerHtml += `<div class="evidence-pinned-header">PINNED EVIDENCE TIMELINE (${selectedIds.size})</div>`;
        selectedIds.forEach(id => {
            const item = selectedObjs.get(id) || alerts.find(a => a.id === id) || events.find(e => e.id === id) || { id, rule_name: "Selected Evidence", severity: "HIGH" };
            const sev = item.severity || "INFO";
            const name = item.rule_name || item.name || item.type || "Evidence Event";
            const src = item.source || item.event?.source || "unknown";
            const dst = item.destination || item.event?.destination || "unknown";
            pickerHtml += `
                <label style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem; cursor: pointer; color: #38bdf8; background: rgba(56, 189, 248, 0.08); padding: 3px 6px; border-radius: 3px;">
                    <input type="checkbox" value="${id}" checked onchange="toggleEvidenceSelection('${id}')">
                    <span><strong>[${sev}]</strong> ${name} &bull; <span style="color: var(--text-muted);">${src} &rarr; ${dst}</span></span>
                </label>
            `;
        });
        pickerHtml += `<div style="border-bottom: 1px solid rgba(255,255,255,0.08); margin: 6px 0;"></div>`;
    }

    // 2. AVAILABLE SECURITY ALERTS (Excluding already selected)
    const unselectedAlerts = alerts.filter(a => !selectedIds.has(a.id)).slice(0, 20);
    if (unselectedAlerts.length > 0) {
        pickerHtml += `<div style="font-size: 0.68rem; color: #94a3b8; margin-bottom: 4px; font-weight: 600;">AVAILABLE SECURITY ALERTS:</div>`;
        unselectedAlerts.forEach(a => {
            const src = a.event?.source || a.source || "unknown";
            const dst = a.event?.destination || a.destination || "unknown";
            pickerHtml += `
                <label style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem; cursor: pointer; color: #e2e8f0;">
                    <input type="checkbox" value="${a.id}" onchange="toggleEvidenceSelection('${a.id}')">
                    <span>[${a.severity}] ${a.rule_name} &bull; <span style="color: var(--text-muted);">${src} &rarr; ${dst}</span></span>
                </label>
            `;
        });
    }

    // 3. AVAILABLE TELEMETRY EVENTS (Excluding already selected)
    const unselectedEvents = events.filter(e => !selectedIds.has(e.id)).slice(0, 10);
    if (unselectedEvents.length > 0) {
        pickerHtml += `<div style="font-size: 0.68rem; color: #94a3b8; margin: 6px 0 4px 0; font-weight: 600;">RECENT INGESTED TELEMETRY:</div>`;
        unselectedEvents.forEach(e => {
            const src = e.source || "unknown";
            const dst = e.destination || "unknown";
            pickerHtml += `
                <label style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.35rem; cursor: pointer; color: #94a3b8;">
                    <input type="checkbox" value="${e.id}" onchange="toggleEvidenceSelection('${e.id}')">
                    <span>[${e.severity || 'INFO'}] ${e.type || 'EVENT'} &bull; <span style="color: var(--text-muted);">${src} &rarr; ${dst}</span></span>
                </label>
            `;
        });
    }

    picker.innerHTML = pickerHtml;
    if (countEl) countEl.textContent = `${selectedIds.size} events selected for evidence timeline`;
}

window.toggleEvidenceSelection = function(id) {
    if (!window.SOC.ui.selectedEvidenceObjects) {
        window.SOC.ui.selectedEvidenceObjects = new Map();
    }
    if (window.SOC.ui.selectedEvidenceIds.has(id)) {
        window.SOC.ui.selectedEvidenceIds.delete(id);
        window.SOC.ui.selectedEvidenceObjects.delete(id);
    } else {
        window.SOC.ui.selectedEvidenceIds.add(id);
        // Cache object details so it survives polling window shifts
        const alertObj = (window.SOC.state.alerts || []).find(a => a.id === id);
        if (alertObj) {
            window.SOC.ui.selectedEvidenceObjects.set(id, {
                id: alertObj.id,
                timestamp: alertObj.timestamp,
                rule_name: alertObj.rule_name || "Security Alert",
                severity: alertObj.severity || "HIGH",
                source: alertObj.event?.source || alertObj.source || "unknown",
                destination: alertObj.event?.destination || alertObj.destination || "unknown",
                type: alertObj.event?.type || "ALERT"
            });
        } else {
            const evObj = (window.SOC.state.events || []).find(e => e.id === id);
            if (evObj) {
                window.SOC.ui.selectedEvidenceObjects.set(id, {
                    id: evObj.id,
                    timestamp: evObj.timestamp,
                    rule_name: evObj.type || "TELEMETRY_EVENT",
                    severity: evObj.severity || "INFO",
                    source: evObj.source || "unknown",
                    destination: evObj.destination || "unknown",
                    type: evObj.type || "EVENT"
                });
            }
        }
    }
    renderEvidencePicker();
};

window.createIncident = async function() {
    const title = document.getElementById("incident-title")?.value?.trim();
    const severity = document.getElementById("incident-severity")?.value || "HIGH";
    const scope = document.getElementById("incident-scope")?.value?.trim() || "Network";
    const notes = document.getElementById("incident-notes")?.value?.trim();

    if (!title) {
        alert("Please provide an Incident Title.");
        return;
    }

    const selectedIds = Array.from(window.SOC.ui.selectedEvidenceIds);
    const chainedEvidence = selectedIds.map(id => {
        if (window.SOC.ui.selectedEvidenceObjects && window.SOC.ui.selectedEvidenceObjects.has(id)) {
            return window.SOC.ui.selectedEvidenceObjects.get(id);
        }
        const a = (window.SOC.state.alerts || []).find(x => x.id === id);
        if (a) {
            return {
                id: a.id,
                timestamp: a.timestamp,
                rule_name: a.rule_name,
                severity: a.severity,
                source: a.event?.source || a.source,
                destination: a.event?.destination || a.destination,
                type: a.event?.type || a.type
            };
        }
        return { id, rule_name: "Event Evidence", severity: "INFO" };
    });

    const incidentPayload = {
        title,
        severity,
        scope,
        notes: notes || "No notes provided.",
        status: "OPEN",
        evidence_ids: selectedIds,
        chained_evidence: chainedEvidence
    };

    const res = await apiRequest("POST", "/api/soc/incidents", incidentPayload);
    if (res && res.status === "success") {
        if (res.incident) {
            window.SOC.state.incidents.unshift(res.incident);
        }
        // Reset form
        document.getElementById("incident-title").value = "";
        document.getElementById("incident-notes").value = "";
        if (document.getElementById("incident-scope")) document.getElementById("incident-scope").value = "";
        window.SOC.ui.selectedEvidenceIds.clear();
        if (window.SOC.ui.selectedEvidenceObjects) {
            window.SOC.ui.selectedEvidenceObjects.clear();
        }
        renderEvidencePicker();
        renderIncidents();
    }
};

window.renderIncidents = function() {
    const list = document.getElementById("incidents-list");
    if (!list) return;

    const incidents = window.SOC.state.incidents || [];
    if (incidents.length === 0) {
        list.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 1.5rem; text-align: center;">No active incident investigations reported.</div>';
        return;
    }

    list.innerHTML = "";
    incidents.forEach(inc => {
        const item = document.createElement("div");
        const color = inc.severity === "CRITICAL" ? "var(--red)" : (inc.severity === "HIGH" ? "var(--orange)" : (inc.severity === "MEDIUM" ? "var(--yellow)" : "var(--cyan)"));
        item.style = `background: rgba(8, 12, 16, 0.85); padding: 1rem; margin-bottom: 1rem; border: 1px solid var(--border); border-left: 4px solid ${color}; border-radius: 4px;`;

        const evidence = inc.chained_evidence || [];
        let timelineHtml = "";
        if (evidence.length > 0) {
            timelineHtml = `
                <div style="margin-top: 0.75rem; background: var(--bg-main); padding: 0.6rem; border-radius: 3px; border: 1px solid var(--border);">
                    <div style="font-size: 0.75rem; color: var(--cyan); font-weight: bold; margin-bottom: 0.35rem;">EVIDENCE CHAIN TIMELINE (${evidence.length} events):</div>
                    ${evidence.map(e => `
                        <div style="font-size: 0.75rem; color: var(--text-main); margin-bottom: 2px;">
                            &bull; <span style="color: var(--text-muted);">${new Date(e.timestamp).toLocaleTimeString()}</span> [${e.severity}] <strong>${e.rule_name}</strong> - ${e.source} &rarr; ${e.destination}
                        </div>
                    `).join("")}
                </div>
            `;
        }

        item.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem; flex-wrap: wrap; gap: 0.5rem;">
                <div>
                    <strong style="color: white; font-size: 1.1rem;">${inc.title}</strong>
                    <span style="font-size: 0.75rem; padding: 2px 6px; border-radius: 3px; background: rgba(255,255,255,0.08); color: ${color}; border: 1px solid ${color}; margin-left: 0.5rem;">${inc.severity}</span>
                    <span style="font-size: 0.75rem; padding: 2px 6px; border-radius: 3px; background: rgba(0,229,255,0.1); color: var(--cyan); margin-left: 0.35rem;">${inc.status || "OPEN"}</span>
                    <span style="font-size: 0.72rem; padding: 2px 6px; border-radius: 3px; background: rgba(0,229,255,0.06); color: var(--cyan); border: 1px solid rgba(0,229,255,0.2); margin-left: 0.35rem;">LAB: ${(window.SOC.networkName || "CYBER HAZARD LAB").toUpperCase()}</span>
                    ${inc.scope ? `<span style="font-size: 0.75rem; padding: 2px 6px; border-radius: 3px; background: rgba(160,174,192,0.15); color: #cbd5e1; margin-left: 0.35rem;">Scope: ${inc.scope}</span>` : ""}
                    <span style="color: var(--text-muted); font-size: 0.8rem; margin-left: 0.5rem;">${new Date(inc.timestamp).toLocaleString()}</span>
                </div>
                <div style="display: flex; gap: 0.4rem; align-items: center;">
                    <button onclick="downloadIncidentPDF('${inc.id}')" title="Generate Formatted Incident PDF Document" style="background: rgba(0,229,255,0.12); border: 1px solid var(--cyan); color: var(--cyan); padding: 0.25rem 0.6rem; font-size: 0.75rem; cursor: pointer; border-radius: 3px; font-weight: bold; display: flex; align-items: center; gap: 4px; transition: 0.15s;">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                        PDF
                    </button>
                    <button onclick="openEditIncidentModal('${inc.id}')" title="Edit Incident Details or Fix Typos" style="background: rgba(255,170,0,0.12); border: 1px solid var(--yellow); color: var(--yellow); padding: 0.25rem 0.6rem; font-size: 0.75rem; cursor: pointer; border-radius: 3px; font-weight: bold; display: flex; align-items: center; gap: 4px; transition: 0.15s;">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                        EDIT
                    </button>
                    <button onclick="deleteIncident('${inc.id}')" title="Delete Incident Case" style="background: transparent; border: 1px solid var(--red); color: var(--red); padding: 0.25rem 0.5rem; font-size: 0.75rem; cursor: pointer; border-radius: 3px;">
                        DELETE
                    </button>
                </div>
            </div>
            <div style="color: #cbd5e1; font-size: 0.85rem; white-space: pre-wrap; margin-top: 0.35rem;">${inc.notes}</div>
            ${timelineHtml}
        `;
        list.appendChild(item);
    });
};

window.downloadIncidentPDF = function(id) {
    const url = `/api/soc/incidents/${encodeURIComponent(id)}/pdf`;
    window.open(url, "_blank");
};

window.openEditIncidentModal = function(id) {
    const inc = (window.SOC.state.incidents || []).find(i => i.id === id);
    if (!inc) return;

    document.getElementById("edit-incident-id").value = inc.id;
    document.getElementById("edit-incident-title").value = inc.title || "";
    document.getElementById("edit-incident-severity").value = inc.severity || "MEDIUM";
    document.getElementById("edit-incident-status").value = inc.status || "OPEN";
    document.getElementById("edit-incident-scope").value = inc.scope || "";
    document.getElementById("edit-incident-notes").value = inc.notes || "";

    const modal = document.getElementById("edit-incident-modal");
    if (modal) modal.style.display = "flex";
};

window.closeEditIncidentModal = function() {
    const modal = document.getElementById("edit-incident-modal");
    if (modal) modal.style.display = "none";
};

window.saveIncidentEdit = async function() {
    const id = document.getElementById("edit-incident-id").value;
    if (!id) return;

    const payload = {
        title: document.getElementById("edit-incident-title").value.trim(),
        severity: document.getElementById("edit-incident-severity").value,
        status: document.getElementById("edit-incident-status").value,
        scope: document.getElementById("edit-incident-scope").value.trim(),
        notes: document.getElementById("edit-incident-notes").value.trim()
    };

    if (!payload.title) {
        alert("Incident title cannot be empty.");
        return;
    }

    const res = await apiRequest("PUT", `/api/soc/incidents/${encodeURIComponent(id)}`, payload);
    if (res && res.status === "success") {
        const idx = (window.SOC.state.incidents || []).findIndex(i => i.id === id);
        if (idx !== -1) {
            window.SOC.state.incidents[idx] = res.incident;
        }
        closeEditIncidentModal();
        renderIncidents();
    } else {
        alert("Failed to update incident: " + (res && res.error ? res.error : "Unknown error"));
    }
};

window.deleteIncident = async function(id) {
    await apiRequest("DELETE", `/api/soc/incidents/${encodeURIComponent(id)}`);
    window.SOC.state.incidents = window.SOC.state.incidents.filter(i => i.id !== id);
    renderIncidents();
};

// ========================================================
// DETECTION RULES TAB LOGIC
// ========================================================

// ========================================================
// YAML DETECTION RULES LOGIC
// ========================================================

window.RULE_TEMPLATES = {
    "reverse-shell": `id: rule-netcat-reverse-shell
title: Netcat Reverse Shell Execution
description: Detects interactive shell execution spawned via netcat or ncat
severity: CRITICAL
status: production
detection:
  selection_cmd:
    type: COMMAND_EXECUTED
    command|contains:
      - "nc "
      - "netcat"
      - "ncat"
    command|contains_all:
      - "-e"
  selection_netcat_sh:
    command|contains:
      - "nc -e"
      - "netcat -e"
      - "/bin/bash"
      - "/bin/sh"
  condition: selection_cmd or selection_netcat_sh`,

    "arp-spoof": `id: rule-arp-spoofing
title: ARP Poisoning / Spoofing Activity
description: Detects execution of ARP spoofing tools or IP-MAC cache conflicts
severity: CRITICAL
status: production
detection:
  selection_tool:
    type: COMMAND_EXECUTED
    command|contains:
      - "arpspoof"
      - "ettercap"
      - "bettercap"
  selection_cache_conflict:
    type: ARP_REPLY
    metadata.conflict: true
  condition: selection_tool or selection_cache_conflict`,

    "ssh-brute-force": `id: rule-ssh-brute-force
title: SSH Brute Force Attack
description: 3 or more SSH authentication failures from the same source within 60 seconds
severity: CRITICAL
status: production
detection:
  selection:
    type: SSH_AUTH_FAILED
  aggregation:
    operator: ">="
    threshold: 3
    timeframe: 60s
    by: source
  condition: selection`,

    "port-scan": `id: rule-port-scan
title: Network Port Scanning
description: Detects network port scanning tools (nmap) or rapid multi-port probes
severity: HIGH
status: production
detection:
  selection_tool:
    type: COMMAND_EXECUTED
    command|contains:
      - "nmap"
  selection_probes:
    protocol:
      - TCP
      - SYN
  filter_dns:
    metadata.payload|contains: "dns_health"
  aggregation:
    field: dest_port
    distinct: true
    operator: ">="
    threshold: 4
    timeframe: 15s
    by: source
  condition: selection_tool or (selection_probes and not filter_dns)`,

    "icmp-sweep": `id: rule-icmp-sweep
title: ICMP Reconnaissance Sweep
description: Detects ICMP ping sweep targeting 4 or more distinct destinations within 15 seconds
severity: MEDIUM
status: production
detection:
  selection_icmp:
    protocol: ICMP
  filter_dns_health:
    metadata.payload|contains: "dns_health"
  aggregation:
    field: destination
    distinct: true
    operator: ">="
    threshold: 4
    timeframe: 15s
    by: source
  condition: selection_icmp and not filter_dns_health`,

    "root-privesc": `id: rule-root-privilege-escalation
title: Direct Root Login / Privilege Escalation
description: Superuser privilege escalation via su/sudo or direct root login
severity: CRITICAL
status: production
detection:
  selection_su:
    type: COMMAND_EXECUTED
    command|contains:
      - "sudo su"
      - "sudo -i"
      - "su -"
      - "su root"
  selection_ssh_root:
    type: SSH_AUTH_SUCCESS
    metadata.user: root
  selection_root_event:
    type: ROOT_LOGIN
  condition: selection_su or selection_ssh_root or selection_root_event`,

    "custom": `id: rule-custom-detection
title: Custom Security Detection Rule
description: Brief explanation of threat or anomalous behavior detected
severity: HIGH
status: experimental
detection:
  selection:
    type: COMMAND_EXECUTED
    command|contains: "suspicious_keyword"
  condition: selection`
};

window.loadRuleTemplate = function(key) {
    const editor = document.getElementById("rule-yaml-editor");
    const status = document.getElementById("rule-validation-status");
    if (status) status.style.display = "none";
    if (editor && window.RULE_TEMPLATES[key]) {
        editor.value = window.RULE_TEMPLATES[key];
    }
};

window.validateCurrentRule = async function() {
    const editor = document.getElementById("rule-yaml-editor");
    const status = document.getElementById("rule-validation-status");
    if (!editor || !status) return;

    const yamlText = editor.value.trim();
    if (!yamlText) {
        status.style.display = "block";
        status.style.background = "rgba(255, 75, 75, 0.15)";
        status.style.border = "1px solid var(--red)";
        status.style.color = "var(--red)";
        status.innerHTML = "[ERROR] YAML editor is empty. Enter a detection rule or select a template.";
        return false;
    }

    try {
        const res = await apiRequest("POST", "/api/soc/rules/validate", { yaml: yamlText });
        status.style.display = "block";
        if (res && res.valid) {
            status.style.background = "rgba(0, 230, 118, 0.12)";
            status.style.border = "1px solid var(--green)";
            status.style.color = "var(--green)";
            status.innerHTML = `[VALID] Rule syntax valid: <strong>${res.rule.title}</strong> [${res.rule.severity}] (${res.rule.id})`;
            return true;
        } else {
            status.style.background = "rgba(255, 75, 75, 0.15)";
            status.style.border = "1px solid var(--red)";
            status.style.color = "var(--red)";
            status.innerHTML = `[SYNTAX ERROR] ${res.error || "Failed to validate rule schema."}`;
            return false;
        }
    } catch (e) {
        status.style.display = "block";
        status.style.background = "rgba(255, 75, 75, 0.15)";
        status.style.border = "1px solid var(--red)";
        status.style.color = "var(--red)";
        status.innerHTML = `[ERROR] Validation request failed: ${e.message}`;
        return false;
    }
};

window.saveCurrentRule = async function() {
    const editor = document.getElementById("rule-yaml-editor");
    const status = document.getElementById("rule-validation-status");
    if (!editor) return;

    const yamlText = editor.value.trim();
    if (!yamlText) {
        alert("Please enter a YAML rule or select a template.");
        return;
    }

    try {
        const res = await apiRequest("POST", "/api/soc/rules", { yaml: yamlText });
        if (res && res.status === "success" && res.rule) {
            if (status) {
                status.style.display = "block";
                status.style.background = "rgba(0, 230, 118, 0.15)";
                status.style.border = "1px solid var(--green)";
                status.style.color = "var(--green)";
                status.innerHTML = `[SUCCESS] Deployed rule: <strong>${res.rule.name || res.rule.title}</strong> [${res.rule.severity}]`;
            }

            // Update in-memory state
            const existingIdx = window.SOC.state.rules.findIndex(r => r.id === res.rule.id);
            if (existingIdx !== -1) {
                window.SOC.state.rules[existingIdx] = res.rule;
            } else {
                window.SOC.state.rules.push(res.rule);
            }

            renderRules();
        } else {
            if (status) {
                status.style.display = "block";
                status.style.background = "rgba(255, 75, 75, 0.15)";
                status.style.border = "1px solid var(--red)";
                status.style.color = "var(--red)";
                status.innerHTML = `[DEPLOY FAILED] ${res.message || "Could not deploy rule."}`;
            }
        }
    } catch (e) {
        alert("Failed to save rule: " + e.message);
    }
};

window.editRuleInBuilder = function(id) {
    const rule = (window.SOC.state.rules || []).find(r => r.id === id);
    if (!rule) return;

    const editor = document.getElementById("rule-yaml-editor");
    if (editor) {
        editor.value = rule.yaml || `id: ${rule.id}\ntitle: "${rule.name}"\nseverity: ${rule.severity}\ndescription: "${rule.description || ''}"\ndetection:\n  condition: selection\n`;
        editor.scrollIntoView({ behavior: 'smooth', block: 'center' });
        editor.focus();
    }
};

window.toggleRuleYamlView = function(id) {
    const drawer = document.getElementById(`rule-drawer-${id}`);
    const btn = document.getElementById(`rule-btn-${id}`);
    if (!drawer) return;

    if (drawer.style.display === "none" || !drawer.style.display) {
        drawer.style.display = "block";
        if (btn) btn.innerText = "HIDE YAML";
    } else {
        drawer.style.display = "none";
        if (btn) btn.innerText = "VIEW YAML";
    }
};

window.renderRules = function() {
    const list = document.getElementById("rules-list");
    if (!list) return;

    list.innerHTML = "";
    const rules = window.SOC.state.rules || [];

    const badge = document.getElementById("rules-count-badge");
    if (badge) badge.innerText = `${rules.length} RULES`;

    if (rules.length === 0) {
        list.innerHTML = '<div style="color: var(--text-muted); font-style: italic; padding: 1rem; background: rgba(0,0,0,0.2); border: 1px solid var(--border); border-radius: 4px;">No detection rules configured. Select a template below to deploy your first rule.</div>';
        return;
    }

    rules.forEach((rule) => {
        const item = document.createElement("div");
        const color = rule.severity === 'CRITICAL' ? 'var(--red)' : (rule.severity === 'HIGH' ? 'var(--orange)' : (rule.severity === 'MEDIUM' ? 'var(--yellow)' : 'var(--cyan)'));
        item.style = `background: rgba(8, 12, 16, 0.85); padding: 0.85rem; margin-bottom: 0.6rem; border: 1px solid var(--border); border-left: 3px solid ${color}; border-radius: 4px;`;

        const ruleYaml = rule.yaml || `id: ${rule.id}\ntitle: "${rule.name || rule.title}"\nseverity: ${rule.severity}\ndescription: "${rule.description || ''}"\n`;

        item.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem;">
                <div style="flex: 1;">
                    <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
                        <strong style="color: white; font-size: 0.95rem;">${rule.title || rule.name}</strong> 
                        <span style="font-size: 0.7rem; color: ${color}; font-weight: bold; background: rgba(255,255,255,0.05); padding: 1px 6px; border-radius: 2px; border: 1px solid ${color};">[${rule.severity}]</span>
                        <span style="font-size: 0.7rem; color: var(--text-muted); font-family: monospace;">${rule.id}</span>
                    </div>
                    ${rule.description ? `<div style="font-size: 0.78rem; color: var(--text-muted); margin-top: 0.3rem;">${rule.description}</div>` : ""}
                </div>
                <div style="display: flex; gap: 0.4rem; align-items: center;">
                    <button id="rule-btn-${rule.id}" onclick="toggleRuleYamlView('${rule.id}')" style="background: rgba(255,255,255,0.05); border: 1px solid var(--border); color: #cbd5e1; padding: 0.3rem 0.6rem; cursor: pointer; border-radius: 3px; font-size: 0.75rem; font-family: monospace;">VIEW YAML</button>
                    <button onclick="editRuleInBuilder('${rule.id}')" style="background: rgba(0, 229, 255, 0.1); border: 1px solid var(--cyan); color: var(--cyan); padding: 0.3rem 0.6rem; cursor: pointer; border-radius: 3px; font-size: 0.75rem; font-family: monospace;">EDIT</button>
                    <button onclick="deleteRule('${rule.id}')" style="background: transparent; border: 1px solid var(--red); color: var(--red); padding: 0.3rem 0.6rem; cursor: pointer; border-radius: 3px; font-size: 0.75rem; font-family: monospace;">DELETE</button>
                </div>
            </div>

            <!-- COLLAPSIBLE YAML VIEW -->
            <div id="rule-drawer-${rule.id}" style="display: none; margin-top: 0.75rem; padding: 0.75rem; background: #04070c; border: 1px solid rgba(255,255,255,0.06); border-radius: 3px;">
                <div style="font-size: 0.7rem; color: var(--text-muted); margin-bottom: 0.4rem; letter-spacing: 0.5px;">SIGMA YAML DEFINITION:</div>
                <pre style="margin: 0; font-family: monospace; font-size: 0.8rem; color: #00e676; line-height: 1.4; white-space: pre-wrap;">${escapeHtml(ruleYaml)}</pre>
            </div>
        `;
        list.appendChild(item);
    });
};

function escapeHtml(str) {
    if (!str) return "";
    return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

window.deleteRule = async function(id) {
    if (!confirm("Are you sure you want to delete this detection rule?")) return;
    await apiRequest("DELETE", `/api/soc/rules/${encodeURIComponent(id)}`);
    window.SOC.state.rules = window.SOC.state.rules.filter(r => r.id !== id);
    renderRules();
};

// ========================================================
// SETTINGS TAB LOGIC
// ========================================================

window.loadSIEMSettings = function() {
    const settings = window.SOC.state.settings || {};
    const portEl = document.getElementById("setting-collector-port");
    const transEl = document.getElementById("setting-transport");
    const retEl = document.getElementById("setting-retention");
    const autoEl = document.getElementById("setting-auto-contain");
    const beepEl = document.getElementById("setting-alert-beep");

    if (portEl && settings.collector_port) portEl.value = settings.collector_port;
    if (transEl && settings.transport) transEl.value = settings.transport;
    if (retEl && settings.retention_hours) retEl.value = settings.retention_hours;
    if (autoEl && settings.auto_containment !== undefined) autoEl.checked = !!settings.auto_containment;
    if (beepEl) {
        const storedBeep = localStorage.getItem("SOC_ALERT_BEEP");
        beepEl.checked = storedBeep !== null ? (storedBeep === "true") : (settings.alert_beep !== false);
    }
};

window.saveSIEMSettings = async function() {
    const portEl = document.getElementById("setting-collector-port");
    const transEl = document.getElementById("setting-transport");
    const retEl = document.getElementById("setting-retention");
    const autoEl = document.getElementById("setting-auto-contain");
    const beepEl = document.getElementById("setting-alert-beep");

    const alertBeepVal = beepEl ? beepEl.checked : true;
    localStorage.setItem("SOC_ALERT_BEEP", alertBeepVal ? "true" : "false");

    const payload = {
        collector_port: portEl ? parseInt(portEl.value) : 514,
        transport: transEl ? transEl.value : "UDP",
        retention_hours: retEl ? parseInt(retEl.value) : 24,
        auto_containment: autoEl ? autoEl.checked : false,
        alert_beep: alertBeepVal
    };

    const res = await apiRequest("POST", "/api/soc/settings", payload);
    if (res && res.status === "success") {
        window.SOC.state.settings = res.settings;
        alert("SIEM settings saved successfully.");
    }
};

// ========================================================
// TRAFFIC, HOSTS & PCAP
// ========================================================

let trafficChartMain = null;
const subCharts = {}; 
window.SOC.telemetryHistory = { 
    "ALL": { traffic: [], eventRate: [] }, 
    devices: {},
    labels: [] 
};
const MAX_HISTORY = 60;

function initTrafficChartMain() {
    const ctx = document.getElementById('trafficChartMain');
    if (!ctx) return;
    
    trafficChartMain = new Chart(ctx, {
        type: 'line',
        data: {
            labels: window.SOC.telemetryHistory.labels,
            datasets: [
                { 
                    label: 'Network Throughput (pkts/s)', 
                    data: window.SOC.telemetryHistory["ALL"].traffic, 
                    borderColor: '#00e5ff', 
                    backgroundColor: 'rgba(0, 229, 255, 0.08)', 
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    fill: true, 
                    tension: 0.3 
                },
                { 
                    label: 'Event Ingestion Rate (events/s)', 
                    data: window.SOC.telemetryHistory["ALL"].eventRate, 
                    borderColor: '#00e676', 
                    backgroundColor: 'rgba(0, 230, 118, 0.08)', 
                    borderWidth: 1.5,
                    pointRadius: 0,
                    pointHoverRadius: 4,
                    fill: true, 
                    tension: 0.3 
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { 
                    ticks: { color: '#64748b', maxTicksLimit: 8, font: { size: 10 } }, 
                    grid: { color: 'rgba(255, 255, 255, 0.04)' } 
                },
                y: { 
                    ticks: { color: '#64748b', font: { size: 10 } }, 
                    grid: { color: 'rgba(255, 255, 255, 0.04)' }, 
                    beginAtZero: true 
                }
            },
            plugins: {
                legend: { 
                    labels: { color: '#cbd5e1', font: { size: 11 }, boxWidth: 12 } 
                }
            }
        }
    });
}

window.toggleTrafficDropdown = function(e) {
    if (e) e.stopPropagation();
    const listEl = document.getElementById("traffic-dropdown-list");
    if (!listEl) return;
    const isVisible = listEl.style.display === "block";
    listEl.style.display = isVisible ? "none" : "block";
    if (!isVisible) {
        populateTrafficDropdown(window.SOC.state.devices || []);
    }
};

document.addEventListener("click", (e) => {
    const listEl = document.getElementById("traffic-dropdown-list");
    const btnEl = document.getElementById("traffic-dropdown-btn");
    if (listEl && listEl.style.display === "block") {
        if (!listEl.contains(e.target) && !btnEl.contains(e.target)) {
            listEl.style.display = "none";
        }
    }
});

function populateTrafficDropdown(devices) {
    const listEl = document.getElementById("traffic-dropdown-list");
    if (!listEl || !Array.isArray(devices)) return;
    listEl.innerHTML = "";
    
    // Filter out laptops if any, keep routers, servers, hosts
    const activeDevices = devices.filter(d => (d.type || "").toLowerCase() !== "laptop");
    if (activeDevices.length === 0) {
        listEl.innerHTML = '<div style="padding: 0.6rem; color: #64748b; font-size: 0.75rem;">No devices available</div>';
        return;
    }

    activeDevices.forEach(dev => {
        const isSelected = !!subCharts[dev.name];
        const item = document.createElement("div");
        item.className = `traffic-dropdown-item ${isSelected ? "active" : ""}`;
        
        const devType = (dev.type || "HOST").toUpperCase();
        item.innerHTML = `
            <div class="traffic-dropdown-device-info">
                <span class="traffic-dropdown-dot"></span>
                <span class="traffic-dropdown-name">${dev.name}</span>
                <span class="traffic-dropdown-badge">${devType}</span>
            </div>
            <div style="font-size: 0.75rem; color: ${isSelected ? '#00e5ff' : '#64748b'}; font-weight: bold;">
                ${isSelected ? "ACTIVE" : "+ ADD"}
            </div>
        `;
        item.onclick = (e) => {
            e.stopPropagation();
            toggleDeviceSubChart(dev.name);
            populateTrafficDropdown(devices);
        };
        listEl.appendChild(item);
    });
}

function toggleDeviceSubChart(devName) {
    const container = document.getElementById("sub-charts-container");
    if (!container) return;

    if (subCharts[devName]) {
        // Destroy existing
        subCharts[devName].chart.destroy();
        const card = document.getElementById(`subchart-card-${devName.replace(/\s+/g, "_")}`);
        if (card) card.remove();
        delete subCharts[devName];
        return;
    }

    // Create new sub-chart card
    const card = document.createElement("div");
    card.id = `subchart-card-${devName.replace(/\s+/g, "_")}`;
    card.className = "subchart-card";
    
    card.innerHTML = `
        <div class="subchart-header">
            <span class="subchart-title">
                <span style="display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: #38bdf8;"></span>
                ${devName} TELEMETRY
            </span>
            <button class="subchart-close-btn" onclick="toggleDeviceSubChart('${devName.replace(/'/g, "\\'")}')" title="Remove Graph">&times;</button>
        </div>
        <div style="flex: 1; position: relative; width: 100%; min-height: 0;">
            <canvas id="subchart-canvas-${devName.replace(/\s+/g, "_")}"></canvas>
        </div>
    `;
    container.appendChild(card);

    const canvas = document.getElementById(`subchart-canvas-${devName.replace(/\s+/g, "_")}`);
    const chart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { 
                    label: 'TX (pkts/s)', 
                    data: [], 
                    borderColor: '#00e5ff', 
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.3 
                },
                { 
                    label: 'RX (pkts/s)', 
                    data: [], 
                    borderColor: '#00e676', 
                    borderWidth: 1.5,
                    pointRadius: 0,
                    tension: 0.3 
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: false },
                y: { ticks: { color: '#64748b', font: { size: 9 } }, grid: { color: 'rgba(255,255,255,0.04)' }, beginAtZero: true }
            },
            plugins: { 
                legend: { labels: { color: '#94a3b8', boxWidth: 8, font: { size: 9 } } } 
            }
        }
    });

    subCharts[devName] = { chart, lastTx: 0, lastRx: 0, labels: [], tx: [], rx: [] };
}

function updateSubCharts(telemetry, now, dt) {
    Object.keys(subCharts).forEach(devName => {
        const sc = subCharts[devName];
        const devTelem = telemetry ? telemetry[devName] : null;
        let curTx = devTelem ? (devTelem.tx_packets || 0) : 0;
        let curRx = devTelem ? (devTelem.rx_packets || 0) : 0;

        let txRate = sc.lastTx !== undefined ? Math.max(0, (curTx - sc.lastTx) / dt) : 0;
        let rxRate = sc.lastRx !== undefined ? Math.max(0, (curRx - sc.lastRx) / dt) : 0;
        sc.lastTx = curTx;
        sc.lastRx = curRx;

        sc.labels.push(now);
        sc.tx.push(parseFloat(txRate.toFixed(1)));
        sc.rx.push(parseFloat(rxRate.toFixed(1)));

        if (sc.labels.length > 30) {
            sc.labels.shift();
            sc.tx.shift();
            sc.rx.shift();
        }

        sc.chart.data.labels = sc.labels;
        sc.chart.data.datasets[0].data = sc.tx;
        sc.chart.data.datasets[1].data = sc.rx;
        sc.chart.update();
    });
}

function updateTrafficView(telemetry) {
    if (!trafficChartMain) return;
    const now = new Date().toLocaleTimeString();

    // 1. Compute Network Packet Rate
    let currentTotalPkts = 0;
    if (telemetry && typeof telemetry === "object") {
        Object.values(telemetry).forEach(dev => {
            currentTotalPkts += (dev.tx_packets || 0) + (dev.rx_packets || 0);
        });
    }

    const nowTime = Date.now();
    const dt = window.SOC._lastTrafficTime ? Math.max(0.5, (nowTime - window.SOC._lastTrafficTime) / 1000) : 1;
    window.SOC._lastTrafficTime = nowTime;

    let pktRate = 0;
    if (window.SOC._lastTotalPkts !== undefined) {
        pktRate = Math.max(0, (currentTotalPkts - window.SOC._lastTotalPkts) / dt);
    }
    window.SOC._lastTotalPkts = currentTotalPkts;

    // 2. Compute Event Ingestion Rate
    const currentTotalEvents = window.SOC.metrics.total_events || 0;
    let evRate = 0;
    if (window.SOC._lastTotalEvents !== undefined) {
        evRate = Math.max(0, (currentTotalEvents - window.SOC._lastTotalEvents) / dt);
    }
    window.SOC._lastTotalEvents = currentTotalEvents;

    window.SOC.telemetryHistory.labels.push(now);
    window.SOC.telemetryHistory["ALL"].traffic.push(parseFloat(pktRate.toFixed(1)));
    window.SOC.telemetryHistory["ALL"].eventRate.push(parseFloat(evRate.toFixed(1)));

    if (window.SOC.telemetryHistory.labels.length > MAX_HISTORY) {
        window.SOC.telemetryHistory.labels.shift();
        window.SOC.telemetryHistory["ALL"].traffic.shift();
        window.SOC.telemetryHistory["ALL"].eventRate.shift();
    }
    trafficChartMain.update();

    // Update active sub-charts
    updateSubCharts(telemetry, now, dt);
}

function updateHostsView(devices) {
    const tbody = document.getElementById("hosts-table-body");
    if (!tbody || !devices || !Array.isArray(devices)) return;
    
    tbody.innerHTML = "";
    devices.forEach(d => {
        const tr = document.createElement("tr");
        tr.style.borderBottom = "1px solid var(--border)";
        
        const statusColor = d.status === "ONLINE" ? "var(--green)" : (d.status === "PAUSED" ? "var(--yellow)" : "var(--red)");
        const threatColor = d.soc_threat_level === "Compromised" ? "var(--red)" : (d.soc_threat_level === "Suspicious" ? "var(--orange)" : "var(--green)");
        
        tr.innerHTML = `
            <td style="padding: 0.6rem; color: white; font-weight: bold;">${d.name}</td>
            <td style="padding: 0.6rem; color: var(--text-main); text-transform: uppercase;">${d.type}</td>
            <td style="padding: 0.6rem; color: ${statusColor}; font-weight: bold;">${d.status}</td>
            <td style="padding: 0.6rem;">
                <select onchange="updateDeviceThreat('${d.name.replace(/'/g, "\\'")}', this.value)" style="background: var(--bg-main); border: 1px solid ${threatColor}; color: ${threatColor}; padding: 0.2rem 0.5rem; border-radius: 3px;">
                    <option value="Normal" ${d.soc_threat_level === 'Normal' ? 'selected' : ''}>Normal</option>
                    <option value="Suspicious" ${d.soc_threat_level === 'Suspicious' ? 'selected' : ''}>Suspicious</option>
                    <option value="Compromised" ${d.soc_threat_level === 'Compromised' ? 'selected' : ''}>Compromised</option>
                </select>
            </td>
            <td style="padding: 0.6rem;">
                <button onclick="containDevice('${d.name.replace(/'/g, "\\'")}', 'pause')" style="background: transparent; border: 1px solid var(--yellow); color: var(--yellow); padding: 0.2rem 0.5rem; cursor: pointer; border-radius: 3px; margin-right: 0.35rem;">PAUSE</button>
                <button onclick="containDevice('${d.name.replace(/'/g, "\\'")}', 'isolate')" style="background: transparent; border: 1px solid var(--red); color: var(--red); padding: 0.2rem 0.5rem; cursor: pointer; border-radius: 3px; margin-right: 0.35rem;">ISOLATE</button>
                <button onclick="containDevice('${d.name.replace(/'/g, "\\'")}', 'reconnect')" style="background: transparent; border: 1px solid var(--green); color: var(--green); padding: 0.2rem 0.5rem; cursor: pointer; border-radius: 3px;">RECONNECT</button>
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

window.renderPcap = function(devices) {
    const tbody = document.getElementById("pcap-table-body");
    if (!tbody || !devices) return;
    
    tbody.innerHTML = "";
    devices.forEach(d => {
        if (d.type === "switch") return;
        if (!d.interfaces || d.interfaces.length === 0) return;
        
        d.interfaces.forEach(intf => {
            const tr = document.createElement("tr");
            tr.style.borderBottom = "1px solid var(--border)";
            const dlLink = `/api/ncm/devices/${encodeURIComponent(d.name)}/interfaces/${encodeURIComponent(intf.name)}/pcap`;
            
            tr.innerHTML = `
                <td style="padding: 0.6rem; color: white;">${d.name}</td>
                <td style="padding: 0.6rem; color: var(--text-main);">${intf.name}</td>
                <td style="padding: 0.6rem;">
                    <a href="${dlLink}" download="${d.name}_${intf.name}.pcap" style="background: transparent; border: 1px solid var(--cyan); color: var(--cyan); padding: 0.2rem 0.6rem; text-decoration: none; cursor: pointer; border-radius: 3px; font-size: 0.8rem;">DOWNLOAD PCAP</a>
                </td>
            `;
            tbody.appendChild(tr);
        });
    });
};

let alertsPieChart = null;

window.updateAlertsPie = function() {
    const timeVal = document.getElementById("alerts-pie-time") ? document.getElementById("alerts-pie-time").value : "60";
    const ctx = document.getElementById("alertsPieChart");
    if (!ctx) return;
    
    const now = new Date();
    const alerts = window.SOC.state.alerts || [];
    const filteredAlerts = alerts.filter(a => {
        if (timeVal === "all") return true;
        const diffMs = now - new Date(a.timestamp);
        return (diffMs / 60000) <= parseInt(timeVal);
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
                    borderColor: '#05070a'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { color: 'white', boxWidth: 12, font: { size: 10 } } }
                }
            }
        });
    }
};

// ========================================================
// MAIN POLLING LOOP
// ========================================================

async function pollSOC() {
    const [events, telemetry, ntmData, links, layout, settings] = await Promise.all([
        apiRequest("GET", "/api/soc/events"),
        apiRequest("GET", "/api/simulation/telemetry"),
        apiRequest("GET", "/api/ntm/devices"),
        apiRequest("GET", "/api/ntm/links"),
        apiRequest("GET", "/api/ntm/layout"),
        apiRequest("GET", "/api/simulation/settings")
    ]);

    if (settings && settings.network_name) {
        window.SOC.networkName = settings.network_name;
        const brandEl = document.getElementById("soc-brand-title");
        if (brandEl) brandEl.textContent = settings.network_name.toUpperCase();
        const sessEl = document.getElementById("soc-simulation-name");
        if (sessEl) sessEl.innerHTML = `LAB: <strong>${settings.network_name.toUpperCase()}</strong>`;
        document.title = `${settings.network_name} // SOC LAB`;
    }

    await loadSOCState();

    // Attacker laptops are strictly outside the defended perimeter and excluded from SOC monitoring
    const defendedDevices = (ntmData || []).filter(d => !d.is_attacker);

    window.SOC.cache = {
        ntmData: defendedDevices,
        links: links || [],
        layout: layout || {}
    };

    const currentEvents = (events && Array.isArray(events)) ? events : (window.SOC.state.events || []);
    updateOverviewMetrics(currentEvents, telemetry || {}, defendedDevices);
    
    if (typeof populateTrafficDropdown === "function") populateTrafficDropdown(defendedDevices);
    if (typeof updateTrafficView === "function") updateTrafficView(telemetry || {});
    if (typeof updateHostsView === "function") updateHostsView(defendedDevices);
    if (typeof renderPcap === "function") renderPcap(defendedDevices);
    if (typeof renderNetworkTopology === "function") renderNetworkTopology(defendedDevices, links || [], layout || {});
    if (typeof renderAlerts === "function") renderAlerts();
    if (typeof renderEvidencePicker === "function") renderEvidencePicker();
    if (typeof updateAlertsPie === "function") updateAlertsPie();
    if (typeof checkNewThreatAlerts === "function") checkNewThreatAlerts(window.SOC.state.alerts || []);
}

// ========================================================
// INITIALIZATION
// ========================================================

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

        if (viewName === "network") {
            if (window.SOC.cache && window.SOC.cache.ntmData) {
                renderNetworkTopology(window.SOC.cache.ntmData, window.SOC.cache.links, window.SOC.cache.layout);
            }
        }
        if (viewName === "settings") loadSIEMSettings();
        if (viewName === "rules") renderRules();
        if (viewName === "incidents") { renderIncidents(); renderEvidencePicker(); }
        if (viewName === "alerts") renderAlerts();
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

    // Alert filter event listeners
    const searchInput = document.getElementById("alerts-search-input");
    if (searchInput) {
        searchInput.addEventListener("input", (e) => {
            window.SOC.ui.searchTerm = e.target.value;
            renderAlerts();
        });
    }

    const statusFilter = document.getElementById("alerts-status-filter");
    if (statusFilter) {
        statusFilter.addEventListener("change", (e) => {
            window.SOC.ui.activeStatusFilter = e.target.value;
            renderAlerts();
        });
    }

    const pillContainer = document.getElementById("alerts-severity-pills");
    if (pillContainer) {
        pillContainer.querySelectorAll(".filter-pill").forEach(pill => {
            pill.addEventListener("click", () => {
                pillContainer.querySelectorAll(".filter-pill").forEach(p => {
                    p.classList.remove("active");
                    p.style.background = "transparent";
                });
                pill.classList.add("active");
                pill.style.background = "var(--bg-hover)";
                window.SOC.ui.activeSeverityFilter = pill.dataset.sev;
                renderAlerts();
            });
        });
    }

    // Support Tab key in YAML Rule Editor
    const yamlEditor = document.getElementById("rule-yaml-editor");
    if (yamlEditor) {
        yamlEditor.addEventListener("keydown", (e) => {
            if (e.key === "Tab") {
                e.preventDefault();
                const start = yamlEditor.selectionStart;
                const end = yamlEditor.selectionEnd;
                yamlEditor.value = yamlEditor.value.substring(0, start) + "  " + yamlEditor.value.substring(end);
                yamlEditor.selectionStart = yamlEditor.selectionEnd = start + 2;
            }
        });
    }

    initTrafficChartMain();
    await loadSOCState();
    renderRules();
    renderAlerts();
    renderIncidents();
    renderEvidencePicker();
    loadSIEMSettings();

    pollSOC();
    window.SOC.pollInterval = setInterval(pollSOC, 2000);
});
