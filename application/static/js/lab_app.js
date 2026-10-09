const CHL = {
    floor: null,
    svgLayer: null,

    devices: [],
    links: [],

    NetworkDevice: null,
    NetworkLink: null,

    DEVICE_CONFIG: {
        PC: {
            prefix: "HOST",
            icons: {
                OFFLINE: "/static/assets/PC_off.png",
                ONLINE: "/static/assets/PC_on.png",
                ERROR: "/static/assets/PC_Err.png"
            },
            icon: "/static/assets/PC_off.png" // fallback
        },
        LAPTOP: {
            prefix: "LAP",
            textLabel: "Laptop",
            icons: {
                OFFLINE: "/static/assets/LAPTOP_off.png",
                ONLINE: "/static/assets/LAPTOP_on.png",
                ERROR: "/static/assets/LAPTOP_Err.png"
            },
            icon: null
        },
        SERVER: {
            prefix: "SERV",
            icons: {
                OFFLINE: "/static/assets/SERV_off.png",
                ONLINE: "/static/assets/SERV_on.png",
                ERROR: "/static/assets/SERV_Err.png"
            },
            icon: "/static/assets/SERV_off.png" // fallback
        },
        NAS: {
            prefix: "NAS",
            icons: {
                OFFLINE: "/static/assets/NAS_off.png",
                ONLINE: "/static/assets/NAS_on.png",
                ERROR: "/static/assets/NAS_Err.png"
            },
            icon: "/static/assets/NAS_off.png"
        },
        SWITCH: {
            prefix: "SWT",
            icons: {
                OFFLINE: "/static/assets/SWITCH_off.png",
                ONLINE: "/static/assets/SWITCH_on.png",
                ERROR: "/static/assets/SWITCH_Err.png"
            },
            icon: "/static/assets/SWITCH_off.png" // fallback
        },
        ACCESSPOINT: {
            prefix: "AP",
            icons: {
                OFFLINE: "/static/assets/ACCESSPOINT_off.png",
                ONLINE: "/static/assets/ACCESSPOINT_on.png",
                ERROR: "/static/assets/ACCESSPOINT_Err.png"
            },
            icon: "/static/assets/ACCESSPOINT_off.png"
        },
        ROUTER: {
            prefix: "RUT",
            icons: {
                OFFLINE: "/static/assets/ROUTER_off.png",
                ONLINE: "/static/assets/ROUTER_on.png",
                ERROR: "/static/assets/ROUTER_Err.png"
            },
            icon: "/static/assets/ROUTER_off.png" // fallback
        }
    }
};


