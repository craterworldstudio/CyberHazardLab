let ncmWindows = new Map();


function openNCM(device) {

    const deviceName = device.name || device.id;

    if (!deviceName) {
        console.error("[CHL:NCM] Cannot open NCM: device has no name.");
        return;
    }

    const existingWindow = ncmWindows.get(deviceName);

    if (existingWindow) {
        existingWindow.hidden = false;
        existingWindow.style.zIndex = ++ncmWindowZIndex;
        return;
    }

    const window = createNCMWindow(deviceName, device.type);

    ncmWindows.set(deviceName, window);

    document.getElementById("topologyFloor").appendChild(window);

    loadNCMDevice(deviceName, window);
}


function closeNCM(deviceName) {

    const window = ncmWindows.get(deviceName);

    if (!window) {
        return;
    }

    window.remove();
    ncmWindows.delete(deviceName);
}


let ncmWindowZIndex = 50;


function createNCMWindow(deviceName, deviceType) {

    const window = document.createElement("section");

    window.className = "ncm-window";
    window.dataset.device = deviceName;

    window.style.zIndex = ++ncmWindowZIndex;

    window.innerHTML = `
        <div class="ncm-header">

            <div class="ncm-title">
                <i class="fa-solid fa-sliders"></i>
                <span>${deviceName}</span>
            </div>

            <button class="ncm-close" type="button">
                <i class="fa-solid fa-xmark"></i>
            </button>

        </div>

        <div class="ncm-tabs">

            <button class="ncm-tab active" data-tab="config">
                CONFIG
            </button>

            <button class="ncm-tab" data-tab="health">
                HEALTH
            </button>

            <button class="ncm-tab" data-tab="services">
                SERVICES
            </button>

            <button class="ncm-tab" data-tab="interfaces">
                INTERFACES
            </button>

        </div>

        <div class="ncm-content">

            <div class="ncm-tab-content active" data-content="config">
                <div class="ncm-device-type">
                    ${deviceType || "UNKNOWN"}
                </div>

                <div class="ncm-config-placeholder">
                    CONFIGURATION
                </div>
            </div>

            <div class="ncm-tab-content" data-content="health">
                <div class="ncm-config-placeholder">
                    HEALTH
                </div>
            </div>

            <div class="ncm-tab-content" data-content="services">
                <div class="ncm-services-list">
                </div>
            </div>

            <div class="ncm-tab-content" data-content="interfaces">
                <div class="ncm-interface-list">
                </div>
            </div>

        </div>
    `;

    const header = window.querySelector(".ncm-header");
    const closeButton = window.querySelector(".ncm-close");

    closeButton.addEventListener("click", () => {
        closeNCM(deviceName);
    });

    window.addEventListener("mousedown", () => {
        window.style.zIndex = ++ncmWindowZIndex;
    });

    setupNCMDragging(window, header);
    setupNCMTabs(window);

    return window;
}


function setupNCMDragging(window, header) {

    let dragging = false;
    let offsetX = 0;
    let offsetY = 0;

    header.addEventListener("mousedown", event => {

        if (event.target.closest(".ncm-close")) {
            return;
        }

        dragging = true;

        const rect = window.getBoundingClientRect();

        offsetX = event.clientX - rect.left;
        offsetY = event.clientY - rect.top;

        event.preventDefault();
    });

    document.addEventListener("mousemove", event => {

        if (!dragging) {
            return;
        }

        const parentRect = window.parentElement.getBoundingClientRect();

        window.style.left = `${event.clientX - parentRect.left - offsetX}px`;
        window.style.top = `${event.clientY - parentRect.top - offsetY}px`;

        window.style.transform = "none";
    });

    document.addEventListener("mouseup", () => {
        dragging = false;
    });
}


function setupNCMTabs(window) {

    const tabs = window.querySelectorAll(".ncm-tab");
    const contents = window.querySelectorAll(".ncm-tab-content");

    tabs.forEach(tab => {

        tab.addEventListener("click", () => {

            const target = tab.dataset.tab;

            tabs.forEach(item => {
                item.classList.toggle("active", item === tab);
            });

            contents.forEach(content => {
                content.classList.toggle(
                    "active",
                    content.dataset.content === target
                );
            });

        });

    });
}


async function loadNCMDevice(deviceName, window) {

    try {

        const interfaces = await apiRequest(
            "GET",
            `/api/ncm/devices/${encodeURIComponent(deviceName)}/interfaces`
        );

        renderNCMInterfaces(window, interfaces);
        
        const health = await apiRequest(
            "GET",
            `/api/ncm/devices/${encodeURIComponent(deviceName)}/health`
        );
        
        renderNCMHealth(window, health);

    } catch (error) {

        console.error(
            `[CHL:NCM] Failed to load ${deviceName}:`,
            error
        );

    }
}


function renderNCMInterfaces(window, interfaces) {

    const container = window.querySelector(".ncm-interface-list");

    container.innerHTML = "";

    if (!interfaces.length) {

        container.textContent = "NO INTERFACES";
        return;
    }

    interfaces.forEach(interface => {

        const row = document.createElement("div");

        row.className = "ncm-interface";

        row.innerHTML = `
            <span class="ncm-interface-name">
                ${interface.name || "UNKNOWN"}
            </span>

            <span class="ncm-interface-value">
                MAC: ${interface.mac || "—"}
            </span>

            <span class="ncm-interface-value">
                IP: ${interface.ip || "—"}
            </span>

            <span class="ncm-interface-value">
                LINK: ${interface.connected ? "CONNECTED" : "FREE"}
            </span>
        `;

        container.appendChild(row);
    });
}

function renderNCMHealth(window, health) {
    const container = window.querySelector('[data-content="health"]');
    if (!container) return;
    
    const st = (health.status || "UNKNOWN").toUpperCase();
    let statusColor = "#9ca3af"; // Default gray
    if (st === "ONLINE" || st === "ON") statusColor = "#4ade80"; // Green
    else if (st === "OFFLINE" || st === "OFF") statusColor = "#ef4444"; // Red
    else if (st === "ERROR" || st === "FAULT" || st === "COMPROMISED") statusColor = "#8b0000"; // Dark Blood Red

    container.innerHTML = `
        <div class="ncm-config-section">
            <div class="ncm-section-title">DEVICE HEALTH</div>
            <div style="display: grid; grid-template-columns: 120px 1fr; gap: 10px; font-family: monospace; font-size: 14px; margin-top: 15px;">
                <div>STATUS</div>
                <div style="color: ${statusColor}; font-weight: bold;">${st}</div>
                
                <div>UPTIME</div>
                <div>${health.uptime || '00:00:00'}</div>
                
                <div>INTERFACES</div>
                <div>${health.interfaces_active ?? 0} / ${health.interfaces_total ?? 0}</div>
                
                <div>SERVICES</div>
                <div>${health.services_total ?? 0} (${health.services_running ?? 0} RUNNING)</div>
                
                <div>PACKETS</div>
                <div style="color: #9ca3af;">N/A</div>
                
                <div>ERRORS</div>
                <div style="color: #9ca3af;">N/A</div>
            </div>
        </div>
    `;
}