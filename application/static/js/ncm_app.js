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
        <div class="ncm-header" style="background: #05070a; border-bottom: 1px solid rgba(0, 229, 255, 0.2);">
            <div class="ncm-title" style="color: #00e5ff; font-family: monospace; letter-spacing: 2px;">
                <i class="fa-solid fa-terminal" style="margin-right: 8px; opacity: 0.8;"></i>
                <span>${deviceName}</span>
            </div>
            <button class="ncm-close" type="button" style="background: transparent; border: 1px solid rgba(255,255,255,0.1); color: #5c6b73; cursor: pointer; transition: 0.2s;" onmouseover="this.style.color='#00e5ff'; this.style.borderColor='#00e5ff'" onmouseout="this.style.color='#5c6b73'; this.style.borderColor='rgba(255,255,255,0.1)'">
                <i class="fa-solid fa-xmark"></i>
            </button>
        </div>

        <div class="ncm-tabs" style="background: #080c10; border-bottom: 1px solid rgba(255,255,255,0.05);">
            <button class="ncm-tab active" data-tab="health">HEALTH</button>
            <button class="ncm-tab" data-tab="config">CONFIG</button>
            <button class="ncm-tab" data-tab="services">SERVICES</button>
            <button class="ncm-tab" data-tab="interfaces">INTERFACES</button>
        </div>

        <div class="ncm-content" style="background: #0a0f18;">
            <div class="ncm-tab-content active" data-content="health">
                <div class="ncm-config-placeholder" style="color: #5c6b73; text-align: center; margin-top: 40px;">
                    >_ AWAITING TELEMETRY...
                </div>
            </div>

            <div class="ncm-tab-content" data-content="config">
                <div class="ncm-device-type" style="color: #00e5ff; border: 1px solid rgba(0,229,255,0.1); padding: 8px; background: rgba(0,229,255,0.05); display: inline-block; font-weight: bold; letter-spacing: 2px; margin-bottom: 20px;">
                    [ TYPE: ${deviceType || "UNKNOWN"} ]
                </div>
                <div class="ncm-config-placeholder" style="color: #5c6b73;">
                    >_ NO CONFIGURATION LOADED
                </div>
            </div>

            <div class="ncm-tab-content" data-content="services">
                <div class="ncm-services-list"></div>
            </div>

            <div class="ncm-tab-content" data-content="interfaces">
                <div class="ncm-interface-list"></div>
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

        renderNCMInterfaces(window, deviceName, interfaces);
        
        const health = await apiRequest(
            "GET",
            `/api/ncm/devices/${encodeURIComponent(deviceName)}/health`
        );
        renderNCMHealth(window, health);

        const services = await apiRequest(
            "GET",
            `/api/ncm/devices/${encodeURIComponent(deviceName)}/services`
        );
        renderNCMServices(window, deviceName, services);

    } catch (error) {

        console.error(
            `[CHL:NCM] Failed to load ${deviceName}:`,
            error
        );

    }
}


