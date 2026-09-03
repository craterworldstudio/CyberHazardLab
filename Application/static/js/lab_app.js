
document.addEventListener("DOMContentLoaded", () => {

    /* =========================================
       ELEMENT REFERENCES
       ========================================= */

    const floor = document.getElementById("topologyFloor");

    const paletteItems = document.querySelectorAll(
        ".palette-item:not(.disabled)"
    );

    const nodeCountEl = document.getElementById("nodeCount");


    if (!floor) {
        console.error("[CHL] Topology floor not found.");
        return;
    }


    console.log(
        "[CHL] Net.Creator workspace initialized."
    );


    /* =========================================
       STATE
       ========================================= */

    const devices = [];

    let selectedDeviceId = null;

    let hostCounter = 1;

    let activeDragDevice = null;

    let dragOffsetX = 0;
    let dragOffsetY = 0;


    /* =========================================
       NETWORK DEVICE CLASS
       ========================================= */

    class NetworkDevice {

        constructor(id, type, iconPath, x, y) {

            this.id = id;

            this.type = type;

            this.state = "OFF";

            this.position = {
                x: x,
                y: y
            };


            /* -------------------------------
               Root element
               ------------------------------- */

            this.element =
                document.createElement("div");

            this.element.className =
                "device-node";

            this.element.dataset.id =
                this.id;

            this.element.style.left =
                `${x}px`;

            this.element.style.top =
                `${y}px`;


            /* -------------------------------
               Device image
               ------------------------------- */

            this.img =
                document.createElement("img");

            this.img.src =
                iconPath;

            this.img.alt =
                `${type} Host`;

            this.img.className =
                "device-icon";

            this.img.draggable = false;


            this.element.appendChild(
                this.img
            );


            /* -------------------------------
               Mouse interaction
               ------------------------------- */

            this.element.addEventListener(
                "mousedown",
                (event) => this.onMouseDown(event)
            );
        }


        /* =====================================
           POSITION
           ===================================== */

        updatePosition(x, y) {

            this.position.x = x;
            this.position.y = y;

            this.element.style.left =
                `${x}px`;

            this.element.style.top =
                `${y}px`;
        }


        /* =====================================
           SELECTION
           ===================================== */

        setSelected(selected) {

            if (selected) {

                this.element.classList.add(
                    "selected"
                );

            } else {

                this.element.classList.remove(
                    "selected"
                );
            }
        }


        /* =====================================
           DEVICE MOUSE DOWN
           ===================================== */

        onMouseDown(event) {

            if (event.button !== 0) {
                return;
            }


            event.preventDefault();

            event.stopPropagation();


            selectDevice(this.id);


            const rect =
                this.element.getBoundingClientRect();


            dragOffsetX =
                event.clientX - rect.left;

            dragOffsetY =
                event.clientY - rect.top;


            activeDragDevice = this;
        }
    }


    /* =========================================
       DEVICE SELECTION
       ========================================= */

    function selectDevice(id) {

        if (selectedDeviceId === id) {
            return;
        }


        /* Deselect previous device */

        if (selectedDeviceId !== null) {

            const previous =
                devices.find(
                    device =>
                        device.id === selectedDeviceId
                );

            if (previous) {
                previous.setSelected(false);
            }
        }


        /* Select new device */

        selectedDeviceId = id;


        const current =
            devices.find(
                device =>
                    device.id === selectedDeviceId
            );


        if (current) {
            current.setSelected(true);
        }
    }


    /* =========================================
       DESELECT EVERYTHING
       ========================================= */

    function deselectAll() {

        if (selectedDeviceId === null) {
            return;
        }


        const current =
            devices.find(
                device =>
                    device.id === selectedDeviceId
            );


        if (current) {
            current.setSelected(false);
        }


        selectedDeviceId = null;
    }


    /* =========================================
       NODE COUNTER
       ========================================= */

    function updateNodeCount() {

        if (!nodeCountEl) {
            return;
        }


        nodeCountEl.textContent =
            devices.length;
    }


    /* =========================================
       HOST SPAWN
       ========================================= */

    function spawnHostAt(x, y) {

        const paddedId =
            String(hostCounter)
                .padStart(2, "0");


        const hostId =
            `HOST-${paddedId}`;


        hostCounter++;


        const iconPath =
            "/static/assets/PC_off.png";


        const host =
            new NetworkDevice(
                hostId,
                "PC",
                iconPath,
                x,
                y
            );


        devices.push(host);


        floor.appendChild(
            host.element
        );


        selectDevice(hostId);


        updateNodeCount();


        console.log(
            `[CHL] Created ${hostId}`
        );


        return host;
    }


    /* =========================================
       PALETTE DRAG
       ========================================= */

    paletteItems.forEach(item => {

        item.addEventListener(
            "mousedown",
            (event) => {

                if (event.button !== 0) {
                    return;
                }


                event.preventDefault();


                const deviceType =
                    item.dataset.type;


                if (deviceType !== "PC") {
                    return;
                }


                const floorRect =
                    floor.getBoundingClientRect();


                /*
                    Spawn the device centered
                    under the cursor.
                */

                let x =
                    event.clientX -
                    floorRect.left -
                    32;


                let y =
                    event.clientY -
                    floorRect.top -
                    32;


                /*
                    Keep the device inside
                    the topology floor.
                */

                const maxX =
                    floorRect.width - 64;

                const maxY =
                    floorRect.height - 64;


                x =
                    Math.max(
                        0,
                        Math.min(x, maxX)
                    );


                y =
                    Math.max(
                        0,
                        Math.min(y, maxY)
                    );


                const device =
                    spawnHostAt(x, y);


                /*
                    Continue dragging the
                    newly created device.
                */

                activeDragDevice =
                    device;


                dragOffsetX = 32;
                dragOffsetY = 32;
            }
        );
    });


    /* =========================================
       DEVICE MOVEMENT
       ========================================= */

    window.addEventListener(
        "mousemove",
        (event) => {

            if (!activeDragDevice) {
                return;
            }


            const floorRect =
                floor.getBoundingClientRect();


            let x =
                event.clientX -
                floorRect.left -
                dragOffsetX;


            let y =
                event.clientY -
                floorRect.top -
                dragOffsetY;


            const maxX =
                floorRect.width - 64;

            const maxY =
                floorRect.height - 64;


            x =
                Math.max(
                    0,
                    Math.min(x, maxX)
                );


            y =
                Math.max(
                    0,
                    Math.min(y, maxY)
                );


            activeDragDevice.updatePosition(
                x,
                y
            );
        }
    );


    /* =========================================
       RELEASE DEVICE
       ========================================= */

    window.addEventListener(
        "mouseup",
        () => {

            if (activeDragDevice) {

                console.log(
                    `[CHL] Released ${activeDragDevice.id}`
                );
            }


            activeDragDevice = null;
        }
    );


    /* =========================================
       FLOOR CLICK
       ========================================= */

    floor.addEventListener(
        "mousedown",
        (event) => {

            if (event.target === floor) {
                deselectAll();
            }
        }
    );


    /* =========================================
       INITIAL STATE
       ========================================= */

    updateNodeCount();

});