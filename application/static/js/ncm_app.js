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
            ${deviceType === 'SWITCH' 
                ? `<button class="ncm-tab" data-tab="mac_table">MAC TABLE</button>`
                : (deviceType === 'ROUTER'
                    ? `<button class="ncm-tab" data-tab="routes">ROUTING TABLE</button>
                       <button class="ncm-tab" data-tab="services">SERVICES</button>
                       <button class="ncm-tab" data-tab="terminal">TERMINAL</button>`
                    : `<button class="ncm-tab" data-tab="services">SERVICES</button>
                       <button class="ncm-tab" data-tab="terminal">TERMINAL</button>`)
            }
            <button class="ncm-tab" data-tab="interfaces">${deviceType === 'SWITCH' ? 'SWITCH PORTS' : 'INTERFACES'}</button>
        </div>

        <div class="ncm-content" style="background: #0a0f18; display: flex; flex-direction: column;">
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

            ${deviceType === 'SWITCH' ? `
            <div class="ncm-tab-content" data-content="mac_table">
                <div class="ncm-mac-table"></div>
            </div>
            ` : (deviceType === 'ROUTER' ? `
            <div class="ncm-tab-content" data-content="routes">
                <div class="ncm-routing-table"></div>
            </div>
            <div class="ncm-tab-content" data-content="services">
                <div class="ncm-services-list"></div>
            </div>
            <div class="ncm-tab-content" data-content="terminal">
                <div style="display: flex; flex-direction: column; height: 100%;">
                    <div class="ncm-terminal-output" style="flex: 1; background: #06090e; color: #d5ebf2; font-family: monospace; font-size: 12px; padding: 10px; overflow-y: auto; border: 1px solid rgba(0, 229, 255, 0.15); margin-bottom: 10px;">
                        <div style="color: #00e5ff; font-weight: bold; letter-spacing: 1px;">> Nox OS (Network Operations Execution)</div>
                        <div style="color: #5c6b73; margin-bottom: 15px;">System version 1.0.0. Type 'help' for available commands.</div>
                    </div>
                    <div style="display: flex; align-items: center; border: 1px solid rgba(0, 229, 255, 0.3); background: #06090e; padding: 8px;">
                        <span class="ncm-terminal-prompt" id="term-prompt-${deviceName}" style="color: #00e5ff; font-family: monospace; font-weight: bold; margin-right: 8px;">root@${deviceName.toLowerCase()}:~$</span>
                        <input type="text" class="ncm-terminal-input" placeholder="_" style="flex: 1; background: transparent; border: none; color: #d5ebf2; font-family: monospace; font-size: 12px; outline: none;" onkeydown="handleTerminalInput(event, '${deviceName}')">
                    </div>
                </div>
            </div>
            ` : `
            <div class="ncm-tab-content" data-content="services">
                <div class="ncm-services-list"></div>
            </div>
            <div class="ncm-tab-content" data-content="terminal">
                <div style="display: flex; flex-direction: column; height: 100%;">
                    <div class="ncm-terminal-output" style="flex: 1; background: #06090e; color: #d5ebf2; font-family: monospace; font-size: 12px; padding: 10px; overflow-y: auto; border: 1px solid rgba(0, 229, 255, 0.15); margin-bottom: 10px;">
                        <div style="color: #00e5ff; font-weight: bold; letter-spacing: 1px;">> Nox OS (Network Operations Execution)</div>
                        <div style="color: #5c6b73; margin-bottom: 15px;">System version 1.0.0. Type 'help' for available commands.</div>
                    </div>
                    <div style="display: flex; align-items: center; border: 1px solid rgba(0, 229, 255, 0.3); background: #06090e; padding: 8px;">
                        <span class="ncm-terminal-prompt" id="term-prompt-${deviceName}" style="color: #00e5ff; font-family: monospace; font-weight: bold; margin-right: 8px;">root@${deviceName.toLowerCase()}:~$</span>
                        <input type="text" class="ncm-terminal-input" placeholder="_" style="flex: 1; background: transparent; border: none; color: #d5ebf2; font-family: monospace; font-size: 12px; outline: none;" onkeydown="handleTerminalInput(event, '${deviceName}')">
                    </div>
                </div>
            </div>
            `)}

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
        window._cachedIntfKey = JSON.stringify(interfaces || []);
        
        const health = await apiRequest(
            "GET",
            `/api/ncm/devices/${encodeURIComponent(deviceName)}/health`
        );
        renderNCMHealth(window, health);

        const services = await apiRequest(
            "GET",
            `/api/ncm/devices/${encodeURIComponent(deviceName)}/services`
        ).catch(() => []); // Ignore if services endpoint fails (e.g. for switches)
        
        renderNCMServices(window, deviceName, services);
        window._renderedServicesKey = JSON.stringify(services || []);
        
        // If it's a switch, fetch MAC table directly from device info
        const deviceData = await apiRequest(
            "GET",
            `/api/ntm/devices/${encodeURIComponent(deviceName)}`
        );
        if (deviceData.type.toUpperCase() === 'SWITCH') {
            renderNCMMacTable(window, deviceName, deviceData.mac_table || {});
            window._renderedMacKey = JSON.stringify(deviceData.mac_table || {});
        } else if (deviceData.type.toUpperCase() === 'ROUTER') {
            renderNCMRoutingTable(window, deviceName, deviceData.routes || []);
            window._renderedRoutesKey = JSON.stringify(deviceData.routes || []);
        }

        renderNCMConfig(window, deviceName, deviceData);

    } catch (error) {

        console.error(
            `[CHL:NCM] Failed to load ${deviceName}:`,
            error
        );

    }
}
    
async function toggleDeviceSetting(deviceName, setting, value) {
    try {
        const payload = {};
        payload[setting] = value;
        await apiRequest("POST", `/api/ncm/devices/${encodeURIComponent(deviceName)}/config`, payload);
        console.log(`[CHL:NCM] Updated ${setting} to ${value} for ${deviceName}`);
    } catch (error) {
        console.error("[CHL:NCM] Failed to update config", error);
    }
}

async function restartNCMDevice(deviceName, win) {
    try {
        await apiRequest("POST", `/api/ncm/devices/${encodeURIComponent(deviceName)}/restart`);
        loadNCMDevice(deviceName, win);
    } catch (error) {
        console.error("[CHL:NCM] Failed to restart device", error);
    }
}