function renderNCMInterfaces(window, deviceName, interfaces) {
    const container = window.querySelector(".ncm-interface-list");
    container.innerHTML = "";

    let html = `
        <div class="ncm-config-section">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px;">
                <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px;">>_ INTERFACE CONFIG</div>
                <button style="background: rgba(0,229,255,0.1); border: 1px solid #00e5ff; color: #00e5ff; font-family: monospace; font-weight: bold; padding: 2px 10px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='#00e5ff'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(0,229,255,0.1)'; this.style.color='#00e5ff';" onclick="const f = document.getElementById('add-intf-form-${deviceName}'); f.style.display = f.style.display === 'none' ? 'block' : 'none';"> + </button>
            </div>
            
            <div id="add-intf-form-${deviceName}" style="display: none; margin-top: 15px; border: 1px dashed rgba(0, 229, 255, 0.3); background: rgba(0, 0, 0, 0.2); padding: 15px;">
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 10px; font-weight: bold;">// CONFIGURE INTERFACE TARGET</div>
                
                <input type="text" id="cfg-intf-name-${deviceName}" placeholder="INTERFACE (e.g. eth0)" style="width: 100%; margin-bottom: 8px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                
                <input type="text" id="cfg-intf-ip-${deviceName}" placeholder="IP ADDRESS" style="width: 100%; margin-bottom: 8px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                
                <input type="text" id="cfg-intf-sub-${deviceName}" placeholder="SUBNET MASK" style="width: 100%; margin-bottom: 12px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                
                <button style="width: 100%; background: rgba(0, 229, 255, 0.1); border: 1px solid #00e5ff; color: #00e5ff; padding: 8px; font-family: monospace; font-weight: bold; letter-spacing: 2px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='#00e5ff'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(0, 229, 255, 0.1)'; this.style.color='#00e5ff';" onclick="updateNCMInterface('${deviceName}', document.getElementById('cfg-intf-name-${deviceName}').value, this.closest('.ncm-window'))">SAVE CONFIG</button>
            </div>
            
            <div style="margin-top: 15px;">
    `;

    if (!interfaces.length) {
        html += `<div style="color: #5c6b73; font-style: italic; text-align: center; padding: 20px 0;">>_ NO INTERFACES DETECTED</div>`;
    } else {
        interfaces.forEach(intf => {

            const statusColor = intf.connected ? '#00e5ff' : '#5c6b73';
            const statusGlow = intf.connected ? `text-shadow: 0 0 5px ${statusColor};` : '';

            html += `
                <div style="border: 1px solid rgba(255,255,255,0.05); background: rgba(255,255,255,0.02); padding: 12px; margin-bottom: 8px; transition: border 0.2s;" onmouseover="this.style.borderColor='rgba(0,229,255,0.3)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.05)'">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <strong style="color: #fff; font-size: 12px;">${intf.name || "UNKNOWN"}</strong>
                            <span style="font-size: 9px; color: ${statusColor}; margin-left: 10px; font-weight: bold; letter-spacing: 1px; ${statusGlow}">[ ${intf.connected ? "LINK_UP" : "LINK_DOWN"} ]</span>
                            <div style="font-size: 11px; margin-top: 8px; color: #8a9ba8; display: grid; grid-template-columns: 50px 1fr; gap: 4px;">
                                <div style="color: #5c6b73;">MAC</div><div style="color: #d5ebf2;">${intf.mac || "—"}</div>
                                <div style="color: #5c6b73;">IP</div><div style="color: #00e5ff;">${intf.ip || "—"}</div>
                                <div style="color: #5c6b73;">SUB</div><div style="color: #d5ebf2;">${intf.subnet || "—"}</div>
                            </div>
                        </div>
                        <div style="display: flex; gap: 6px;">
                            <button style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #8a9ba8; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.color='#fff'; this.style.borderColor='rgba(255,255,255,0.3)';" onmouseout="this.style.color='#8a9ba8'; this.style.borderColor='rgba(255,255,255,0.1)';" title="Edit" onclick="document.getElementById('add-intf-form-${deviceName}').style.display='block'; document.getElementById('cfg-intf-name-${deviceName}').value='${intf.name}'; document.getElementById('cfg-intf-ip-${deviceName}').value='${intf.ip || ''}'; document.getElementById('cfg-intf-sub-${deviceName}').value='${intf.subnet || ''}';">[ EDIT ]</button>
                            
                            <button style="background: rgba(255, 51, 51, 0.05); border: 1px solid rgba(255, 51, 51, 0.2); color: #ff3333; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='rgba(255, 51, 51, 0.2)'; this.style.borderColor='#ff3333';" onmouseout="this.style.background='rgba(255, 51, 51, 0.05)'; this.style.borderColor='rgba(255, 51, 51, 0.2)';" title="Delete" onclick="deleteNCMInterface('${deviceName}', '${intf.name}', this.closest('.ncm-window'))">[ DEL ]</button>
                        </div>
                    </div>
                </div>
            `;
        });
    }

    html += `</div></div>`;
    container.innerHTML = html;
}

async function updateNCMInterface(deviceName, interfaceName, win) {
    const ipInput = document.getElementById(`cfg-intf-ip-${deviceName}`);
    const subInput = document.getElementById(`cfg-intf-sub-${deviceName}`);
    
    if (!interfaceName) return;

    try {
        await apiRequest("PUT", `/api/ncm/devices/${encodeURIComponent(deviceName)}/interfaces/${encodeURIComponent(interfaceName)}`, {
            ip: ipInput.value || null,
            subnet: subInput.value || null
        });
        loadNCMDevice(deviceName, win);
    } catch (error) {
        console.error("[CHL:NCM] Failed to update interface", error);
    }
}

