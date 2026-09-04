document.addEventListener("DOMContentLoaded", () => {

    /* =========================================
       ELEMENTS
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


    console.log("[CHL] Net.Creator workspace initialized.");


    /* =========================================
       STATE
       ========================================= */

    const devices = [];

    let selectedDeviceId = null;
    let hostCounter = 1;

    let activeDevice = null;

    let draggingFromPalette = false;
    let paletteDeviceType = null;

    let dragOffsetX = 0;
    let dragOffsetY = 0;


    /* =========================================
       NETWORK DEVICE
       ========================================= */

    class NetworkDevice {

        constructor(id, type, iconPath, x, y) {

            this.id = id;
            this.type = type;

            this.position = {
                x: x,
                y: y
            };

            this.element = document.createElement("div");

            this.element.className = "device-node";

            this.element.dataset.id = this.id;

            this.img = document.createElement("img");

            this.img.className = "device-icon";

            this.img.src = iconPath;

            this.img.alt = `${type} Host`;

            this.img.draggable = false;

            this.element.appendChild(this.img);


            this.updatePosition(x, y);


            /* Device dragging */

            this.element.addEventListener(
                "mousedown",
                (event) => {

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

                    activeDevice = this;

                    draggingFromPalette = false;
                }
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

            this.element.classList.toggle(
                "selected",
                selected
            );
        }
    }


    /* =========================================
       SELECTION
       ========================================= */

    function selectDevice(id) {

        if (selectedDeviceId === id) {
            return;
        }


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
       NODE COUNT
       ========================================= */

    function updateNodeCount() {

        if (nodeCountEl) {
            nodeCountEl.textContent =
                devices.length;
        }
    }


    /* =========================================
       CREATE HOST
       ========================================= */

    function createHost() {

        const id =
            `HOST-${String(hostCounter).padStart(2, "0")}`;

        hostCounter++;


        const host =
            new NetworkDevice(
                id,
                "PC",
                "/static/assets/PC_off.png",
                0,
                0
            );


        devices.push(host);

        floor.appendChild(host.element);

        selectDevice(id);

        updateNodeCount();


        console.log(
            `[CHL] Created ${id}`
        );


        return host;
    }


    /* =========================================
       CALCULATE FLOOR POSITION
       ========================================= */

    function getFloorPosition(clientX, clientY) {

        const floorRect =
            floor.getBoundingClientRect();


        /*
         * Convert browser coordinates
         * into coordinates relative to
         * the topology floor.
         */

        let x =
            clientX -
            floorRect.left -
            dragOffsetX;


        let y =
            clientY -
            floorRect.top -
            dragOffsetY;


        /*
         * Keep device inside the floor.
         */

        const deviceWidth =
            activeDevice
                ? activeDevice.element.offsetWidth
                : 64;

        const deviceHeight =
            activeDevice
                ? activeDevice.element.offsetHeight
                : 64;


        const maxX =
            floor.clientWidth -
            deviceWidth;


        const maxY =
            floor.clientHeight -
            deviceHeight;


        x = Math.max(
            0,
            Math.min(x, maxX)
        );


        y = Math.max(
            0,
            Math.min(y, maxY)
        );


        return {
            x,
            y
        };
    }


    /* =========================================
       PALETTE DRAG START
       ========================================= */

    paletteItems.forEach(item => {

        item.addEventListener(
            "mousedown",
            (event) => {

                if (event.button !== 0) {
                    return;
                }


                event.preventDefault();


                const type =
                    item.dataset.type;


                /*
                 * At the moment only PC
                 * is implemented.
                 */

                if (type !== "PC") {
                    return;
                }


                draggingFromPalette = true;

                paletteDeviceType = type;


                /*
                 * The device follows the
                 * cursor from its center.
                 */

                dragOffsetX = 32;
                dragOffsetY = 32;


                /*
                 * We do NOT create the device
                 * yet.
                 *
                 * It will be created once the
                 * cursor reaches the floor.
                 */

                activeDevice = null;


                console.log(
                    `[CHL] Started palette drag: ${type}`
                );
            }
        );
    });


    /* =========================================
       GLOBAL MOUSE MOVEMENT
       ========================================= */

    window.addEventListener(
        "mousemove",
        (event) => {

            /*
             * ----------------------------------
             * PALETTE → FLOOR
             * ----------------------------------
             */

            if (draggingFromPalette) {

                const floorRect =
                    floor.getBoundingClientRect();


                const insideFloor =
                    event.clientX >= floorRect.left &&
                    event.clientX <= floorRect.right &&
                    event.clientY >= floorRect.top &&
                    event.clientY <= floorRect.bottom;


                /*
                 * Create the device when the
                 * cursor first enters the floor.
                 */

                if (
                    insideFloor &&
                    activeDevice === null
                ) {

                    if (paletteDeviceType === "PC") {

                        activeDevice =
                            createHost();
                    }
                }


                /*
                 * If the device now exists,
                 * move it with the cursor.
                 */

                if (activeDevice) {

                    const position =
                        getFloorPosition(
                            event.clientX,
                            event.clientY
                        );


                    activeDevice.updatePosition(
                        position.x,
                        position.y
                    );
                }


                return;
            }


            /*
             * ----------------------------------
             * EXISTING DEVICE DRAG
             * ----------------------------------
             */

            if (activeDevice) {

                const position =
                    getFloorPosition(
                        event.clientX,
                        event.clientY
                    );


                activeDevice.updatePosition(
                    position.x,
                    position.y
                );
            }
        }
    );


    /* =========================================
       GLOBAL MOUSE RELEASE
       ========================================= */

    window.addEventListener(
        "mouseup",
        () => {

            if (draggingFromPalette) {

                if (activeDevice) {

                    console.log(
                        `[CHL] Placed ${activeDevice.id}`
                    );

                } else {

                    console.log(
                        "[CHL] Palette drag cancelled."
                    );
                }
            }


            activeDevice = null;

            draggingFromPalette = false;

            paletteDeviceType = null;
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