function renderNCMConfig(window, deviceName, deviceData) {
    const container = window.querySelector('[data-content="config"]');
    if (!container) return;
    
    container.innerHTML = `
        <div class="ncm-device-type" style="color: #00e5ff; border: 1px solid rgba(0,229,255,0.1); padding: 8px; background: rgba(0,229,255,0.05); display: inline-block; font-weight: bold; letter-spacing: 2px; margin-bottom: 20px;">
            [ TYPE: ${deviceData.type || "UNKNOWN"} ]
        </div>
        <div class="ncm-config-section">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px; margin-bottom: 15px;">
                <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px;">>_ DEVICE CONFIGURATION</div>
            </div>
            
            <div style="border: 1px solid rgba(255,255,255,0.05); background: rgba(255,255,255,0.02); padding: 15px;">
                <div style="color: #d5ebf2; font-size: 13px; margin-bottom: 15px;">
                    <strong>NODE ID:</strong> <span style="color: #00e5ff;">${deviceName}</span>
                </div>
                
                <div style="color: #8a9ba8; font-size: 11px; margin-bottom: 20px;">
                    Use the restart button to reboot the device node, clearing local states (like ephemeral ports, active connections, and runtime errors) while preserving saved interfaces and services.
                </div>
                
                <button style="background: rgba(255, 170, 0, 0.1); border: 1px solid #ffaa00; color: #ffaa00; padding: 10px 15px; font-family: monospace; font-weight: bold; letter-spacing: 2px; cursor: pointer; transition: 0.2s; width: 100%;" onmouseover="this.style.background='#ffaa00'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(255, 170, 0, 0.1)'; this.style.color='#ffaa00';" onclick="restartNCMDevice('${deviceName}', this.closest('.ncm-window'))">REBOOT DEVICE NODE</button>
            </div>
        </div>
    `;
}

function renderNCMInterfaces(window, deviceName, interfaces) {
    const container = window.querySelector(".ncm-interface-list");
    container.innerHTML = "";

    let html = `
        <div class="ncm-config-section">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px;">
                <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px;">>_ ${deviceName.startsWith('SWT') ? 'PORT' : 'INTERFACE'} CONFIG</div>
                <button style="background: rgba(0,229,255,0.1); border: 1px solid #00e5ff; color: #00e5ff; font-family: monospace; font-weight: bold; padding: 2px 10px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='#00e5ff'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(0,229,255,0.1)'; this.style.color='#00e5ff';" onclick="const f = document.getElementById('add-intf-form-${deviceName}'); f.style.display = f.style.display === 'none' ? 'block' : 'none';"> + </button>
            </div>
            
            <div id="add-intf-form-${deviceName}" style="display: none; margin-top: 15px; border: 1px dashed rgba(0, 229, 255, 0.3); background: rgba(0, 0, 0, 0.2); padding: 15px;">
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 10px; font-weight: bold;">// CONFIGURE ${deviceName.startsWith('SWT') ? 'PORT' : 'INTERFACE'} TARGET</div>
                
                <input type="text" id="cfg-intf-name-${deviceName}" placeholder="${deviceName.startsWith('SWT') ? 'PORT (e.g. 1)' : 'INTERFACE (e.g. eth0)'}" style="width: 100%; margin-bottom: 8px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                
                <input type="text" id="cfg-intf-ip-${deviceName}" placeholder="IP ADDRESS (e.g. 10.0.0.1/24)" style="width: 100%; margin-bottom: 8px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                
                <button style="width: 100%; background: rgba(0, 229, 255, 0.1); border: 1px solid #00e5ff; color: #00e5ff; padding: 8px; font-family: monospace; font-weight: bold; letter-spacing: 2px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='#00e5ff'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(0, 229, 255, 0.1)'; this.style.color='#00e5ff';" onclick="updateNCMInterface('${deviceName}', document.getElementById('cfg-intf-name-${deviceName}').value, this.closest('.ncm-window'))">SAVE CONFIG</button>
            </div>
            
            <div style="margin-top: 15px;">
    `;

    if (!interfaces.length) {
        html += `<div style="color: #5c6b73; font-style: italic; text-align: center; padding: 20px 0;">>_ NO ${deviceName.startsWith('SWT') ? 'PORTS' : 'INTERFACES'} DETECTED</div>`;
    } else {
        interfaces.forEach(intf => {

            const isLinkUp = intf.connected && intf.status === 'up';
            const isAdminDown = intf.status === 'down';
            let statusText = isAdminDown ? "ADMIN_DOWN" : (intf.connected ? "LINK_UP" : "LINK_DOWN");
            let statusColor = isAdminDown ? '#ff3333' : (intf.connected ? '#00e5ff' : '#5c6b73');
            const statusGlow = isLinkUp ? `text-shadow: 0 0 5px ${statusColor};` : '';
            
            if (deviceName.startsWith('SWT')) {
                html += `
                    <div style="border: 1px solid rgba(255,255,255,0.05); background: rgba(255,255,255,0.02); padding: 12px; margin-bottom: 8px; transition: border 0.2s;" onmouseover="this.style.borderColor='rgba(0,229,255,0.3)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.05)'">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div>
                                <strong style="color: #fff; font-size: 12px;">${intf.name || "UNKNOWN"}</strong>
                                <span style="font-size: 9px; color: ${statusColor}; margin-left: 10px; font-weight: bold; letter-spacing: 1px; ${statusGlow}">[ ${statusText} ]</span>
                                <div style="font-size: 11px; margin-top: 8px; color: #8a9ba8; display: grid; grid-template-columns: 50px 1fr; gap: 4px;">
                                    <div style="color: #5c6b73;">PORT</div><div style="color: #d5ebf2;">${intf.port_number || "—"}</div>
                                    <div style="color: #5c6b73;">MODE</div><div style="color: #00e5ff;">${intf.mode || "ACCESS"}</div>
                                    <div style="color: #5c6b73;">LINK</div><div style="color: #d5ebf2;">${intf.connected_to || "—"}</div>
                                </div>
                            </div>
                            <div style="display: flex; gap: 6px;">
                                <button style="background: rgba(255, 51, 51, 0.05); border: 1px solid rgba(255, 51, 51, 0.2); color: #ff3333; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='rgba(255, 51, 51, 0.2)'; this.style.borderColor='#ff3333';" onmouseout="this.style.background='rgba(255, 51, 51, 0.05)'; this.style.borderColor='rgba(255, 51, 51, 0.2)';" title="Delete" onclick="deleteNCMInterface('${deviceName}', '${intf.name}', this.closest('.ncm-window'))">[ DEL ]</button>
                            </div>
                        </div>
                    </div>
                `;
            } else {
                html += `
                    <div style="border: 1px solid rgba(255,255,255,0.05); background: rgba(255,255,255,0.02); padding: 12px; margin-bottom: 8px; transition: border 0.2s;" onmouseover="this.style.borderColor='rgba(0,229,255,0.3)'" onmouseout="this.style.borderColor='rgba(255,255,255,0.05)'">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                            <div>
                                <strong style="color: #fff; font-size: 12px;">${intf.name || "UNKNOWN"}</strong>
                                <span style="font-size: 9px; color: ${statusColor}; margin-left: 10px; font-weight: bold; letter-spacing: 1px; ${statusGlow}">[ ${statusText} ]</span>
                                <div style="font-size: 11px; margin-top: 8px; color: #8a9ba8; display: grid; grid-template-columns: 50px 1fr; gap: 4px;">
                                    <div style="color: #5c6b73;">MAC</div><div style="color: #d5ebf2;">${intf.mac || "—"}</div>
                                    <div style="color: #5c6b73;">IP</div><div style="color: #00e5ff;">${intf.ip ? (intf.subnet && intf.subnet.includes('/') ? intf.ip + '/' + intf.subnet.split('/')[1] : intf.ip) : "—"}</div>
                                </div>
                            </div>
                            <div style="display: flex; gap: 6px;">
                                <button style="background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #8a9ba8; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.color='#fff'; this.style.borderColor='rgba(255,255,255,0.3)';" onmouseout="this.style.color='#8a9ba8'; this.style.borderColor='rgba(255,255,255,0.1)';" title="Edit" onclick="const form = document.getElementById('add-intf-form-${deviceName}'); form.style.display='block'; form.dataset.editing='${intf.name}'; document.getElementById('cfg-intf-name-${deviceName}').value='${intf.name}'; document.getElementById('cfg-intf-name-${deviceName}').readOnly=true; document.getElementById('cfg-intf-name-${deviceName}').style.opacity='0.5'; document.getElementById('cfg-intf-ip-${deviceName}').value='${intf.ip ? (intf.subnet && intf.subnet.includes('/') ? intf.ip + '/' + intf.subnet.split('/')[1] : intf.ip) : ''}';">[ EDIT ]</button>
                                
                                <button style="background: rgba(255, 51, 51, 0.05); border: 1px solid rgba(255, 51, 51, 0.2); color: #ff3333; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='rgba(255, 51, 51, 0.2)'; this.style.borderColor='#ff3333';" onmouseout="this.style.background='rgba(255, 51, 51, 0.05)'; this.style.borderColor='rgba(255, 51, 51, 0.2)';" title="Delete" onclick="deleteNCMInterface('${deviceName}', '${intf.name}', this.closest('.ncm-window'))">[ DEL ]</button>
                            </div>
                        </div>
                    </div>
                `;
            }
        });
    }

    html += `</div></div>`;
    container.innerHTML = html;
}

