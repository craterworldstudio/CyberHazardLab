
document.addEventListener("DOMContentLoaded", () => {

    // =========================================
    // ELEMENTS
    // =========================================

    const floor = document.getElementById("topologyFloor");
    const svgLayer = document.getElementById("linkSvgLayer");
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

    const devices = [];
    const links = [];

    let selectedDeviceId = null;
    let selectedLinkId = null;

    let hostCounter = 1;
    let serverCounter = 1;

    // Device visual asset mapping
    const DEVICE_CONFIG = {
        PC: {
            prefix: "HOST",
            icon: "/static/assets/PC_off.png"
        },
        SERVER: {
            prefix: "SERV",
            icon: "/static/assets/server_off.png"
        }
    };
    let linkCounter = 1;

    let activeDevice = null;
    let activeSegmentDrag = null; // { link, segmentIndex, orientation, initialMouseX, initialMouseY, initialOffset }

    // Tools: "SELECT" | "PLIERS" | "CONNECT" | "DISCONNECT" | "INSPECT" | "REMOVE" | "DUPLICATE"
    let currentTool = "SELECT";
    let pendingCutLink = null;
    let connectionSourceDevice = null;

    let draggingFromPalette = false;
    let paletteDeviceType = null;
    let dragOffsetX = 0;
    let dragOffsetY = 0;

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
            pendingCutLink = null;
        }
    
        console.log(`[CHL] Active Tool switched to: ${currentTool}`);
    }
    
    // Bind button clicks inside the horizontal ribbon
    document.querySelectorAll(".tool-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            setTool(btn.dataset.tool);
        });
    });

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
        constructor(id, type, iconPath, x, y) {
            this.id = id;
            this.type = type;
            this.position = { x, y };

            this.element = document.createElement("div");
            this.element.className = "device-node";
            this.element.dataset.id = this.id;

            this.img = document.createElement("img");
            this.img.className = "device-icon";
            this.img.src = iconPath;
            this.img.alt = `${type} Host`;
            this.img.draggable = false;
            this.element.appendChild(this.img);

            this.label = document.createElement("span");
            this.label.className = "device-label";
            this.label.textContent = this.id;
            this.element.appendChild(this.label);    

            this.updatePosition(x, y);

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
            const start = this.source.getCenter();
            
            const end = this.cutTargetPos ? this.cutTargetPos : this.target.getCenter();
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

        updatePath() {
            const points = this.getRenderPoints();
            if (points.length < 2) return;

            let d = `M ${points[0].x} ${points[0].y}`;
            for (let i = 1; i < points.length; i++) {
                d += ` L ${points[i].x} ${points[i].y}`;
            }
            this.path.setAttribute("d", d);
            this.path.classList.toggle("physical-cut", this.isPhysicallyCut);
        
            this.renderSegmentHitboxes(points);
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

    /* =========================================
       CENTRAL INTERACTION HANDLERS
       ========================================= */

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
                deselectAll();
                deleteLink(link.id);
                console.log(`[CHL:REMOVE] Wire ${link.id} removed.`);
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

        link.isPhysicallyCut = true;
        link.cutTargetPos = { x: clickX, y: clickY };
        link.updatePath();

        pendingCutLink = link;
        console.log(`[CHL:PLIERS] Wire severed. Click any device to connect the loose end.`);
    }

    function executeConnectDevice(device) {
        if (!connectionSourceDevice) {
            connectionSourceDevice = device;
            connectionSourceDevice.setPendingConnect(true);
        } else {
            if (connectionSourceDevice.id === device.id) return;
            createConnection(connectionSourceDevice, device);
            connectionSourceDevice.setPendingConnect(false);
            connectionSourceDevice = null;
            //setTool("SELECT");
        }
    }
    
    function executeInspectDevice(device) {
        deselectAll();
        selectDevice(device.id);
        console.log(`%c[CHL:INSPECT] Device: ${device.id}`, "color: #00e5ff; font-weight: bold;");
        console.table({ ID: device.id, Type: device.type, Position: `X: ${device.position.x}, Y: ${device.position.y}` });
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

        pendingCutLink.target = device;
        pendingCutLink.cutTargetPos = null;
        pendingCutLink.isPhysicallyCut = false;
        pendingCutLink.middleSegmentOffset = null;
        pendingCutLink.updatePath();

        console.log(`[CHL:PLIERS] Reconnected wire to ${device.id}`);
        pendingCutLink = null;
        setTool("SELECT");
    }
    function executeRemoveDevice(device) {
        deselectAll();
        
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
        console.log(`[CHL:REMOVE] Device ${device.id} removed.`);
    }
    
    function executeDuplicateDevice(device) {
        deselectAll();
    
        // Offset position by +40px so duplicate is visible
        const newX = device.position.x + 40;
        const newY = device.position.y + 40;
    
        const dup = createHost(newX, newY);
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

        const linkId = `LINK-${String(linkCounter).padStart(2, "0")}`;
        linkCounter++;

        const link = new NetworkLink(linkId, sourceDevice, targetDevice);
        links.push(link);
        svgLayer.appendChild(link.group);

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

    function createHost(x = 0, y = 0) {
        const id = `HOST-${String(hostCounter).padStart(2, "0")}`;
        hostCounter++;

        const host = new NetworkDevice(id, "PC", "/static/assets/PC_off.png", x, y);
        devices.push(host);
        floor.appendChild(host.element);

        updateCounts();
        console.log(`[CHL] Created ${id}`);
        return host;
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
        /* item.addEventListener("mousedown", (event) => {
            if (event.button !== 0) return;

            event.preventDefault();
            const type = item.dataset.type;
            // At the moment only PC is implemented.
            if (type !== "PC") return;

            draggingFromPalette = true;
            paletteDeviceType = type;

            // Device follows cursor from its center.
            dragOffsetX = 32;
            dragOffsetY = 32;

            // Device is created when cursor reaches the floor.
            activeDevice = null;

            console.log(`[CHL] Started palette drag: ${type}`);
        }); */

        item.addEventListener("pointerdown", (event) => {
            if (event.button !== 0 && event.pointerType === "mouse") return;
            event.preventDefault();
            
            const type = item.dataset.type;
            if (type !== "PC") return;
            
            draggingFromPalette = true;
            paletteDeviceType = type;
            dragOffsetX = 32;
            dragOffsetY = 32;
            activeDevice = null;
        });
    });

    // =========================================
    // GLOBAL MOUSE MOVEMENT
    // =========================================

 /*    window.addEventListener("mousemove", (event) => {
        // ----------------------------------
        // PALETTE → FLOOR
        // ----------------------------------

        if (activeSegmentDrag) {
            const floorRect = floor.getBoundingClientRect();
            let mouseX = Math.round(event.clientX - floorRect.left);
            let mouseY = Math.round(event.clientY - floorRect.top);

            const deltaX = mouseX - activeSegmentDrag.initialMouseX;
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

            // Create device when cursor first enters floor.
            if (insideFloor && activeDevice === null) {
                if (paletteDeviceType === "PC") {
                    activeDevice = createHost();
                }
            }

            // Move device with cursor.
            if (activeDevice) {
                const position = getFloorPosition( event.clientX, event.clientY );
                activeDevice.updatePosition(position.x, position.y);
            }

            return;
        }

        // ----------------------------------
        // EXISTING DEVICE DRAG
        // ----------------------------------

        if (activeDevice) {
            const position = getFloorPosition( event.clientX, event.clientY );

            activeDevice.updatePosition(position.x, position.y);
        }
    }); */

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

            if (insideFloor && activeDevice === null) {
                if (paletteDeviceType === "PC") {
                    activeDevice = createHost();
                }
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

        activeDevice = null;
        activeSegmentDrag = null;
        draggingFromPalette = false;
        paletteDeviceType = null;
    }

    // REPLACE window.addEventListener("mouseup") WITH:
    window.addEventListener("pointerup", handlePointerRelease);
    window.addEventListener("pointercancel", handlePointerRelease);

    // 3. FLOOR DESELECTION
    // REPLACE floor.addEventListener("mousedown") WITH:
    floor.addEventListener("pointerdown", (event) => {
        if (event.target === floor || event.target === svgLayer) {
            deselectAll();
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
       INITIALIZATION: PROTOTYPE SCENE
       ========================================= */

    function initPrototypeScene() {
        const floorWidth = floor.clientWidth || 800;
        const floorHeight = floor.clientHeight || 500;

        // Position initial hosts with comfortable separation
        const host1X = Math.floor(floorWidth * 0.25) - 32;
        const host1Y = Math.floor(floorHeight * 0.4) - 32;

        const host2X = Math.floor(floorWidth * 0.70) - 32;
        const host2Y = Math.floor(floorHeight * 0.6) - 32;

        const host1 = createHost(host1X, host1Y);
        const host2 = createHost(host2X, host2Y);

        // Pre-connect prototype wire
        createConnection(host1, host2);
    }

    initPrototypeScene();
});