async function deleteNCMInterface(deviceName, interfaceName, win) {
    try {
        await apiRequest("DELETE", `/api/ncm/interfaces`, {
            device: deviceName,
            interface: interfaceName
        });
        loadNCMDevice(deviceName, win);
    } catch (error) {
        console.error("[CHL:NCM] Failed to delete interface", error);
    }
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
            <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px;">>_ SYSTEM DIAGNOSTICS</div>
            
            <div style="background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.05); padding: 15px; margin-top: 15px;">
                <div style="display: grid; grid-template-columns: 140px 1fr; gap: 12px; font-family: monospace; font-size: 11px;">
                    
                    <div style="color: #5c6b73;">> STATUS</div>
                    <div style="color: ${statusColor}; font-weight: bold; letter-spacing: 1px; text-shadow: 0 0 5px ${statusColor}60;">[ ${st} ]</div>
                    
                    <div style="color: #5c6b73;">> UPTIME</div>
                    <div style="color: #d5ebf2;">${health.uptime || '00:00:00'}</div>
                    
                    <div style="color: #5c6b73;">> INTERFACES</div>
                    <div style="color: #d5ebf2;">${health.interfaces_active ?? 0} / ${health.interfaces_total ?? 0} ACTIVE</div>
                    
                    <div style="color: #5c6b73;">> SERVICES</div>
                    <div style="color: #d5ebf2;">${health.services_total ?? 0} TOTAL <span style="color: #00e5ff; margin-left: 8px;">(${health.services_running ?? 0} RUNNING)</span></div>
                    
                    <div style="color: #5c6b73;">> PACKET_TRACE</div>
                    <div style="color: #5c6b73; font-style: italic;">N/A (AWAITING PROBE)</div>
                    
                    <div style="color: #5c6b73;">> FAULT_LOGS</div>
                    <div style="color: #5c6b73; font-style: italic;">0 ERRORS DETECTED</div>
                </div>
            </div>
        </div>
    `;
}

function renderNCMServices(window, deviceName, services) {
    const container = window.querySelector('[data-content="services"]');
    if (!container) return;

    let servicesHtml = `
        <div class="ncm-config-section">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px;">
                <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px;">>_ DAEMON CONTROL</div>
                <button style="background: rgba(0,229,255,0.1); border: 1px solid #00e5ff; color: #00e5ff; font-family: monospace; font-weight: bold; padding: 2px 10px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='#00e5ff'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(0,229,255,0.1)'; this.style.color='#00e5ff';" onclick="const f = document.getElementById('add-svc-form-${deviceName}'); f.style.display = f.style.display === 'none' ? 'block' : 'none';">[ + ] INIT</button>
            </div>
            
            <div id="add-svc-form-${deviceName}" style="display: none; margin-top: 15px; border: 1px dashed rgba(0, 229, 255, 0.3); background: rgba(0, 0, 0, 0.2); padding: 15px;">
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 10px; font-weight: bold;">// INITIALIZE NEW SERVICE ROUTINE</div>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
                    <input type="text" id="new-svc-name-${deviceName}" placeholder="NAME (e.g. HTTP)" style="background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                    
                    <input type="text" id="new-svc-proto-${deviceName}" placeholder="PROTOCOL (TCP/UDP)" style="background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                    
                    <input type="number" id="new-svc-port-${deviceName}" placeholder="PORT_BINDING" style="grid-column: span 2; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                    
                    <button style="grid-column: span 2; background: rgba(0, 229, 255, 0.1); border: 1px solid #00e5ff; color: #00e5ff; padding: 8px; font-family: monospace; font-weight: bold; letter-spacing: 2px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='#00e5ff'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(0, 229, 255, 0.1)'; this.style.color='#00e5ff';" onclick="addNCMService('${deviceName}', this.closest('.ncm-window'))">SPAWN SERVICE</button>
                </div>
            </div>
            
            <div style="margin-top: 15px;">
    `;

    if (services.length === 0) {
        servicesHtml += `<div style="color: #5c6b73; font-style: italic; text-align: center; padding: 20px 0;">>_ PROCESS TABLE EMPTY</div>`;
    } else {
        servicesHtml += services.map(s => {
            const isRunning = s.status === 'running';
            const statusColor = isRunning ? '#00e5ff' : '#5c6b73';
            const statusText = isRunning ? 'RUNNING' : 'HALTED';
            const statusGlow = isRunning ? `text-shadow: 0 0 5px ${statusColor};` : '';

            return `

            <div style="border: 1px solid rgba(255,255,255,0.05); background: rgba(255,255,255,0.02); padding: 12px; margin-bottom: 8px; transition: border 0.2s;" onmouseover="this.style.borderColor='rgba(0,229,255,0.3)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.05)'">
                <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                    <div>
                        <strong style="color: #fff; font-size: 12px;">${s.name}</strong>
                        <span style="font-size: 9px; color: ${statusColor}; margin-left: 10px; font-weight: bold; letter-spacing: 1px; ${statusGlow}">[ ${statusText} ]</span>
                        <div style="font-size: 11px; margin-top: 8px; color: #8a9ba8; display: grid; grid-template-columns: 40px 1fr; gap: 4px;">
                            <div style="color: #5c6b73;">PROTO</div><div style="color: #d5ebf2;">${(s.protocol || '').toUpperCase()}</div>
                            <div style="color: #5c6b73;">PORT</div><div style="color: #00e5ff;">${s.port}</div>
                        </div>
                    </div>
                    <div style="display: flex; gap: 6px; align-items: flex-start;">
                        ${isRunning ? 
                            `<button style="background: rgba(255, 170, 0, 0.05); border: 1px solid rgba(255, 170, 0, 0.3); color: #ffaa00; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='rgba(255, 170, 0, 0.2)'; this.style.borderColor='#ffaa00';" onmouseout="this.style.background='rgba(255, 170, 0, 0.05)'; this.style.borderColor='rgba(255, 170, 0, 0.3)';" title="Stop" onclick="manageService('${deviceName}', '${s.name}', 'stop', this.closest('.ncm-window'))">[ STOP ]</button>` :
                            `<button style="background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.3); color: #00e5ff; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='rgba(0, 229, 255, 0.2)'; this.style.borderColor='#00e5ff';" onmouseout="this.style.background='rgba(0, 229, 255, 0.05)'; this.style.borderColor='rgba(0, 229, 255, 0.3)';" title="Start" onclick="manageService('${deviceName}', '${s.name}', 'start', this.closest('.ncm-window'))">[ START ]</button>`
                        }
                        
                        <button style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #8a9ba8; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.color='#fff'; this.style.borderColor='rgba(255,255,255,0.3)';" onmouseout="this.style.color='#8a9ba8'; this.style.borderColor='rgba(255,255,255,0.1)';" title="Edit" onclick="const f=document.getElementById('add-svc-form-${deviceName}'); f.style.display='block'; document.getElementById('new-svc-name-${deviceName}').value='${s.name}'; document.getElementById('new-svc-proto-${deviceName}').value='${s.protocol}'; document.getElementById('new-svc-port-${deviceName}').value='${s.port}';">[ EDIT ]</button>
                        
                        <button style="background: rgba(255, 51, 51, 0.05); border: 1px solid rgba(255, 51, 51, 0.2); color: #ff3333; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='rgba(255, 51, 51, 0.2)'; this.style.borderColor='#ff3333';" onmouseout="this.style.background='rgba(255, 51, 51, 0.05)'; this.style.borderColor='rgba(255, 51, 51, 0.2)';" title="Delete" onclick="manageService('${deviceName}', '${s.name}', 'remove', this.closest('.ncm-window'))">[ DEL ]</button>
                    </div>
                </div>
            </div>
            `;
        }).join('');
    }

    servicesHtml += `</div></div>`;
    container.innerHTML = servicesHtml;
}

async function manageService(deviceName, serviceName, action, win) {
    try {
        if (action === 'remove') {
            await apiRequest("DELETE", `/api/ncm/devices/${encodeURIComponent(deviceName)}/services/${encodeURIComponent(serviceName)}`);
        } else {
            await apiRequest("POST", `/api/ncm/devices/${encodeURIComponent(deviceName)}/services/${encodeURIComponent(serviceName)}/${action}`);
        }
        loadNCMDevice(deviceName, win);
    } catch (error) {
        console.error("[CHL:NCM] Failed to manage service", error);
    }
}

async function addNCMService(deviceName, win) {
    const nameInput = document.getElementById(`new-svc-name-${deviceName}`);
    const protoInput = document.getElementById(`new-svc-proto-${deviceName}`);
    const portInput = document.getElementById(`new-svc-port-${deviceName}`);

    if (!nameInput.value || !protoInput.value || !portInput.value) return;

    try {
        await apiRequest("POST", `/api/ncm/devices/${encodeURIComponent(deviceName)}/services`, {
            name: nameInput.value,
            protocol: protoInput.value,
            port: portInput.value
        });
        loadNCMDevice(deviceName, win);
    } catch (error) {
        console.error("[CHL:NCM] Failed to add service", error);
    }
}