function renderNCMMacTable(window, deviceName, macTable) {
    const container = window.querySelector(".ncm-mac-table");
    if (!container) return;
    
    const key = JSON.stringify(macTable || {});
    if (window._renderedMacKey === key) return;
    window._renderedMacKey = key;
    
    let html = `
        <div class="ncm-config-section">
            <div style="border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px;">
                <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px;">>_ MAC ADDRESS TABLE</div>
            </div>
            <div style="margin-top: 15px;">
    `;
    
    const entries = Object.entries(macTable);
    if (!entries.length) {
        html += `<div style="color: #5c6b73; font-style: italic; text-align: center; padding: 20px 0;">>_ TABLE IS EMPTY</div>`;
    } else {
        html += `
            <table style="width: 100%; text-align: left; border-collapse: collapse; font-family: monospace; font-size: 11px;">
                <thead>
                    <tr style="color: #5c6b73; border-bottom: 1px solid rgba(255,255,255,0.1);">
                        <th style="padding: 8px 4px;">MAC ADDRESS</th>
                        <th style="padding: 8px 4px;">PORT</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        entries.forEach(([mac, port]) => {
            html += `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.02); color: #d5ebf2;">
                    <td style="padding: 8px 4px; color: #00e5ff;">${mac}</td>
                    <td style="padding: 8px 4px;">Port-${port}</td>
                </tr>
            `;
        });
        
        html += `</tbody></table>`;
    }
    
    html += `</div></div>`;
    container.innerHTML = html;
}

function renderNCMRoutingTable(window, deviceName, routes) {
    const container = window.querySelector(".ncm-routing-table");
    if (!container) return;
    
    const key = JSON.stringify(routes || []);
    if (window._renderedRoutesKey === key) return;
    window._renderedRoutesKey = key;
    
    let html = `
        <div class="ncm-config-section">
            <div style="border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px;">
                <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px;">>_ ROUTING TABLE</div>
            </div>
            <div style="margin-top: 15px;">
    `;
    
    if (!routes.length) {
        html += `<div style="color: #5c6b73; font-style: italic; text-align: center; padding: 20px 0;">>_ TABLE IS EMPTY</div>`;
    } else {
        html += `
            <table style="width: 100%; text-align: left; border-collapse: collapse; font-family: monospace; font-size: 11px;">
                <thead>
                    <tr style="color: #5c6b73; border-bottom: 1px solid rgba(255,255,255,0.1);">
                        <th style="padding: 8px 4px;">DESTINATION</th>
                        <th style="padding: 8px 4px;">INTERFACE</th>
                        <th style="padding: 8px 4px;">NEXT HOP</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        routes.forEach(route => {
            html += `
                <tr style="border-bottom: 1px solid rgba(255,255,255,0.02); color: #d5ebf2;">
                    <td style="padding: 8px 4px; color: #00e5ff;">${route.destination}</td>
                    <td style="padding: 8px 4px;">${route.interface || "—"}</td>
                    <td style="padding: 8px 4px;">${route.next_hop || "DIRECT"}</td>
                </tr>
            `;
        });
        
        html += `</tbody></table>`;
    }
    
    html += `</div></div>`;
    container.innerHTML = html;
}

const terminalHistory = [];
let terminalHistoryIndex = -1;