document.addEventListener("DOMContentLoaded", () => {

    // =========================================
    // ELEMENTS
    // =========================================

    const floor = document.getElementById("topologyFloor");
    const svgLayer = document.getElementById("linkSvgLayer");

    CHL.floor = floor;
    CHL.svgLayer = svgLayer;

    const paletteItems = document.querySelectorAll(".palette-item:not(.disabled)");
    const nodeCountEl = document.getElementById("nodeCount");
    const linkCountEl = document.getElementById("linkCount");
    const toolSelect = document.getElementById("toolSelect");
    if (!floor || !svgLayer) {
        console.error("[CHL] Topology floor or SVG layer not found.");
        return;
    }

    console.log("[CHL] Net.Creator workspace initialized.");

    // =========================================
    // STATE
    // =========================================
    let selectedDeviceId = null;
    let selectedLinkId = null;

    let hostCounter = 1;
    let serverCounter = 1;

    let linkCounter = 1;

    let activeDevice = null;
    let activeSegmentDrag = null; // { link, segmentIndex, orientation, initialMouseX, initialMouseY, initialOffset }

    // Tools: "SELECT" | "PLIERS" | "CONNECT" | "DISCONNECT" | "INSPECT" | "REMOVE" | "DUPLICATE"
    let currentTool = "SELECT";
    let pendingCutLink = null;
    let connectionSourceDevice = null;

    let draggingFromPalette = false;
    let paletteDeviceType = null;
    let creatingPaletteDevice = false;
    let dragOffsetX = 0;
    let dragOffsetY = 0;



    const devices = CHL.devices;
    const links = CHL.links;
    const DEVICE_CONFIG = CHL.DEVICE_CONFIG;
    // =========================================
    // RIBBON TAB SWITCHING
    // =========================================

    const ribbonTabs = document.querySelectorAll(".ribbon-tab");
    const ribbonPanels = document.querySelectorAll(".ribbon-toolbar");

    ribbonTabs.forEach(tab => {
        tab.addEventListener("click", () => {

            const targetPanel = tab.dataset.tab;

            // Update active tab
            ribbonTabs.forEach(t => {
                t.classList.remove("active");
            });

            tab.classList.add("active");

            // Show selected panel
            ribbonPanels.forEach(panel => {
                panel.hidden = panel.dataset.panel !== targetPanel;
            });

        });
    });




    /* =========================================
       TOOL SWITCHING LOGIC
       ========================================= */

    // Replace or update setTool in your existing app script:
    function setTool(tool) {
        currentTool = tool;
    
        // Update active highlight on horizontal ribbon buttons
        document.querySelectorAll(".tool-btn").forEach(btn => {
            btn.classList.toggle("active", btn.dataset.tool === tool);
        });

        if (toolSelect) {
            toolSelect.value = tool;
        }
    
        if (currentTool !== "CONNECT" && connectionSourceDevice) {
            connectionSourceDevice.setPendingConnect(false);
            connectionSourceDevice = null;
        }

        if (currentTool !== "PLIERS" && pendingCutLink) {
            deleteLink(pendingCutLink.id);
            pendingCutLink = null;
        }
    
        console.log(`[CHL] Active Tool switched to: ${currentTool}`);
    }
    
    // Bind button clicks inside the horizontal ribbon
    document.querySelectorAll(".tool-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            if (btn.dataset.tool) {
                setTool(btn.dataset.tool);
            } else if (btn.dataset.action) {
                handleRibbonAction(btn.dataset.action);
            } else if (btn.dataset.view) {
                handleViewAction(btn.dataset.view, btn);
            }
        });
    });

    function handleViewAction(view, btn) {
        if (view === "shortcuts") {
            const panel = document.getElementById("shortcut-panel");
            if (panel) {
                const isHidden = panel.style.display === "none";
                panel.style.display = isHidden ? "block" : "none";
                
                // Toggle active state on button
                if (isHidden) {
                    btn.classList.add("active");
                } else {
                    btn.classList.remove("active");
                }
            }
        }
        
        if (view === "grid") {
            const floor = document.getElementById("topologyFloor");
            floor.classList.toggle("hide-grid");
            if (!floor.classList.contains("hide-grid")) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
            if(CHL.links) CHL.links.forEach(l => l.updatePath());
        }
        
        if (view === "interfaces") {
            const floor = document.getElementById("topologyFloor");
            floor.classList.toggle("show-interfaces");
            if (floor.classList.contains("show-interfaces")) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
            if(CHL.links) CHL.links.forEach(l => l.updatePath());
        }

        if (view === "labels") {
            const floor = document.getElementById("topologyFloor");
            floor.classList.toggle("hide-labels");
            if (!floor.classList.contains("hide-labels")) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
            if(CHL.links) CHL.links.forEach(l => l.updatePath());
        }

        if (view === "ap-coverage") {
            const floor = document.getElementById("topologyFloor");
            floor.classList.toggle("hide-ap-coverage");
            if (!floor.classList.contains("hide-ap-coverage")) {
                btn.classList.add("active");
            } else {
                btn.classList.remove("active");
            }
        }
    }

    // Global Master Poll Object
    window.SimulationState = {
        status: "stopped",
        devices: [],
        events: []
    };
    
    let lastEventCount = 0;

    async function pollSimulationState() {
        try {
            const state = await apiRequest("GET", "/api/simulation/poll");
            window.SimulationState = state;
            
            // 1. Sync Renamed Devices from state.renames
            if (state.renames && typeof state.renames === "object") {
                for (const [oldName, newName] of Object.entries(state.renames)) {
                    if (oldName === newName) continue;
                    const localDevice = devices.find(d => d.id === oldName);
                    if (localDevice) {
                        console.log(`[CHL:POLL] Syncing renamed node: ${oldName} -> ${newName}`);
                        renameDevice(oldName, newName);
                    }
                }
            }

            // 1b. Self-healing fallback: match unmatched canvas devices with backend devices
            if (Array.isArray(state.devices) && devices.length > 0) {
                const unmatchedLocal = devices.filter(d => !state.devices.some(b => b.name === d.id));
                const unmatchedBackend = state.devices.filter(b => !devices.some(d => d.id === b.name));

                if (unmatchedLocal.length > 0 && unmatchedLocal.length === unmatchedBackend.length) {
                    for (let i = 0; i < unmatchedLocal.length; i++) {
                        const lDev = unmatchedLocal[i];
                        const bDev = unmatchedBackend.find(b => b.type.toLowerCase() === lDev.type.toLowerCase()) || unmatchedBackend[i];
                        if (bDev) {
                            console.log(`[CHL:POLL] Self-healing unmatched node: ${lDev.id} -> ${bDev.name}`);
                            renameDevice(lDev.id, bDev.name);
                            const idx = unmatchedBackend.indexOf(bDev);
                            if (idx !== -1) unmatchedBackend.splice(idx, 1);
                        }
                    }
                }
            }

            // 2. Sync Canvas Devices Status
            for (const backendDevice of state.devices) {
                const localDevice = devices.find(d => d.id === backendDevice.name);
                if (localDevice) {
                    if (backendDevice.status !== localDevice.status) {
                        localDevice.updateStatus(backendDevice.status);
                    }
                    if (backendDevice.coverage_radius !== undefined) {
                        const isRecentlyUpdated = localDevice._lastRadiusUpdateTime && (Date.now() - localDevice._lastRadiusUpdateTime < 3500);
                        if (!isRecentlyUpdated && localDevice.coverageRadius !== backendDevice.coverage_radius) {
                            localDevice.coverageRadius = backendDevice.coverage_radius;
                            if (localDevice.type && localDevice.type.toUpperCase() === "ACCESSPOINT") {
                                renderAPCoverageCircle(localDevice);
                            }
                        }
                    }
                }
            }
            
            // 3. Dispatch event to let WEL know about new logs
            if (state.events.length > 0) {
                const newEventsCount = state.events.length;
                if (newEventsCount !== lastEventCount) {
                    lastEventCount = newEventsCount;
                    const event = new CustomEvent("simulation-events-updated", { detail: state.events });
                    window.dispatchEvent(event);
                }
            }
            
        } catch (e) {
            // silent catch for background polling
        }
    }

    // Master Poll every 1000ms
    setInterval(pollSimulationState, 1000);

    async function handleRibbonAction(action) {
        if (action === "network_config") {
            if (typeof openGlobalNCM === "function") {
                openGlobalNCM();
            }
            return;
        }

        if (action === "save") {
            try {
                const state = await apiRequest("GET", "/api/simulation/export");
                const blob = new Blob([JSON.stringify(state, null, 4)], { type: "application/json" });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `network_state_${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            } catch (e) {
                console.error("Failed to save", e);
            }
            return;
        }

        if (action === "open") {
            const input = document.createElement('input');
            input.type = 'file';
            input.accept = 'application/json';
            input.onchange = async (e) => {
                const file = e.target.files[0];
                if (!file) return;
                const reader = new FileReader();
                reader.onload = async (event) => {
                    try {
                        const json = JSON.parse(event.target.result);
                        await apiRequest("POST", "/api/simulation/import", json);
                        window.location.reload();
                    } catch (err) {
                        console.error("Failed to import", err);
                        alert("Invalid simulation state file.");
                    }
                };
                reader.readAsText(file);
            };
            input.click();
            return;
        }

        if (action === "new" || action === "clear") {
            if (confirm("Reset simulation to factory defaults?")) {
                try {
                    await apiRequest("POST", "/api/simulation/reset");
                    location.reload();
                } catch (e) {
                    console.error("Failed to reset", e);
                }
            }
            return;
        }

        if (["run", "stop", "validate"].includes(action)) {
            try {
                const response = await apiRequest("POST", `/api/simulation/${action}`);
                console.log(`[CHL:SIM] ${action.toUpperCase()} action completed.`, response);
                console.log(`[CHL:SIM] ${action.toUpperCase()} action completed.`, response);
            } catch (error) {
                console.error(`[CHL:SIM] Failed to execute ${action}:`, error);
            }
        }
    }

    if (toolSelect) {
        toolSelect.addEventListener("change", (e) => setTool(e.target.value));
    }

    window.addEventListener("keydown", (e) => {
        if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return;

        const key = e.key.toUpperCase();
        if (key === "S") setTool("SELECT");
        if (key === "P") setTool("PLIERS");
        if (key === "C") setTool("CONNECT");
        if (key === "L") setTool("INSPECT");
        if (key === "X") setTool("REMOVE");
        if (key === "D") setTool("DUPLICATE");
        if (e.key === "Escape") {
            setTool("SELECT");
            deselectAll();
        }
    });

        // =========================================
    // NETWORK DEVICE
    // =========================================

    class NetworkDevice {
        constructor(id, type, status, x, y) {
            this.id = id;
            this.type = type;
            this.status = status || "OFFLINE";
            this.position = { x, y };
            if (this.type && this.type.toUpperCase() === "ACCESSPOINT") {
                this.coverageRadius = 200;
            }

            this.element = document.createElement("div");
            this.element.className = "device-node";
            this.element.dataset.id = this.id;

            this.img = document.createElement("img");
            this.img.className = "device-icon";
            this.img.alt = `${type} Host`;
            this.img.draggable = false;
            this.element.appendChild(this.img);

            this.label = document.createElement("span");
            this.label.className = "device-label";
            this.label.textContent = this.id;
            this.element.appendChild(this.label);    

            this.updatePosition(x, y);
            this.updateStatus(this.status);

            // Device dragging
            this.element.addEventListener("pointerdown", (event) => this.onPointerDown(event));
            //this.element.addEventListener("mousedown", (e) => this.onMouseDown(e));
        }

        // =====================================
        // POSITION
        // =====================================

        updatePosition(x, y) {
            this.position.x = x;
            this.position.y = y;

            this.element.style.left = `${x}px`;
            this.element.style.top = `${y}px`;

            updateDeviceConnectedLinks(this.id);
            if (this.type && this.type.toUpperCase() === "ACCESSPOINT") {
                if (typeof renderAPCoverageCircle === "function") renderAPCoverageCircle(this);
            }
            if (this.type && (this.type.toUpperCase() === "LAPTOP" || this.type.toUpperCase() === "ACCESSPOINT")) {
                if (typeof evaluateWirelessAssociations === "function") evaluateWirelessAssociations();
            }
        }

        updateStatus(status) {
            this.status = status;
            const config = CHL.DEVICE_CONFIG[this.type] || CHL.DEVICE_CONFIG.PC;
            const iconPath = config.icons ? (config.icons[this.status] || config.icons.OFFLINE) : config.icon;
            if (iconPath) {
                this.img.src = iconPath;
                this.img.style.display = "";
                if (this.placeholder) this.placeholder.style.display = "none";
            } else {
                this.img.style.display = "none";
                if (!this.placeholder) {
                    this.placeholder = document.createElement("div");
                    this.placeholder.className = "device-placeholder";
                    this.placeholder.style.cssText = "width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: bold; border: 1px dashed #00e5ff; color: #00e5ff; margin: 0 auto; background: rgba(0,229,255,0.05); border-radius: 4px; user-select: none;";
                    this.placeholder.textContent = config.textLabel || this.type;
                    this.element.insertBefore(this.placeholder, this.label);
                } else {
                    this.placeholder.style.display = "flex";
                }
            }
        }

        getCenter() {
            return {
                x: this.position.x + 32,
                y: this.position.y + 32
            };
        }

        // =====================================
        // SELECTION
        // =====================================

        setSelected(selected) {
            this.element.classList.toggle("selected", selected);
        }

        setPendingConnect(pending) {
            this.element.classList.toggle("connect-pending", pending);
        }

        // UPDATE THE HANDLER:
        onPointerDown(event) {
            if (event.button !== 0 && event.pointerType === "mouse") return;
            event.preventDefault();
            event.stopPropagation();
        
            try {
                this.element.setPointerCapture(event.pointerId);
            } catch (err) {}
        
            //handleDeviceClick(this, event);
            handleDeviceInteraction(this, event);
        }

        /* onMouseDown(event) {
            if (event.button !== 0) return;
            event.preventDefault();
            event.stopPropagation();

            handleDeviceClick(this, event);
        } */
    }

    /* =========================================
       NETWORK LINK / WIRE CLASS
       ========================================= */

    class NetworkLink {
        constructor(id, sourceDevice, targetDevice) {
            this.id = id;
            this.source = sourceDevice;
            this.target = targetDevice;

            // Manual offset for the middle orthogonal segment
            this.middleSegmentOffset = null;

            this.group = document.createElementNS("http://www.w3.org/2000/svg", "g");
            this.group.setAttribute("class", "link-group");
            this.group.setAttribute("data-id", this.id);

            // Visible path element
            this.path = document.createElementNS("http://www.w3.org/2000/svg", "path");
            this.path.setAttribute("class", "link-path");

            // Container for individual segment click hitboxes
            this.segmentsGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
            this.segmentsGroup.setAttribute("class", "segments-group");

            this.breakpoints = [];
            this.isPhysicallyCut = false;
            this.cutRatio = null;
            this.retainedEnd = "source";
                    
            // Add right-click listener to group:
            this.group.addEventListener("contextmenu", (e) => {
                e.preventDefault();
                e.stopPropagation();
                inspectLinkDetails(this);
            });

            this.group.appendChild(this.path);
            this.group.appendChild(this.segmentsGroup);

            this.updatePath();
        }

        // Calculate orthogonal sequence of points: start -> corner1 -> corner2 -> end
        getFullOrderedPoints() {
            let start = this.source.getCenter();
            
            let end = this.target.getCenter(); //const end = this.cutTargetPos ? this.cutTargetPos : this.target.getCenter();

            if (this.isPhysicallyCut && this.cutTargetPos) {
                if (this.retainedEnd === "target") {
                    start = this.cutTargetPos; // Loose end is at the source side
                } else {
                    end = this.cutTargetPos;   // Loose end is at the target side
                }
            }

            let midX = this.middleSegmentOffset !== null ? this.middleSegmentOffset : Math.round((start.x + end.x) / 2);

            const basePoints = [
                start,
                { x: midX, y: start.y },
                { x: midX, y: end.y },
                end
            ];
        
            if (this.breakpoints.length === 0) return basePoints;
        
            const combined = [start, ...this.breakpoints, end];
            const route = [];
            for (let i = 0; i < combined.length - 1; i++) {
                const pA = combined[i];
                const pB = combined[i + 1];
                const mX = Math.round((pA.x + pB.x) / 2);
                route.push(pA);
                route.push({ x: mX, y: pA.y });
                route.push({ x: mX, y: pB.y });
            }
            route.push(end);
            return route;
        }

        getRenderPoints() {
            const points = this.getFullOrderedPoints();
            if (!this.isPhysicallyCut) return points;
        
            if (this.retainedEnd === "source") {
                const cutLength = Math.max(2, Math.floor(points.length * (this.cutRatio || 0.5)));
                return points.slice(0, cutLength);
            } else {
                const startIdx = Math.min(points.length - 2, Math.floor(points.length * (1 - (this.cutRatio || 0.5))));
                return points.slice(startIdx);
            }
        }

        
        // Added for interface text
        getInterfaceLabel(sourceName, targetName) {
            const state = window.SimulationState;
            if (!state || !state.devices) return null;
            const dev = state.devices.find(d => d.name === sourceName);
            if (!dev || !dev.interfaces) return null;
            const intf = dev.interfaces.find(i => i.connected_to === targetName);
            if (!intf) return null;
            const devType = (dev.type || "").toUpperCase();
            if (devType === "SWITCH" || devType === "ACCESSPOINT") {
                return "PORT " + (intf.port_number || intf.name.replace("Port-", "")); 
            } else {
                return intf.ip_only || intf.ip || "No IP";
            }
        }

        getPointAlongPath(points, distance) {
            let traveled = 0;
            for (let i = 0; i < points.length - 1; i++) {
                const p1 = points[i];
                const p2 = points[i+1];
                const dx = p2.x - p1.x;
                const dy = p2.y - p1.y;
                const len = Math.hypot(dx, dy);
                if (traveled + len >= distance) {
                    const remaining = distance - traveled;
                    return {
                        x: p1.x + (dx / len) * remaining,
                        y: p1.y + (dy / len) * remaining
                    };
                }
                traveled += len;
            }
            if (points.length > 0) return { ...points[points.length - 1] };
            return {x: 0, y: 0};
        }

        drawLabelOnPath(originalPoints, text, thisNodeName, isSource) {
            const points = isSource ? originalPoints : [...originalPoints].reverse();
            
            let dist = 45; // base distance from center
            let finalPoint = {x: 0, y: 0};
            
            while (dist < 300) {
                finalPoint = this.getPointAlongPath(points, dist);
                let collided = false;
                
                if (CHL.svgLayer) {
                    const existing = Array.from(CHL.svgLayer.querySelectorAll(`.interface-label[data-node="${thisNodeName}"]`));
                    for (const el of existing) {
                        const ex = parseFloat(el.getAttribute("x"));
                        const ey = parseFloat(el.getAttribute("y"));
                        // 15px radius for collision
                        if (Math.hypot(ex - finalPoint.x, ey - finalPoint.y) < 18) {
                            collided = true;
                            break;
                        }
                    }
                }
                
                if (!collided) break;
                dist += 20; // slide it further down the wire
            }

            const textEl = document.createElementNS("http://www.w3.org/2000/svg", "text");
            textEl.setAttribute("x", finalPoint.x);
            textEl.setAttribute("y", finalPoint.y);
            textEl.setAttribute("class", "interface-label");
            textEl.setAttribute("data-node", thisNodeName);
            
            textEl.setAttribute("fill", "#d5ebf2");
            textEl.setAttribute("font-size", "9px");
            textEl.setAttribute("font-weight", "800");
            textEl.setAttribute("font-family", "Courier New");
            textEl.setAttribute("text-anchor", "middle");
            textEl.setAttribute("dominant-baseline", "middle");
            textEl.setAttribute("paint-order", "stroke");
            textEl.setAttribute("stroke", "rgba(5, 7, 10, 0.85)");
            textEl.setAttribute("stroke-width", "4px");
            textEl.setAttribute("stroke-linecap", "round");
            textEl.setAttribute("stroke-linejoin", "round");
            textEl.style.cursor = "default";
            textEl.style.userSelect = "none";
            
            textEl.textContent = text;
            this.group.appendChild(textEl);
        }

        updateLabels(points) {
            if (!this.group) return;
            const oldLabels = this.group.querySelectorAll(".interface-label");
            oldLabels.forEach(el => el.remove());
            
            const floor = document.getElementById("topologyFloor");
            if (!floor || !floor.classList.contains("show-interfaces")) return;
            if (points.length < 2) return;

            const srcLabelText = this.getInterfaceLabel(this.source.id, this.target.id);
            if (srcLabelText) {
                this.drawLabelOnPath(points, srcLabelText, this.source.id, true);
            }

            const tgtLabelText = this.getInterfaceLabel(this.target.id, this.source.id);
            if (tgtLabelText) {
                this.drawLabelOnPath(points, tgtLabelText, this.target.id, false);
            }
        }

        updatePath() {
            const points = this.getRenderPoints();
            if (points.length < 2) return;

            let d = `M ${points[0].x} ${points[0].y}`;
            for (let i = 1; i < points.length; i++) {
                d += ` L ${points[i].x} ${points[i].y}`;
            }
            this.path.setAttribute("d", d);
            this.path.classList.toggle("physical-cut", this.isPhysicallyCut);
            
            console.log(`[CHL:DEBUG] Wire ${this.id} path updated to: ${d}`);

            this.renderSegmentHitboxes(points);
            this.updateLabels(points);
        }


        renderSegmentHitboxes(points) {
            this.segmentsGroup.innerHTML = "";

            for (let i = 0; i < points.length - 1; i++) {
                const pA = points[i];
                const pB = points[i + 1];

                const isHorizontal = Math.abs(pA.y - pB.y) < 1;
                const isVertical = Math.abs(pA.x - pB.x) < 1;

                // Skip zero-length segments
                if (isHorizontal && Math.abs(pA.x - pB.x) < 2) continue;
                if (isVertical && Math.abs(pA.y - pB.y) < 2) continue;

                const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("x1", pA.x);
                line.setAttribute("y1", pA.y);
                line.setAttribute("x2", pB.x);
                line.setAttribute("y2", pB.y);

                const orientation = isHorizontal ? "horizontal" : "vertical";
                line.setAttribute("class", `segment-hitbox ${orientation}`);
                
                line.addEventListener("pointerdown", (e) => {
                    if (e.button !== 0 && e.pointerType === "mouse") return;
                    e.preventDefault();
                    e.stopPropagation();

                    //handleWireSegmentClick(this, i, orientation, e);
                    handleWireInteraction(this, i, orientation, e);
                });

                /* line.addEventListener("mousedown", (e) => {
                    if (e.button !== 0) return;
                    e.preventDefault();
                    e.stopPropagation();

                    handleWireSegmentClick(this, i, orientation, e);
                }); */

                this.segmentsGroup.appendChild(line);
            }
        }

        setSelected(selected) {
            this.group.classList.toggle("selected", selected);
        }
    }




    CHL.NetworkDevice = NetworkDevice;
    CHL.NetworkLink = NetworkLink;
    /* =========================================
       CENTRAL INTERACTION HANDLERS
       ========================================= */
    // not in use
    function handleDeviceClick(device, event) {
        if (currentTool === "SELECT" || currentTool === "PLIERS") {
            deselectAll();
            selectDevice(device.id);

            const rect = device.element.getBoundingClientRect();
            dragOffsetX = event.clientX - rect.left;
            dragOffsetY = event.clientY - rect.top;

            activeDevice = device;
            draggingFromPalette = false;

        } else if (currentTool === "CONNECT") {
            handleConnectClick(device);

        } else if (currentTool === "INSPECT") {
            deselectAll();
            selectDevice(device.id);
            console.log(`[CHL] INSPECT Config Tool -> Opened Inspection interface for ${device.id}`);
        }
    }

    /* =========================================
        INTERACTION ROUTING ENGINE
       ========================================= */

    function handleDeviceInteraction(device, event) {
        switch (currentTool) {
            case "SELECT":
                executeSelectDevice(device, event);
                break;
            case "CONNECT":
                executeConnectDevice(device);
                break;
            case "INSPECT":
                executeInspectDevice(device);
                break;
            case "REMOVE":
                executeRemoveDevice(device);
                break;
            case "DUPLICATE":
                executeDuplicateDevice(device);
                break;
            case "PLIERS":
                // Reconnecting a cut wire to this device:
                if (pendingCutLink) {
                    executePliersReconnect(device);
                }
                break;
        }
    }

    function handleWireInteraction(link, segmentIndex, orientation, event) {
        switch (currentTool) {
            case "SELECT":
                executeSelectWire(link, segmentIndex, orientation, event);
                break;
            case "PLIERS":
                executePliersCut(link, segmentIndex, event);
                break;
            case "INSPECT":
                inspectLinkDetails(link);
                break;
            case "REMOVE":
                executeRemoveLink(link);
                break;
        }
    }

    function executeSelectDevice(device, event) {
        deselectAll();
        selectDevice(device.id);

        const rect = device.element.getBoundingClientRect();
        dragOffsetX = event.clientX - rect.left;
        dragOffsetY = event.clientY - rect.top;

        activeDevice = device;
        draggingFromPalette = false;
    }

    function executeSelectWire(link, segmentIndex, orientation, event) {
        deselectAll();
        selectLink(link.id);

        const floorRect = floor.getBoundingClientRect();
        const points = link.getFullOrderedPoints();

        activeSegmentDrag = {
            link: link,
            segmentIndex: segmentIndex,
            orientation: orientation,
            initialMouseX: event.clientX - floorRect.left,
            initialMouseY: event.clientY - floorRect.top,
            initialOffset: link.middleSegmentOffset !== null ? link.middleSegmentOffset : points[1].x
        };
    }

    function executePliersCut(link, segmentIndex, event) {
        deselectAll();
        selectLink(link.id);

        const floorRect = floor.getBoundingClientRect();
        const clickX = Math.round(event.clientX - floorRect.left);
        const clickY = Math.round(event.clientY - floorRect.top);

        const start = link.source.getCenter();
        const end = link.target.getCenter();
        const distSource = Math.hypot(start.x - clickX, start.y - clickY);
        const distTarget = Math.hypot(end.x - clickX, end.y - clickY);

        link.retainedEnd = distSource < distTarget ? "target" : "source";
        link.isPhysicallyCut = true;
        link.cutTargetPos = { x: clickX, y: clickY };
        link.updatePath();

        pendingCutLink = link;
        console.log(`[CHL:PLIERS] Wire severed. Click any device to connect the loose end.`);

        fetch("/api/ntm/disconnect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                device_a: link.source.id,
                device_b: link.target.id
            })
        })
        .then(res => {
            if (!res.ok) throw new Error("Backend disconnect failed");
            return res.json();
        })
        .then(data => console.log("[CHL:API] Backend disconnected:", data))
        .catch(err => console.error("[CHL:API] API Error:", err));
    }

    function executeConnectDevice(device) {
        const isLaptop = d => d && d.type && d.type.toUpperCase() === "LAPTOP";
        if (isLaptop(device) || isLaptop(connectionSourceDevice)) {
            console.warn("[CHL] Laptops only connect wirelessly to Access Points and cannot be cabled via Connect tool.");
            if (connectionSourceDevice) {
                connectionSourceDevice.setPendingConnect(false);
                connectionSourceDevice = null;
            }
            return;
        }

        if (!connectionSourceDevice) {
            connectionSourceDevice = device;
            connectionSourceDevice.setPendingConnect(true);
        } else {
            if (connectionSourceDevice.id === device.id) return;
            const sourceDevice = connectionSourceDevice;
            const targetDevice = device;
            connectDevices( connectionSourceDevice, device ).then(() => {
            
                createConnection( sourceDevice, targetDevice );
                connectionSourceDevice = null;
            }).catch(error => {
            
                console.error( "[CHL] Failed to connect devices:", error );
            });

            connectionSourceDevice.setPendingConnect(false);
            connectionSourceDevice = null;
            //setTool("SELECT");
        }
    }
    
    async function executeInspectDevice(device) {
        deselectAll();
        selectDevice(device.id);
        //console.log(`%c[CHL:INSPECT] Device: ${device.id}`, "color: #00e5ff; font-weight: bold;");
        //console.table({ ID: device.id, Type: device.type, Position: `X: ${device.position.x}, Y: ${device.position.y}` });
        openNCM(device);

    }

    function inspectLinkDetails(link) {
        console.log(`%c[CHL:INSPECT] NetworkLink: ${link.id}`, "color: #00e5ff; font-weight: bold;");
        console.table({
            ID: link.id,
            Source: link.source.id,
            Target: link.target.id,
            Cut: link.isPhysicallyCut,
            Retained: link.retainedEnd,
            Breakpoints: link.breakpoints.length
        });
        console.log("Ordered Points:", link.getFullOrderedPoints());
    }

    function executePliersReconnect(device) {
        if (!pendingCutLink) return;

        if (device.id === pendingCutLink.source.id) {
            console.warn("[CHL:PLIERS] Cannot connect wire back to its own source.");
            return;
        }

        if (pendingCutLink.retainedEnd === "target") {
            pendingCutLink.source = device;
        } else {
            pendingCutLink.target = device
        }

        pendingCutLink.target = device;
        pendingCutLink.cutTargetPos = null;
        pendingCutLink.isPhysicallyCut = false;
        pendingCutLink.middleSegmentOffset = null;
        pendingCutLink.updatePath();

        console.log(`[CHL:PLIERS] Reconnected wire to ${device.id}`);
        

        fetch("/api/ntm/connect", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                device_a: pendingCutLink.source.id,
                device_b: pendingCutLink.target.id
            })
        })
        .then(res => {
            if (!res.ok) throw new Error("Backend connect failed");
            return res.json();
        })
        .then(data => console.log("[CHL:API] Backend connected:", data))
        .catch(err => console.error("[CHL:API] API Error:", err));

        pendingCutLink = null;
        setTool("SELECT");
    }

    async function executeRemoveDevice(device) {
        deselectAll();
        
        try {
            const response = await apiRequest(
                "DELETE",
                "/api/ntm/devices",
                {
                    name: device.name || device.id,
                }
            );
            
            // 1. Remove all connected links safely
            const connected = links.filter(l => l.source.id === device.id || l.target.id === device.id);
            connected.forEach(l => deleteLink(l.id));
            
            // 2. Remove DOM element
            if (device.element && device.element.parentNode) {
                device.element.parentNode.removeChild(device.element);
            }
        
            // 3. Remove from internal devices array
            const idx = devices.findIndex(d => d.id === device.id);
            if (idx !== -1) {
                devices.splice(idx, 1);
            }
    
            updateCounts();
            if (device.type && device.type.toUpperCase() === "ACCESSPOINT") {
                removeAPCoverageCircle(device.id);
            }
            evaluateWirelessAssociations();
            console.log(`[CHL:REMOVE] Device ${device.id} removed.`);
        } catch (error) {
            console.error(`[CHL:REMOVE] Failed to remove ${device.id}:`, error);
        }
    }
    
    function executeRemoveLink(link) {
        deselectAll();
        
        if (!link.isPhysicallyCut) {
            fetch("/api/ntm/disconnect", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    device_a: link.source.id,
                    device_b: link.target.id
                })
            })
            .then(res => {
                if (!res.ok) throw new Error("Backend disconnect failed");
                return res.json();
            })
            .then(data => console.log("[CHL:API] Backend disconnected:", data))
            .catch(err => console.error("[CHL:API] API Error:", err));
        }

        deleteLink(link.id);
        console.log(`[CHL:REMOVE] Wire ${link.id} removed.`);
    }
    
    function executeDuplicateDevice(device) {
        deselectAll();
    
        // Offset position by +40px so duplicate is visible
        const newX = device.position.x + 40;
        const newY = device.position.y + 40;
    
        const dup = createDevice(device.type, newX, newY);
        selectDevice(dup.id);
        console.log(`[CHL:DUPLICATE] Created duplicate ${dup.id} from ${device.id}`);
        //setTool("SELECT");
    }


    // =========================================
    // SELECTION
    // =========================================

    function selectDevice(id) {
        if (selectedDeviceId === id) return;

        if (selectedDeviceId !== null) {
            const prev = devices.find(d => d.id === selectedDeviceId);
            if (prev) prev.setSelected(false);
        }

        selectedDeviceId = id;
        const current = devices.find(d => d.id === selectedDeviceId);
        if (current) current.setSelected(true);
    }

    function selectLink(id) {
        if (selectedLinkId === id) return;

        if (selectedLinkId !== null) {
            const prev = links.find(l => l.id === selectedLinkId);
            if (prev) prev.setSelected(false);
        }

        selectedLinkId = id;
        const current = links.find(l => l.id === selectedLinkId);
        if (current) current.setSelected(true);
    }

    function deselectAll() {
        if (selectedDeviceId !== null) {
            const current = devices.find(d => d.id === selectedDeviceId);
            if (current) current.setSelected(false);
            selectedDeviceId = null;
        }

        if (selectedLinkId !== null) {
            const current = links.find(l => l.id === selectedLinkId);
            if (current) current.setSelected(false);
            selectedLinkId = null;
        }

        if (connectionSourceDevice) {
            connectionSourceDevice.setPendingConnect(false);
            connectionSourceDevice = null;
        }
    }

    function createConnection(sourceDevice, targetDevice) {
        const exists = links.some(l =>
            !l.isPhysicallyCut && (
                (l.source.id === sourceDevice.id && l.target.id === targetDevice.id) ||
                (l.source.id === targetDevice.id && l.target.id === sourceDevice.id)
            )
        );

        if (exists) {
            console.warn(`[CHL] Connection already exists between ${sourceDevice.id} and ${targetDevice.id}`);
            return null;
        }

        const linkNum = getNextDeviceNumber("LINK-", links);
        const linkId = `LINK-${String(linkNum).padStart(2, "0")}`;

        const link = new NetworkLink(linkId, sourceDevice, targetDevice);
        links.push(link);
        svgLayer.appendChild(link.group);
        
        // Wait for DOM flush before updating path, matching the topology.js trick
        requestAnimationFrame(() => {
            link.updatePath();
        });

        updateCounts();
        console.log(`[CHL] Created wire ${linkId} (${sourceDevice.id} <-> ${targetDevice.id})`);
        return link;
    }

    /* =========================================
       LINK DELETION HELPER
       ========================================= */

    function deleteLink(linkId) {
        const index = links.findIndex(l => l.id === linkId);
        if (index === -1) return;

        const link = links[index];

        if (link.group && link.group.parentNode) {
            link.group.parentNode.removeChild(link.group);
        }

        if (selectedLinkId === linkId) {
            selectedLinkId = null;
        }

        if (typeof pendingCutLink !== "undefined" && pendingCutLink && pendingCutLink.id === linkId) {
            pendingCutLink = null;
        }

        links.splice(index, 1);
        updateCounts();

        console.log(`[CHL] Cut/Removed wire ${linkId}`);
    }

    function updateDeviceConnectedLinks(deviceId) {
        links.forEach(link => {
            if (link.source.id === deviceId || link.target.id === deviceId) {
                link.updatePath();
            }
        });
    }

    // Generalized Device Factory
    async function createDevice(type = "PC", x = 0, y = 0) {

        const config = DEVICE_CONFIG[type] || DEVICE_CONFIG.PC;
        let id;

        if (!window._deviceCounters) window._deviceCounters = {};
        if (window._deviceCounters[config.prefix] === undefined) {
            let max = -1;
            devices.forEach(device => {
                if (!device.id.startsWith(config.prefix)) return;
                const numStr = device.id.split('-').pop();
                const number = Number(numStr);
                if (!Number.isNaN(number)) max = Math.max(max, number);
            });
            const renames = (window.SimulationState && window.SimulationState.renames) || {};
            for (const oldName of Object.keys(renames)) {
                if (oldName.startsWith(config.prefix)) {
                    const numStr = oldName.split('-').pop();
                    const number = Number(numStr);
                    if (!Number.isNaN(number)) max = Math.max(max, number);
                }
            }
            window._deviceCounters[config.prefix] = max >= 0 ? max + 1 : 1;
            // Also factor in the legacy counters if they were used
            if (config.prefix === "HOST" && hostCounter > window._deviceCounters[config.prefix]) {
                window._deviceCounters[config.prefix] = hostCounter;
            }
            if (config.prefix === "SERV" && serverCounter > window._deviceCounters[config.prefix]) {
                window._deviceCounters[config.prefix] = serverCounter;
            }
        }
        
        id = `${config.prefix}-${String(window._deviceCounters[config.prefix]).padStart(2, "0")}`;
        window._deviceCounters[config.prefix]++;

        const backendDevice = await apiRequest(
            "POST",
            "/api/ntm/devices",
            {
                name: id,
                type: type.toLowerCase()
            }
        );

        console.log(
            `[CHL] Backend created ${backendDevice.name} (${backendDevice.type})`
        );

        const device = new NetworkDevice( backendDevice.name, type, backendDevice.status, x, y
        );

        if (backendDevice.coverage_radius !== undefined) {
            device.coverageRadius = backendDevice.coverage_radius;
        } else if (type.toUpperCase() === "ACCESSPOINT") {
            device.coverageRadius = 200;
        }

        devices.push(device);
        floor.appendChild(device.element);
        updateCounts();

        if (type.toUpperCase() === "ACCESSPOINT") {
            renderAPCoverageCircle(device);
        }
        evaluateWirelessAssociations();

        console.log(
            `[CHL] Created visual device ${device.id} (${type})`
        );

        return device;
    }

    // Preserve createHost for existing prototype scene initialization
    async function createHost(x = 0, y = 0) {
        return createDevice("PC", x, y);
    }


    // =========================================
    // NODE COUNT
    // =========================================

    function updateCounts() {
        if (nodeCountEl) nodeCountEl.textContent = devices.length;
        if (linkCountEl) linkCountEl.textContent = links.length;
    }

    // =========================================
    // CALCULATE FLOOR POSITION
    // =========================================

    function getFloorPosition(clientX, clientY) {
        const floorRect = floor.getBoundingClientRect();

        let x = clientX - floorRect.left - dragOffsetX;
        let y = clientY - floorRect.top - dragOffsetY;

        const deviceWidth = activeDevice
            ? activeDevice.element.offsetWidth
            : 64;

        const deviceHeight = activeDevice
            ? activeDevice.element.offsetHeight
            : 64;

        const maxX = floor.clientWidth - deviceWidth;
        const maxY = floor.clientHeight - deviceHeight;

        x = Math.max(0, Math.min(x, maxX));
        y = Math.max(0, Math.min(y, maxY));

        return { x, y };
    }

    // =========================================
    // PALETTE DRAG START
    // =========================================

    paletteItems.forEach(item => {
        item.addEventListener("pointerdown", (event) => {
            if (event.button !== 0 && event.pointerType === "mouse") return;
            event.preventDefault();
            
            const type = item.dataset.type;
            // Removed: if (type !== "PC" && type !== "SERVER") return;
            
            draggingFromPalette = true;
            paletteDeviceType = type;
            dragOffsetX = 32;
            dragOffsetY = 32;
            activeDevice = null;
        });
    });


    window.addEventListener("pointermove", (event) => {
        if (activeSegmentDrag) {
            const floorRect = floor.getBoundingClientRect();
            const currentMouseX = event.clientX - floorRect.left;
            const deltaX = currentMouseX - activeSegmentDrag.initialMouseX;
            let newMidX = activeSegmentDrag.initialOffset + deltaX;

            newMidX = Math.max(10, Math.min(newMidX, floor.clientWidth - 10));
            activeSegmentDrag.link.middleSegmentOffset = newMidX;
            activeSegmentDrag.link.updatePath();
            return;
        }

        if (draggingFromPalette) {
            const floorRect = floor.getBoundingClientRect();
            const insideFloor =
                event.clientX >= floorRect.left &&
                event.clientX <= floorRect.right &&
                event.clientY >= floorRect.top &&
                event.clientY <= floorRect.bottom;

            if ( insideFloor && activeDevice === null && !creatingPaletteDevice) {
                
                    creatingPaletteDevice = true;
                    createDevice(paletteDeviceType).then(device => {    
                        
                            activeDevice = device;
                            const position = getFloorPosition( event.clientX, event.clientY );
                            activeDevice.updatePosition( position.x, position.y );
                        
                        }).catch(error => {
                        
                            console.error( "[CHL] Failed to create device:", error );
                        
                        }).finally(() => { creatingPaletteDevice = false; });
                }

            if (activeDevice) {
                const position = getFloorPosition(event.clientX, event.clientY);
                activeDevice.updatePosition(position.x, position.y);
            }
            return;
        }

        if (activeDevice) {
            const position = getFloorPosition(event.clientX, event.clientY);
            activeDevice.updatePosition(position.x, position.y);
        }
    });



    // =========================================
    // GLOBAL MOUSE RELEASE
    // =========================================

    function handlePointerRelease(event) {
        if (draggingFromPalette) {
            if (activeDevice) {
                console.log(`[CHL] Placed ${activeDevice.id}`);
            }
        }

        if (activeDevice && activeDevice.element) {
            try {
                if (activeDevice.element.hasPointerCapture(event.pointerId)) {
                    activeDevice.element.releasePointerCapture(event.pointerId);
                }
            } catch (err) {}
        }

        if (activeDevice) {
            saveLayout();
        }

        activeDevice = null;
        activeSegmentDrag = null;
        draggingFromPalette = false;
        paletteDeviceType = null;
        creatingPaletteDevice = false;

        evaluateWirelessAssociations();
    }

    async function saveLayout() {
        const layout = {};
        devices.forEach(d => {
            layout[d.id] = { x: d.position.x, y: d.position.y };
        });
        try {
            await apiRequest("POST", "/api/ntm/layout", layout);
            console.log("[CHL:API] Layout saved.");
        } catch (e) {
            console.error("[CHL:API] Failed to save layout", e);
        }
    }

    function renameDevice(oldId, newId) {
        if (!oldId || !newId || oldId === newId) return false;
        const dev = devices.find(d => d.id === oldId);
        if (!dev) return false;

        dev.id = newId;
        dev.element.dataset.id = newId;
        if (dev.label) dev.label.textContent = newId;

        if (selectedDeviceId === oldId) {
            selectedDeviceId = newId;
        }

        updateDeviceConnectedLinks(newId);

        if (svgLayer) {
            const circle = svgLayer.querySelector(`.ap-coverage-circle[data-device="${oldId}"]`);
            if (circle) circle.setAttribute("data-device", newId);
        }

        // Also update open NCM window if open under oldId
        if (typeof ncmWindows !== 'undefined' && ncmWindows.has(oldId)) {
            const win = ncmWindows.get(oldId);
            ncmWindows.delete(oldId);
            ncmWindows.set(newId, win);
            win.dataset.device = newId;
            const titleEl = win.querySelector(".ncm-title span");
            if (titleEl) titleEl.innerText = newId;
            const termPrompt = win.querySelector(".ncm-terminal-prompt");
            if (termPrompt) {
                termPrompt.id = `term-prompt-${newId}`;
                termPrompt.innerText = `user@${newId.toLowerCase()}:~$`;
            }
            const termInput = win.querySelector(".ncm-terminal-input");
            if (termInput) {
                const safeNewId = newId.replace(/'/g, "\\'");
                termInput.setAttribute("onkeydown", `handleTerminalInput(event, '${safeNewId}')`);
            }
            const closeBtn = win.querySelector(".ncm-close");
            if (closeBtn) {
                closeBtn.onclick = () => closeNCM(newId);
            }
            if (typeof loadNCMDevice === "function") {
                loadNCMDevice(newId, win);
            }
        }

        saveLayout();
        window.dispatchEvent(new CustomEvent("device-renamed", { detail: { oldId, newId } }));
        console.log(`[CHL] Renamed canvas device ${oldId} -> ${newId}`);
        return true;
    }
    CHL.renameDevice = renameDevice;

    // REPLACE window.addEventListener("mouseup") WITH:
    window.addEventListener("pointerup", handlePointerRelease);
    window.addEventListener("pointercancel", handlePointerRelease);

    // 3. FLOOR DESELECTION
    floor.addEventListener("pointerdown", (event) => {
        if (event.target === floor || event.target === svgLayer) {
            deselectAll();
            if (typeof pendingCutLink !== 'undefined' && pendingCutLink) {
                deleteLink(pendingCutLink.id);
                pendingCutLink = null;
                setTool("SELECT");
            }
        }
    });


    window.addEventListener("mouseup", () => {
        if (draggingFromPalette) {
            if (activeDevice) {
                console.log(`[CHL] Placed ${activeDevice.id}`);
            } else {
                console.log("[CHL] Palette drag cancelled.");
            }
        }

        activeDevice = null;
        activeSegmentDrag = null;
        draggingFromPalette = false;
        paletteDeviceType = null;
    });

    // =========================================
    // FLOOR CLICK
    // =========================================

    floor.addEventListener("mousedown", (event) => {
        if (event.target === floor || event.target === svgLayer) {
            deselectAll();
        }
    });

    /* =========================================
       WIRELESS COVERAGE & ASSOCIATIONS
       ========================================= */

    function getOrCreateAPCoverageLayer() {
        let layer = document.getElementById("apCoverageLayer");
        if (!layer && svgLayer) {
            layer = document.createElementNS("http://www.w3.org/2000/svg", "g");
            layer.setAttribute("id", "apCoverageLayer");
            layer.setAttribute("class", "ap-coverage-layer");
            svgLayer.insertBefore(layer, svgLayer.firstChild);
        }
        return layer;
    }

    function renderAPCoverageCircle(device) {
        if (!device || !device.type || device.type.toUpperCase() !== "ACCESSPOINT") return;
        const layer = getOrCreateAPCoverageLayer();
        if (!layer) return;

        let circle = layer.querySelector(`.ap-coverage-circle[data-device="${device.id}"]`);
        if (!circle) {
            circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("class", "ap-coverage-circle");
            circle.setAttribute("data-device", device.id);
            layer.appendChild(circle);
        }
        const center = device.getCenter();
        const radius = device.coverageRadius !== undefined ? device.coverageRadius : 200;
        circle.setAttribute("cx", center.x);
        circle.setAttribute("cy", center.y);
        circle.setAttribute("r", radius);
    }

    function removeAPCoverageCircle(deviceId) {
        const layer = getOrCreateAPCoverageLayer();
        if (!layer) return;
        const circle = layer.querySelector(`.ap-coverage-circle[data-device="${deviceId}"]`);
        if (circle) circle.remove();
    }

    function updateAllAPCoverageCircles() {
        devices.forEach(dev => {
            if (dev.type && dev.type.toUpperCase() === "ACCESSPOINT") {
                renderAPCoverageCircle(dev);
            }
        });
    }

    window.updateAPCoverageRadius = function(deviceId, newRadius) {
        const dev = devices.find(d => d.id === deviceId);
        if (dev) {
            dev.coverageRadius = Number(newRadius);
            dev._lastRadiusUpdateTime = Date.now();
            renderAPCoverageCircle(dev);
            evaluateWirelessAssociations();

            if (dev._saveRadiusTimeout) clearTimeout(dev._saveRadiusTimeout);
            dev._saveRadiusTimeout = setTimeout(() => {
                fetch(`/api/ncm/devices/${encodeURIComponent(deviceId)}/config`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ coverage_radius: Number(newRadius) })
                }).then(() => {
                    dev._lastRadiusUpdateTime = Date.now();
                }).catch(() => {});
            }, 100);
        }
    };

    const pendingWirelessOps = new Set();

    async function evaluateWirelessAssociations() {
        const laptops = devices.filter(d => d.type && d.type.toUpperCase() === "LAPTOP");
        const aps = devices.filter(d => d.type && d.type.toUpperCase() === "ACCESSPOINT");

        for (const laptop of laptops) {
            if (pendingWirelessOps.has(laptop.id)) continue;

            const laptopCenter = laptop.getCenter();

            // Find existing link between this laptop and an AP
            const existingLink = links.find(l =>
                !l.isPhysicallyCut &&
                ((l.source.id === laptop.id && l.target.type && l.target.type.toUpperCase() === "ACCESSPOINT") ||
                 (l.target.id === laptop.id && l.source.type && l.source.type.toUpperCase() === "ACCESSPOINT"))
            );

            let connectedAP = null;
            if (existingLink) {
                connectedAP = (existingLink.source.id === laptop.id) ? existingLink.target : existingLink.source;
            }

            // 1. If currently connected to an AP, check if still within its coverage radius
            if (connectedAP) {
                const apCenter = connectedAP.getCenter();
                const dist = Math.hypot(laptopCenter.x - apCenter.x, laptopCenter.y - apCenter.y);
                const radius = connectedAP.coverageRadius !== undefined ? connectedAP.coverageRadius : 200;

                if (dist > radius) {
                    console.log(`[CHL:WIRELESS] Laptop ${laptop.id} moved out of range of AP ${connectedAP.id} (dist: ${dist.toFixed(1)}px > radius: ${radius}px). Disconnecting.`);
                    pendingWirelessOps.add(laptop.id);
                    deleteLink(existingLink.id);

                    try {
                        await apiRequest("POST", "/api/ntm/disconnect", {
                            device_a: laptop.id,
                            device_b: connectedAP.id
                        });
                    } catch (err) {
                        console.warn(`[CHL:WIRELESS] Failed to disconnect ${laptop.id} from ${connectedAP.id}:`, err);
                    } finally {
                        pendingWirelessOps.delete(laptop.id);
                    }

                    // Disconnected - check below if entering another AP
                    connectedAP = null;
                } else {
                    // Still in range: ensure styled with .wireless-link
                    if (!existingLink.isWireless) {
                        existingLink.isWireless = true;
                        if (existingLink.group) existingLink.group.classList.add("wireless-link");
                    }
                    continue;
                }
            }

            // 2. If laptop has NO connection, check if it entered any AP radius
            if (!connectedAP && aps.length > 0) {
                const inRangeAPs = [];
                for (const ap of aps) {
                    const apCenter = ap.getCenter();
                    const dist = Math.hypot(laptopCenter.x - apCenter.x, laptopCenter.y - apCenter.y);
                    const radius = ap.coverageRadius !== undefined ? ap.coverageRadius : 200;
                    if (dist <= radius) {
                        inRangeAPs.push({ ap, dist });
                    }
                }

                if (inRangeAPs.length > 0) {
                    let minDist = Math.min(...inRangeAPs.map(i => i.dist));
                    const candidates = inRangeAPs.filter(i => Math.abs(i.dist - minDist) < 0.5);

                    let chosen;
                    if (candidates.length === 1) {
                        chosen = candidates[0].ap;
                    } else {
                        // Equidistant tie-breaker: connect randomly
                        const randIdx = Math.floor(Math.random() * candidates.length);
                        chosen = candidates[randIdx].ap;
                        console.log(`[CHL:WIRELESS] Equidistant APs for ${laptop.id}. Randomly chosen: ${chosen.id}`);
                    }

                    console.log(`[CHL:WIRELESS] Auto-connecting ${laptop.id} to AP ${chosen.id} (dist: ${minDist.toFixed(1)}px).`);
                    pendingWirelessOps.add(laptop.id);

                    const newLink = createConnection(laptop, chosen);
                    if (newLink) {
                        newLink.isWireless = true;
                        if (newLink.group) newLink.group.classList.add("wireless-link");
                    }

                    try {
                        await connectDevices(laptop, chosen);
                    } catch (err) {
                        console.error(`[CHL:WIRELESS] Failed to connect ${laptop.id} to ${chosen.id}:`, err);
                        if (newLink) deleteLink(newLink.id);
                    } finally {
                        pendingWirelessOps.delete(laptop.id);
                    }
                }
            }
        }
    }

    /* =========================================
       INITIALIZATION: PROTOTYPE SCENE
       ========================================= */

    async function initPrototypeScene() {

        const floorWidth = floor.clientWidth || 800;
        const floorHeight = floor.clientHeight || 500;

        const host1X = Math.floor(floorWidth * 0.25) - 32;
        const host1Y = Math.floor(floorHeight * 0.4) - 32;

        const host2X = Math.floor(floorWidth * 0.70) - 32;
        const host2Y = Math.floor(floorHeight * 0.6) - 32;

        const host1 = await createHost(host1X,host1Y);

        const host2 = await createHost(host2X,host2Y);

        createConnection( host1, host2 );
    }

    //initPrototypeScene();
    hostCounter = getNextDeviceNumber("HOST-", devices);
    serverCounter = getNextDeviceNumber("SERV-", devices);

    loadDevices()
    .then(() => loadLinks())
    .then(() => {
        updateCounts();
        updateAllAPCoverageCircles();
        evaluateWirelessAssociations();
    })
    .catch(error => {
        console.error(
            "[CHL] Failed to load topology:",
            error
        );
    });
});
