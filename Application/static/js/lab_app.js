document.addEventListener("DOMContentLoaded", () => {
    // Basic floor mount verification
    const floor = document.getElementById("topologyFloor");
    
    if (floor) {
        console.log("[CHL] Net.Creator workspace floor initialized.");
    }
});

document.addEventListener("DOMContentLoaded", () => {
    const floor = document.getElementById("topologyFloor");
    const paletteItems = document.querySelectorAll(".palette-item:not(.disabled)");
    const nodeCountEl = document.getElementById("nodeCount");

    if (!floor) return;

    const devices = [];
    let selectedDeviceId = null;
    let hostCounter = 1;

    // Drag Tracking State
    let activeDragDevice = null;
    let isPaletteDrag = false;
    let pendingDeviceType = null;
    let dragOffsetX = 32;
    let dragOffsetY = 32;

    // --- DEVICE CLASS ---
    class NetworkDevice {
        constructor(id, type, iconPath, x, y) {
            this.id = id;
            this.type = type;
            this.state = 'OFF';
            this.position = { x, y };

            this.element = document.createElement("div");
            this.element.className = "device-node";
            this.element.dataset.id = this.id;
            this.element.style.left = `${this.position.x}px`;
            this.element.style.top = `${this.position.y}px`;

            this.img = document.createElement("img");
            this.img.src = iconPath;
            this.img.alt = `${type} Host`;
            this.img.className = "device-icon";
            this.img.draggable = false;
            this.element.appendChild(this.img);

            this.element.addEventListener("mousedown", (e) => this.onMouseDown(e));
        }

        updatePosition(x, y) {
            this.position.x = x;
            this.position.y = y;
            this.element.style.left = `${x}px`;
            this.element.style.top = `${y}px`;
        }

        setSelected(isSelected) {
            if (isSelected) {
                this.element.classList.add("selected");
            } else {
                this.element.classList.remove("selected");
            }
        }

        onMouseDown(e) {
            if (e.button !== 0) return;

            e.preventDefault();
            e.stopPropagation();

            selectDevice(this.id);

            const rect = this.element.getBoundingClientRect();
            dragOffsetX = e.clientX - rect.left;
            dragOffsetY = e.clientY - rect.top;

            activeDragDevice = this;
            isPaletteDrag = false;
        }
    }

    // --- SELECTION MANAGEMENT ---
    function selectDevice(id) {
        if (selectedDeviceId === id) return;

        if (selectedDeviceId) {
            const prev = devices.find(d => d.id === selectedDeviceId);
            if (prev) prev.setSelected(false);
        }

        selectedDeviceId = id;
        const current = devices.find(d => d.id === selectedDeviceId);
        if (current) current.setSelected(true);
    }

    function deselectAll() {
        if (selectedDeviceId) {
            const current = devices.find(d => d.id === selectedDeviceId);
            if (current) current.setSelected(false);
            selectedDeviceId = null;
        }
    }

    function updateNodeCount() {
        if (nodeCountEl) {
            nodeCountEl.textContent = devices.length;
        }
    }

    // --- SPAWN FACTORY ---
    function spawnHostAt(x, y) {
        const padId = String(hostCounter).padStart(2, '0');
        const hostId = `HOST-${padId}`;
        hostCounter++;

        const iconPath = "/assets/PC_off.png"; 

        const host = new NetworkDevice(hostId, "PC", iconPath, x, y);

        devices.push(host);
        floor.appendChild(host.element);
        selectDevice(hostId);
        updateNodeCount();

        return host;
    }

    // --- SIDEBAR PALETTE MOUSE DRAG INITIATION ---
    paletteItems.forEach(item => {
        item.addEventListener("mousedown", (e) => {
            if (e.button !== 0) return;

            e.preventDefault();
            
            const deviceType = item.dataset.type;
            const floorRect = floor.getBoundingClientRect();

            // Calculate drop coordinate relative to floor
            let startX = e.clientX - floorRect.left - 32;
            let startY = e.clientY - floorRect.top - 32;

            const maxX = floorRect.width - 64;
            const maxY = floorRect.height - 64;

            startX = Math.max(0, Math.min(startX, maxX));
            startY = Math.max(0, Math.min(startY, maxY));

            // Instantly spawn device and attach to active drag movement
            const newDevice = spawnHostAt(startX, startY);
            
            activeDragDevice = newDevice;
            isPaletteDrag = true;
            dragOffsetX = 32;
            dragOffsetY = 32;
        });
    });

    // --- GLOBAL DRAG AND DROP MOVEMENT HANDLER ---
    window.addEventListener("mousemove", (e) => {
        if (!activeDragDevice) return;

        const floorRect = floor.getBoundingClientRect();

        let newX = (e.clientX - floorRect.left) - dragOffsetX;
        let newY = (e.clientY - floorRect.top) - dragOffsetY;

        const maxX = floorRect.width - 64;
        const maxY = floorRect.height - 64;

        newX = Math.max(0, Math.min(newX, maxX));
        newY = Math.max(0, Math.min(newY, maxY));

        activeDragDevice.updatePosition(newX, newY);
    });

    window.addEventListener("mouseup", () => {
        activeDragDevice = null;
        isPaletteDrag = false;
    });

    floor.addEventListener("mousedown", (e) => {
        if (e.target === floor) {
            deselectAll();
        }
    });

    updateNodeCount();
});