async function handleTerminalInput(event, deviceName) {
    const inputField = event.target;

    if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (terminalHistory.length > 0) {
            if (terminalHistoryIndex < terminalHistory.length - 1) {
                terminalHistoryIndex++;
            }
            inputField.value = terminalHistory[terminalHistory.length - 1 - terminalHistoryIndex];
        }
        return;
    }
    
    if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (terminalHistoryIndex > 0) {
            terminalHistoryIndex--;
            inputField.value = terminalHistory[terminalHistory.length - 1 - terminalHistoryIndex];
        } else if (terminalHistoryIndex === 0) {
            terminalHistoryIndex = -1;
            inputField.value = "";
        }
        return;
    }

    if (event.key === 'Enter') {
        const commandStr = inputField.value.trim();
        if (!commandStr) return;
        
        // Save to history
        if (terminalHistory[terminalHistory.length - 1] !== commandStr) {
            terminalHistory.push(commandStr);
        }
        terminalHistoryIndex = -1;
        
        const win = ncmWindows.get(deviceName);
        if (!win) return;
        
        const promptSpan = win.querySelector('.ncm-terminal-prompt');
        const currentPrompt = promptSpan ? promptSpan.textContent : `root@${deviceName.toLowerCase()}:~$ `;
        
        const escapeHtml = (unsafe) => {
            return (unsafe || "").toString()
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        };
        
        const outputDiv = win.querySelector('.ncm-terminal-output');
        
        // Echo command
        if (currentPrompt.toLowerCase().includes("password:")) {
            outputDiv.innerHTML += `<div style="color: #00e5ff; margin-top: 5px;">${escapeHtml(currentPrompt)}</div>`;
        } else {
            outputDiv.innerHTML += `<div style="color: #00e5ff; margin-top: 5px;">${escapeHtml(currentPrompt)} ${escapeHtml(commandStr)}</div>`;
        }
        inputField.value = '';
        inputField.disabled = true;
        
        outputDiv.scrollTop = outputDiv.scrollHeight;
        
        try {
            const response = await apiRequest("POST", `/api/ncm/devices/${encodeURIComponent(deviceName)}/terminal`, {
                command: commandStr
            });

            if (response.prompt && promptSpan) {
                promptSpan.textContent = response.prompt;
                if (response.prompt.toLowerCase().includes("password:")) {
                    inputField.type = "password";
                } else {
                    inputField.type = "text";
                }
            }

            if (response.output) {
                // Render multiline response with artificial latency
                const lines = response.output.split('\n');
                
                for (let line of lines) {
                    let delay = 0;
                    const delayMatch = line.match(/\[DELAY:(\d+)\]/);
                    if (delayMatch) {
                        delay = parseInt(delayMatch[1], 10);
                        line = line.replace(/\[DELAY:\d+\]/, '');
                    } else {
                        if (line.includes("Request timed out") || line.includes("Destination Host Unreachable")) {
                            delay = 2000;
                        } else if (line.includes(" ms ") || line.includes("icmp_seq=")) {
                            delay = 600;
                        } else if (line.includes("Tracing route to")) {
                            delay = 300;
                        }
                    }
                    
                    if (delay > 0) {
                        await new Promise(resolve => setTimeout(resolve, delay));
                    }
                    
                    outputDiv.innerHTML += `<div style="color: #d5ebf2; white-space: pre;">${escapeHtml(line)}</div>`;
                    outputDiv.scrollTop = outputDiv.scrollHeight;
                }
            }
        } catch (error) {
            outputDiv.innerHTML += `<div style="color: #ff3333;">ERROR: ${error.message || "Failed to execute command"}</div>`;
        }
        
        outputDiv.innerHTML += `<br>`;
        outputDiv.scrollTop = outputDiv.scrollHeight;
        inputField.disabled = false;
        inputField.focus();
    }
}

