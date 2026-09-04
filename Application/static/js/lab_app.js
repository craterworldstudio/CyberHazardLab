
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
    let linkCounter = 1;

    let activeDevice = null;
    let activeSegmentDrag = null; // { link, segmentIndex, orientation, initialMouseX, initialMouseY, initialOffset }

    // Current Active Tool: "SELECT" | "PLIERS" | "CONNECT" | "INSPECT"
    let currentTool = "SELECT";
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
    
        if (currentTool !== "CONNECT" && connectionSourceDevice) {
            connectionSourceDevice.setPendingConnect(false);
            connectionSourceDevice = null;
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
        
            handleDeviceClick(this, event);
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

            this.group.appendChild(this.path);
            this.group.appendChild(this.segmentsGroup);

            this.updatePath();
        }

        // Calculate orthogonal sequence of points: start -> corner1 -> corner2 -> end
        getPoints() {
            const start = this.source.getCenter();
            const end = this.target.getCenter();

            // Default middle split point
            let midX = Math.round((start.x + end.x) / 2);

            if (this.middleSegmentOffset !== null) {
                midX = this.middleSegmentOffset;
            }

            return [
                start,
                { x: midX, y: start.y },
                { x: midX, y: end.y },
                end
            ];
        }

        updatePath() {
            const points = this.getPoints();

            let d = `M ${points[0].x} ${points[0].y}`;
            for (let i = 1; i < points.length; i++) {
                d += ` L ${points[i].x} ${points[i].y}`;
            }
            this.path.setAttribute("d", d);

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

                    handleWireSegmentClick(this, i, orientation, e);
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

    function handleWireSegmentClick(link, segmentIndex, orientation, event) {

        if (currentTool === "PLIERS") {
            deselectAll();
            deleteLink(link.id);
            return;
        }


        deselectAll();
        selectLink(link.id);

        if (currentTool === "SELECT") {
            deselectAll();
            selectLink(link.id);

            const floorRect = floor.getBoundingClientRect();
            const points = link.getPoints();

            activeSegmentDrag = {
                link: link,
                segmentIndex: segmentIndex,
                orientation: orientation,
                initialMouseX: event.clientX - floorRect.left,
                initialMouseY: event.clientY - floorRect.top,
                initialOffset: link.middleSegmentOffset !== null ? link.middleSegmentOffset : points[1].x
            };
        }
    }

    function handleConnectClick(device) {
        if (!connectionSourceDevice) {
            connectionSourceDevice = device;
            connectionSourceDevice.setPendingConnect(true);
            console.log(`[CHL] CONNECT Tool: Source selected (${device.id})`);
        } else {
            if (connectionSourceDevice.id === device.id) {
                console.warn("[CHL] CONNECT Tool: Cannot connect device to itself.");
                return;
            }

            createConnection(connectionSourceDevice, device);

            connectionSourceDevice.setPendingConnect(false);
            connectionSourceDevice = null;
            //setTool("SELECT");
        }
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
            (l.source.id === sourceDevice.id && l.target.id === targetDevice.id) ||
            (l.source.id === targetDevice.id && l.target.id === sourceDevice.id)
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