async function updateNCMInterface(deviceName, interfaceName, win) {
    const ipInput = document.getElementById(`cfg-intf-ip-${deviceName}`);
    const form = document.getElementById(`add-intf-form-${deviceName}`);
    
    // Use the original name we're editing, or the field value if it's a new interface
    const isNew = !form.dataset.editing;
    const targetName = form.dataset.editing || interfaceName;
    
    if (!targetName) return;

    try {
        if (isNew) {
            await apiRequest("POST", `/api/ncm/interfaces`, {
                device: deviceName,
                name: targetName,
                ip: ipInput.value || null
            });
            // If IP provided, we also need to update it since POST only sets the name/mac
            if (ipInput.value) {
                await apiRequest("PUT", `/api/ncm/devices/${encodeURIComponent(deviceName)}/interfaces/${encodeURIComponent(targetName)}`, {
                    ip: ipInput.value || null
                });
            }
        } else {
            await apiRequest("PUT", `/api/ncm/devices/${encodeURIComponent(deviceName)}/interfaces/${encodeURIComponent(targetName)}`, {
                ip: ipInput.value || null
            });
        }
        
        // Reset form state
        delete form.dataset.editing;
        document.getElementById(`cfg-intf-name-${deviceName}`).readOnly = false;
        document.getElementById(`cfg-intf-name-${deviceName}`).style.opacity = '1';
        
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

async function refreshNCMHealth(deviceName, window) {
    try {
        const health = await apiRequest("GET", `/api/ncm/devices/${encodeURIComponent(deviceName)}/health`);
        renderNCMHealth(window, health);
    } catch (e) {
        // Silent catch for background polling
    }
}

async function refreshNCMTables(deviceName, window) {
    try {
        const deviceData = await apiRequest("GET", `/api/ntm/devices/${encodeURIComponent(deviceName)}`);
        if (deviceData.type.toUpperCase() === 'SWITCH' && deviceData.mac_table) {
            renderNCMMacTable(window, deviceName, deviceData.mac_table);
        } else if (deviceData.type.toUpperCase() === 'ROUTER' && deviceData.routes) {
            renderNCMRoutingTable(window, deviceName, deviceData.routes);
        }
    } catch (e) {
        // Silent catch for background polling
    }
}

// Global polling is now handled by lab_app.js (window.SimulationState)
window.addEventListener("simulation-events-updated", (e) => {
    if (typeof ncmWindows !== 'undefined') {
        ncmWindows.forEach((win, deviceName) => {
            if (!win.hidden && deviceName === "GLOBAL_NETWORK") {
                refreshGlobalAlerts(win);
            }
        });
    }
});

// We can also sync NCM tables using the global state instead of fetching individually
setInterval(() => {
    if (typeof ncmWindows !== 'undefined' && window.SimulationState && window.SimulationState.devices) {
        ncmWindows.forEach((win, deviceName) => {
            if (!win.hidden && deviceName !== "GLOBAL_NETWORK") {
                const deviceData = window.SimulationState.devices.find(d => d.name === deviceName);
                if (deviceData) {
                    if (deviceData.type.toUpperCase() === 'SWITCH' && deviceData.mac_table) {
                        renderNCMMacTable(win, deviceName, deviceData.mac_table);
                    } else if (deviceData.type.toUpperCase() === 'ROUTER' && deviceData.routes) {
                        renderNCMRoutingTable(win, deviceName, deviceData.routes);
                    }
                    
                    // Only update Interfaces if form is not actively editing and interface data changed
                    const form = win.querySelector(`#add-intf-form-${deviceName}`);
                    const isFormOpen = form && form.style.display !== 'none' && form.style.display !== '';
                    const isEditing = form && Boolean(form.dataset.editing);
                    
                    if (!isFormOpen && !isEditing) {
                        const intfKey = JSON.stringify(deviceData.interfaces || []);
                        if (win._cachedIntfKey !== intfKey) {
                            renderNCMInterfaces(win, deviceName, deviceData.interfaces || []);
                            win._cachedIntfKey = intfKey;
                        }
                    }
                    
                    const intfs = deviceData.interfaces || [];
                    const svcs = deviceData.services || [];

                    // Sync Services if data changed & add-service form not open
                    const sForm = win.querySelector(`#add-svc-form-${deviceName}`);
                    const isSFormOpen = sForm && sForm.style.display !== 'none' && sForm.style.display !== '';
                    if (!isSFormOpen) {
                        renderNCMServices(win, deviceName, svcs);
                    }
                    
                    // Update Health with real telemetry metrics
                    const healthData = deviceData.health || {
                        status: deviceData.status,
                        uptime: deviceData.uptime || '00:00:00',
                        interfaces_active: deviceData.interfaces_active ?? intfs.filter(i => i.connected && i.status === 'up').length,
                        interfaces_total: deviceData.interfaces_total ?? intfs.length,
                        services_total: deviceData.services_total ?? svcs.length,
                        services_running: deviceData.services_running ?? svcs.filter(s => (s.status || '').toLowerCase() === 'running').length
                    };

                    renderNCMHealth(win, healthData);
                }
            }
        });
    }
}, 1000);

async function refreshGlobalAlerts(win) {
    try {
        const events = await apiRequest("GET", "/api/simulation/events");
        renderGlobalAlerts(win, events.filter(e => e.severity === "HIGH" || e.severity === "WARNING"));
    } catch(e) {}
}

function renderGlobalAlerts(win, events) {
    const container = win.querySelector(".ncm-alerts-list");
    if (!container) return;
    
    let html = `
        <div class="ncm-config-section">
            <div style="border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px;">
                <div class="ncm-section-title" style="color: #ff3333; font-weight: bold; letter-spacing: 2px;">>_ CRITICAL & HIGH ALERTS</div>
            </div>
            <div style="margin-top: 15px;">
    `;

    if (!events || events.length === 0) {
        html += `<div style="color: #4ade80; font-family: monospace; font-size: 11px; padding: 15px 0; text-align: center;">>_ ALL SYSTEMS SECURE - NO HIGH SEVERITY ALERTS</div>`;
    } else {
        const reversed = [...events].reverse();
        reversed.slice(0, 30).forEach(evt => {
            const timeStr = evt.timestamp ? (new Date(evt.timestamp).toLocaleTimeString()) : "—";
            html += `
                <div style="border: 1px solid rgba(255, 51, 51, 0.2); background: rgba(255, 51, 51, 0.05); padding: 10px; margin-bottom: 8px; font-family: monospace; font-size: 11px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
                        <span style="color: #ff3333; font-weight: bold;">[${evt.type}]</span>
                        <span style="color: #8a9ba8;">${timeStr}</span>
                    </div>
                    <div style="color: #d5ebf2; margin-bottom: 4px;">Source: <span style="color: #00e5ff;">${evt.source || "System"}</span> &rarr; Dest: <span style="color: #00e5ff;">${evt.destination || "Broadcast"}</span></div>
                    ${evt.metadata ? `<div style="color: #ffaa00; font-size: 10px;">${JSON.stringify(evt.metadata)}</div>` : ''}
                </div>
            `;
        });
    }

    html += `</div></div>`;
    container.innerHTML = html;
}

function renderNCMHealth(window, health) {
    const container = window.querySelector('[data-content="health"]');
    if (!container) return;
    
    const deviceName = window.dataset.device || "";
    
    const st = (health.status || "UNKNOWN").toUpperCase();
    let statusColor = "#9ca3af"; // Default gray
    if (st === "ONLINE" || st === "ON") statusColor = "#4ade80"; // Green
    else if (st === "OFFLINE" || st === "OFF") statusColor = "#ef4444"; // Red
    else if (st === "ERROR" || st === "FAULT" || st === "COMPROMISED") statusColor = "#8b0000"; // Dark Blood Red

    const statusEl = container.querySelector(".ncm-health-status");
    const uptimeEl = container.querySelector(".ncm-health-uptime");
    const intfEl = container.querySelector(".ncm-health-interfaces");
    const svcEl = container.querySelector(".ncm-health-services");

    if (statusEl && uptimeEl && intfEl) {
        statusEl.textContent = `[ ${st} ]`;
        statusEl.style.color = statusColor;
        statusEl.style.textShadow = `0 0 5px ${statusColor}60`;
        uptimeEl.textContent = health.uptime || "00:00:00";
        intfEl.textContent = `${health.interfaces_active ?? 0} / ${health.interfaces_total ?? 0} ACTIVE`;
        if (svcEl) {
            svcEl.innerHTML = `${health.services_total ?? 0} TOTAL <span style="color: #00e5ff; margin-left: 8px;">(${health.services_running ?? 0} RUNNING)</span>`;
        }
        return;
    }

    container.innerHTML = `
        <div class="ncm-config-section">
            <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px;">>_ SYSTEM DIAGNOSTICS</div>
            
            <div style="background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.05); padding: 15px; margin-top: 15px;">
                <div style="display: grid; grid-template-columns: 140px 1fr; gap: 12px; font-family: monospace; font-size: 11px;">
                    
                    <div style="color: #5c6b73;">> STATUS</div>
                    <div class="ncm-health-status" style="color: ${statusColor}; font-weight: bold; letter-spacing: 1px; text-shadow: 0 0 5px ${statusColor}60;">[ ${st} ]</div>
                    
                    <div style="color: #5c6b73;">> UPTIME</div>
                    <div class="ncm-health-uptime" style="color: #d5ebf2;">${health.uptime || '00:00:00'}</div>
                    
                    <div style="color: #5c6b73;">> ${deviceName.startsWith('SWT') ? 'SWITCH_PORTS' : 'INTERFACES'}</div>
                    <div class="ncm-health-interfaces" style="color: #d5ebf2;">${health.interfaces_active ?? 0} / ${health.interfaces_total ?? 0} ACTIVE</div>
                    
                    ${!deviceName.startsWith('SWT') ? `
                    <div style="color: #5c6b73;">> SERVICES</div>
                    <div class="ncm-health-services" style="color: #d5ebf2;">${health.services_total ?? 0} TOTAL <span style="color: #00e5ff; margin-left: 8px;">(${health.services_running ?? 0} RUNNING)</span></div>
                    ` : ''}
                    
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
    
    if (!services || !Array.isArray(services)) {
        services = [];
    }

    const key = JSON.stringify(services);
    if (window._renderedServicesKey === key) return;
    window._renderedServicesKey = key;

    const availableServices = [
        { value: "HTTP", label: "HTTP SERVER (TCP/80)" },
        { value: "DNS", label: "DNS SERVER (UDP/53)" },
        { value: "DHCP", label: "DHCP SERVER (UDP/67)" },
        { value: "DHCP_CLIENT", label: "DHCP CLIENT (UDP/68)" },
        { value: "DHCP_RELAY", label: "DHCP RELAY (UDP/67)" },
        { value: "SSH", label: "SSH SERVER (TCP/22)" },
        { value: "SSH_CLIENT", label: "SSH CLIENT (AGENT)" },
        { value: "ECHO", label: "ECHO SERVER (TCP/7)" }
    ];
    
    let optionsHtml = "";
    for (const svc of availableServices) {
        const isActive = services.find(s => s.name === svc.value) !== undefined;
        optionsHtml += `<option value="${svc.value}" ${isActive ? 'disabled' : ''}>${svc.label}${isActive ? ' - (ACTIVE)' : ''}</option>`;
    }

    let servicesHtml = `
        <div class="ncm-config-section">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px;">
                <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px;">>_ DAEMON CONTROL</div>
                <button style="background: rgba(0,229,255,0.1); border: 1px solid #00e5ff; color: #00e5ff; font-family: monospace; font-weight: bold; padding: 2px 10px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='#00e5ff'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(0,229,255,0.1)'; this.style.color='#00e5ff';" onclick="const f = document.getElementById('add-svc-form-${deviceName}'); f.style.display = f.style.display === 'none' ? 'block' : 'none';">[ + ] INIT</button>
            </div>
            
            <div id="add-svc-form-${deviceName}" style="display: none; margin-top: 15px; border: 1px dashed rgba(0, 229, 255, 0.3); background: rgba(0, 0, 0, 0.2); padding: 15px;">
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 10px; font-weight: bold;">// INITIALIZE NEW SERVICE ROUTINE</div>
                <div style="display: grid; grid-template-columns: 1fr; gap: 10px;">
                    <select id="new-svc-preset-${deviceName}" onchange="document.getElementById('svc-config-wrapper-'+'${deviceName}').style.display = (this.value === 'DHCP_RELAY') ? 'block' : 'none';" style="background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s; cursor: pointer;">
                        ${optionsHtml}
                    </select>
                    <div id="svc-config-wrapper-${deviceName}" style="display: none;">
                        <input type="text" id="svc-target-ip-${deviceName}" placeholder="Target Server IP (e.g. 10.0.1.254)" style="background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s; width: 100%;">
                    </div>
                    
                    <button style="background: rgba(0, 229, 255, 0.1); border: 1px solid #00e5ff; color: #00e5ff; padding: 8px; font-family: monospace; font-weight: bold; letter-spacing: 2px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='#00e5ff'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(0, 229, 255, 0.1)'; this.style.color='#00e5ff';" onclick="addNCMService('${deviceName}', this.closest('.ncm-window'))">SPAWN SERVICE</button>
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
                            ${s.config && s.config.target_ip ? `<div style="color: #5c6b73;">TARGET</div><div style="color: #ffaa00;">${s.config.target_ip}</div>` : ''}
                        </div>
                    </div>
                    <div style="display: flex; gap: 6px; align-items: flex-start;">
                        ${isRunning ? 
                            `<button style="background: rgba(255, 170, 0, 0.05); border: 1px solid rgba(255, 170, 0, 0.3); color: #ffaa00; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='rgba(255, 170, 0, 0.2)'; this.style.borderColor='#ffaa00';" onmouseout="this.style.background='rgba(255, 170, 0, 0.05)'; this.style.borderColor='rgba(255, 170, 0, 0.3)';" title="Stop" onclick="manageService('${deviceName}', '${s.name}', 'stop', this.closest('.ncm-window'))">[ STOP ]</button>` :
                            `<button style="background: rgba(0, 229, 255, 0.05); border: 1px solid rgba(0, 229, 255, 0.3); color: #00e5ff; font-family: monospace; padding: 4px 8px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='rgba(0, 229, 255, 0.2)'; this.style.borderColor='#00e5ff';" onmouseout="this.style.background='rgba(0, 229, 255, 0.05)'; this.style.borderColor='rgba(0, 229, 255, 0.3)';" title="Start" onclick="manageService('${deviceName}', '${s.name}', 'start', this.closest('.ncm-window'))">[ START ]</button>`
                        }
                        
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
    const preset = document.getElementById(`new-svc-preset-${deviceName}`).value;
    
    let proto = "TCP";
    let port = 80;
    let config = {};

    if (preset === "HTTP") { proto = "TCP"; port = 80; }
    else if (preset === "DNS") { proto = "UDP"; port = 53; }
    else if (preset === "DHCP") { proto = "UDP"; port = 67; }
    else if (preset === "DHCP_CLIENT") { proto = "UDP"; port = 68; }
    else if (preset === "DHCP_RELAY") { 
        proto = "UDP"; 
        port = 67; 
        const targetIpInput = win.querySelector(`#svc-target-ip-${deviceName}`);
        if (targetIpInput && targetIpInput.value) {
            config.target_ip = targetIpInput.value;
        }
    }
    else if (preset === "SSH" || preset === "SSH_SERVER") { proto = "TCP"; port = 22; }
    else if (preset === "SSH_CLIENT") { proto = "TCP"; port = 0; }
    else if (preset === "ECHO") { proto = "TCP"; port = 7; }

    try {
        await apiRequest("POST", `/api/ncm/devices/${encodeURIComponent(deviceName)}/services`, {
            name: preset,
            protocol: proto,
            port: port,
            config: config
        });
        loadNCMDevice(deviceName, win);
    } catch (error) {
        console.error("[CHL:NCM] Failed to add service", error);
    }
}
// ========================================================
// GLOBAL NETWORK NCM
// ========================================================

function openGlobalNCM() {
    const deviceName = "GLOBAL_NETWORK";
    if (ncmWindows.has(deviceName)) {
        const existingWindow = ncmWindows.get(deviceName);
        existingWindow.hidden = false;
        existingWindow.style.zIndex = ++ncmWindowZIndex;
        loadGlobalNCM(existingWindow);
        return;
    }

    const win = document.createElement("section");
    win.className = "ncm-window";
    win.dataset.device = deviceName;
    win.style.zIndex = ++ncmWindowZIndex;

    win.innerHTML = `
        <div class="ncm-header" style="background: #05070a; border-bottom: 1px solid rgba(0, 229, 255, 0.2);">
            <div class="ncm-title" style="color: #00e5ff; font-family: monospace; letter-spacing: 2px;">
                <i class="fa-solid fa-globe" style="margin-right: 8px; opacity: 0.8;"></i>
                <span>NETWORK CONTROLLER</span>
            </div>
            <button class="ncm-close" type="button"><i class="fa-solid fa-xmark"></i></button>
        </div>
        <div class="ncm-tabs">
            <button class="ncm-tab active" data-tab="settings">SETTINGS</button>
            <button class="ncm-tab" data-tab="forger">PAYLOAD FORGER</button>
            <button class="ncm-tab" data-tab="alerts">ALERTS (HIGH)</button>
        </div>
        <div class="ncm-content">
            <div class="ncm-tab-content active" data-content="settings">
                <div class="ncm-settings-list"></div>
            </div>
            <div class="ncm-tab-content" data-content="forger">
                <div class="ncm-forger-interface"></div>
            </div>
            <div class="ncm-tab-content" data-content="alerts">
                <div class="ncm-alerts-list"></div>
            </div>
        </div>
    `;

    const header = win.querySelector(".ncm-header");
    setupNCMDragging(win, header);

    // Close Button
    win.querySelector(".ncm-close").addEventListener("click", () => {
        win.remove();
        ncmWindows.delete(deviceName);
    });

    win.addEventListener("mousedown", () => {
        win.style.zIndex = ++ncmWindowZIndex;
    });

    // Tab Switching
    const tabs = win.querySelectorAll(".ncm-tab");
    tabs.forEach(tab => {
        tab.addEventListener("click", () => {
            tabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            win.querySelectorAll(".ncm-tab-content").forEach(c => c.classList.remove("active"));
            const targetContent = win.querySelector(`[data-content="${tab.dataset.tab}"]`);
            if (targetContent) targetContent.classList.add("active");
        });
    });

    ncmWindows.set(deviceName, win);
    document.getElementById("topologyFloor").appendChild(win);
    
    // Position it centered on viewport
    const floor = document.getElementById("topologyFloor");
    const floorWidth = floor ? floor.clientWidth : window.innerWidth;
    const initialLeft = Math.max(20, Math.floor((floorWidth - 620) / 2));
    win.style.left = `${initialLeft}px`;
    win.style.top = "80px";
    win.style.transform = "none";

    loadGlobalNCM(win);
}

async function loadGlobalNCM(win) {
    try {
        const settings = await apiRequest("GET", "/api/simulation/settings");
        renderGlobalSettings(win, settings);

        renderPayloadForger(win);
        
        const events = await apiRequest("GET", "/api/simulation/events");
        renderGlobalAlerts(win, events.filter(e => e.severity === "HIGH" || e.severity === "WARNING"));
    } catch (error) {
        console.error("[CHL:NCM] Error loading global NCM:", error);
    }
}

function renderGlobalSettings(win, settings) {
    const container = win.querySelector(".ncm-settings-list");
    let html = `
        <div class="ncm-config-section">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px; margin-bottom: 15px;">
                <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px;">>_ NETWORK IDENTITY</div>
            </div>
            
            <div style="background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.05); padding: 15px;">
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// TOPOLOGY ALIAS</div>
                <input type="text" id="cfg-net-name" value="${settings.network_name || 'Cyber Hazard Network'}" style="width: 100%; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
            </div>
        </div>

        <div class="ncm-config-section" style="margin-top: 25px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px; margin-bottom: 15px;">
                <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px;">>_ INFRASTRUCTURE ROUTINES</div>
            </div>
            
            <div style="background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.05); padding: 15px;">
                
                <!-- DHCP CONFIG -->
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// DHCP ALLOCATION MODE</div>
                <select id="cfg-dhcp-mode" style="width: 100%; margin-bottom: 8px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s; cursor: pointer;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                    <option value="auto" ${settings.dhcp_mode === 'auto' ? 'selected' : ''}>AUTO (ORCHESTRATOR LEVEL)</option>
                    <option value="manual" ${settings.dhcp_mode === 'manual' ? 'selected' : ''}>MANUAL (DEPLOY DHCP DAEMONS)</option>
                </select>
                <div style="font-size: 10px; color: #5c6b73; margin-bottom: 20px; line-height: 1.4; border-left: 2px solid rgba(0, 229, 255, 0.2); padding-left: 8px;">
                    <strong style="color: #8a9ba8;">[ AUTO ]</strong> Simulation engine assigns IPs to hosts instantly.<br>
                    <strong style="color: #8a9ba8;">[ MANUAL ]</strong> Must configure a Server node with 'DHCP' service on port 67.
                </div>

                <!-- DNS CONFIG -->
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// DNS RESOLUTION MODE</div>
                <select id="cfg-dns-mode" style="width: 100%; margin-bottom: 8px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s; cursor: pointer;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                    <option value="auto" ${settings.dns_mode === 'auto' ? 'selected' : ''}>AUTO (MAGIC RESOLUTION)</option>
                    <option value="manual" ${settings.dns_mode === 'manual' ? 'selected' : ''}>MANUAL (DEPLOY DNS DAEMONS)</option>
                </select>
                <div style="font-size: 10px; color: #5c6b73; margin-bottom: 20px; line-height: 1.4; border-left: 2px solid rgba(0, 229, 255, 0.2); padding-left: 8px;">
                    <strong style="color: #8a9ba8;">[ AUTO ]</strong> Hostnames map to IPs automatically.<br>
                    <strong style="color: #8a9ba8;">[ MANUAL ]</strong> Must configure a Server node with 'DNS' service on port 53.
                </div>
                
                <!-- ROUTING CONFIG -->
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// ROUTING MODE</div>
                <select id="cfg-routing-mode" style="width: 100%; margin-bottom: 8px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s; cursor: pointer;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                    <option value="auto" ${settings.auto_routes !== false ? 'selected' : ''}>AUTO (CONNECTED SUBNETS)</option>
                    <option value="manual" ${settings.auto_routes === false ? 'selected' : ''}>MANUAL (STATIC ROUTING)</option>
                </select>
                <div style="font-size: 10px; color: #5c6b73; margin-bottom: 20px; line-height: 1.4; border-left: 2px solid rgba(0, 229, 255, 0.2); padding-left: 8px;">
                    <strong style="color: #8a9ba8;">[ AUTO ]</strong> Routers automatically generate routes for attached subnets.<br>
                    <strong style="color: #8a9ba8;">[ MANUAL ]</strong> Must manually add static routes via terminal.
                </div>

                <!-- SWITCHING CONFIG -->
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// SWITCHING MODE</div>
                <select id="cfg-switching-mode" style="width: 100%; margin-bottom: 8px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s; cursor: pointer;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                    <option value="auto" ${settings.auto_mac_learning !== false ? 'selected' : ''}>AUTO (TRANSPARENT BRIDGING)</option>
                    <option value="manual" ${settings.auto_mac_learning === false ? 'selected' : ''}>MANUAL (STATIC MAC ONLY)</option>
                </select>
                <div style="font-size: 10px; color: #5c6b73; margin-bottom: 20px; line-height: 1.4; border-left: 2px solid rgba(0, 229, 255, 0.2); padding-left: 8px;">
                    <strong style="color: #8a9ba8;">[ AUTO ]</strong> Switches automatically learn MAC addresses.<br>
                    <strong style="color: #8a9ba8;">[ MANUAL ]</strong> Unlearned packets are flooded.
                </div>
                
                <!-- TTL CONFIG -->
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// PACKET LIFESPAN (TTL / MAX HOPS)</div>
                <input type="number" id="cfg-ttl" value="${settings.default_ttl || 64}" style="width: 100%; margin-bottom: 8px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;" onfocus="this.style.borderColor='#00e5ff'" onblur="this.style.borderColor='rgba(255,255,255,0.1)'">
                <div style="font-size: 10px; color: #5c6b73; margin-bottom: 10px; border-left: 2px solid rgba(0, 229, 255, 0.2); padding-left: 8px;">
                    Limits routing loops by terminating packets after threshold hops.
                </div>
            </div>
            
            <button style="width: 100%; margin-top: 15px; background: rgba(0, 229, 255, 0.1); border: 1px solid #00e5ff; color: #00e5ff; padding: 10px; font-family: monospace; font-weight: bold; letter-spacing: 2px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='#00e5ff'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(0, 229, 255, 0.1)'; this.style.color='#00e5ff';" onclick="saveGlobalSettings(this.closest('.ncm-window'))">[ OVERRIDE SETTINGS ]</button>
        </div>
    `;
    container.innerHTML = html;
}

async function saveGlobalSettings(win) {
    const settings = {
        network_name: document.getElementById("cfg-net-name").value,
        dhcp_mode: document.getElementById("cfg-dhcp-mode").value,
        dns_mode: document.getElementById("cfg-dns-mode").value,
        auto_routes: document.getElementById("cfg-routing-mode").value === "auto",
        auto_mac_learning: document.getElementById("cfg-switching-mode").value === "auto",
        default_ttl: parseInt(document.getElementById("cfg-ttl").value) || 64
    };
    try {
        await apiRequest("POST", "/api/simulation/settings", settings);
        console.log("[CHL:NCM] Network settings applied.");
    } catch (e) {
        console.error("Failed to save network settings", e);
    }
}

function renderPayloadForger(win) {
    const container = win.querySelector(".ncm-forger-interface");
    if (!container) return;
    
    container.innerHTML = `
        <div class="ncm-config-section">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(0, 229, 255, 0.15); padding-bottom: 8px; margin-bottom: 15px;">
                <div class="ncm-section-title" style="color: #00e5ff; font-weight: bold; letter-spacing: 2px;">>_ CRAFT CUSTOM PACKET</div>
            </div>
            
            <div style="background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.05); padding: 15px;">
                
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px;">
                    <div>
                        <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// PROTOCOL</div>
                        <select id="forge-proto" style="width: 100%; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s; cursor: pointer;">
                            <option value="TCP">TCP</option>
                            <option value="UDP">UDP</option>
                            <option value="ICMP">ICMP</option>
                        </select>
                    </div>
                    <div>
                        <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// SRC PORT</div>
                        <input type="number" id="forge-src-port" placeholder="49152" value="49152" style="width: 100%; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;">
                    </div>
                    <div>
                        <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// DEST PORT</div>
                        <input type="number" id="forge-dst-port" placeholder="80" value="80" style="width: 100%; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;">
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px;">
                    <div>
                        <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// SOURCE IP (SPOOFABLE)</div>
                        <input type="text" id="forge-src" placeholder="10.0.0.5" style="width: 100%; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;">
                    </div>
                    <div>
                        <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// DESTINATION IP</div>
                        <input type="text" id="forge-dst" placeholder="10.0.1.5" style="width: 100%; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #00e5ff; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s;">
                    </div>
                </div>
                
                <div style="font-size: 10px; color: #8a9ba8; letter-spacing: 1px; margin-bottom: 8px; font-weight: bold;">// RAW PAYLOAD DATA</div>
                <textarea id="forge-payload" placeholder="Enter raw string payload (e.g. GET /index.html HTTP/1.1 or DROP TABLE USERS;)" style="width: 100%; height: 60px; background: #06090e; border: 1px solid rgba(255,255,255,0.1); color: #d5ebf2; padding: 8px; font-family: monospace; font-size: 11px; outline: none; transition: border 0.2s; resize: none; margin-bottom: 15px;"></textarea>

                <button id="forge-submit-btn" style="width: 100%; background: rgba(255, 51, 51, 0.1); border: 1px solid #ff3333; color: #ff3333; padding: 10px 15px; font-family: monospace; font-weight: bold; letter-spacing: 2px; cursor: pointer; transition: 0.2s;" onmouseover="this.style.background='#ff3333'; this.style.color='#0a0f18';" onmouseout="this.style.background='rgba(255, 51, 51, 0.1)'; this.style.color='#ff3333';" onclick="submitForgedPayload()">[ FIRE PAYLOAD ]</button>
            </div>
        </div>
    `;
}

async function submitForgedPayload() {
    const proto = document.getElementById("forge-proto").value;
    const srcPort = document.getElementById("forge-src-port").value;
    const dstPort = document.getElementById("forge-dst-port").value;
    const src = document.getElementById("forge-src").value;
    const dst = document.getElementById("forge-dst").value;
    const payload = document.getElementById("forge-payload").value;
    
    if (!dst) {
        alert("Destination IP is required!");
        return;
    }
    
    try {
        await apiRequest("POST", "/api/simulation/forge", {
            protocol: proto,
            source_port: parseInt(srcPort) || null,
            destination_port: parseInt(dstPort) || null,
            source_ip: src || null,
            destination_ip: dst,
            payload: payload
        });
        
        // Flash button green on success
        const btn = document.getElementById("forge-submit-btn");
        if (btn) {
            const oldBg = btn.style.background;
            const oldColor = btn.style.color;
            btn.style.background = "#00e5ff";
            btn.style.color = "#0a0f18";
            btn.innerText = "[ PAYLOAD INJECTED ]";
            
            setTimeout(() => {
                btn.style.background = oldBg;
                btn.style.color = oldColor;
                btn.innerText = "[ FIRE PAYLOAD ]";
            }, 1000);
        }
        
    } catch (e) {
        console.error("Payload forge failed", e);
        alert("Failed to inject payload: " + (e.message || "Unknown Error"));
    }
}
