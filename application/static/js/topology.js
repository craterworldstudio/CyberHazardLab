async function loadDevices() {

        const backendDevices = await apiRequest(
            "GET",
            "/api/ntm/devices"
        );

        let layout = {};
        try {
            layout = await apiRequest("GET", "/api/ntm/layout");
        } catch (e) {
            console.warn("[CHL] Could not load layout", e);
        }

        for (const backendDevice of backendDevices) {
            const type = backendDevice.type.toUpperCase();
            const config = CHL.DEVICE_CONFIG[type] || CHL.DEVICE_CONFIG.PC;
            
            const pos = layout[backendDevice.name] || {x: 0, y: 0};
            const device = new CHL.NetworkDevice( backendDevice.name, type, backendDevice.status, pos.x, pos.y );

            CHL.devices.push(device);
            CHL.floor.appendChild(device.element);
        }


        console.log(
            `[CHL] Loaded ${backendDevices.length} devices from backend`
        );
}

async function loadLinks() {

    const backendLinks = await apiRequest(
        "GET",
        "/api/ntm/links"
    );

    for (const backendLink of backendLinks) {

        const sourceDevice = CHL.devices.find(
            device => device.id === backendLink.endpoint_a
        );

        const targetDevice = CHL.devices.find(
            device => device.id === backendLink.endpoint_b
        );

        if (!sourceDevice || !targetDevice) {
            console.warn(
                `[CHL] Could not reconstruct link: ` +
                `${backendLink.endpoint_a} <-> ${backendLink.endpoint_b}`
            );
            continue;
        }

        const linkId =
            `LINK-${String(CHL.links.length + 1).padStart(2, "0")}`;

        const link = new CHL.NetworkLink( linkId, sourceDevice, targetDevice
        );

        CHL.links.push(link);
        CHL.svgLayer.appendChild(link.group);
    }

    console.log(
        `[CHL] Loaded ${backendLinks.length} links from backend`
    );
}

async function connectDevices(deviceA, deviceB) {

    const result = await apiRequest(
        "POST",
        "/api/ntm/connect",
        {
            device_a: deviceA.id,
            device_b: deviceB.id
        }
    );

    console.log(
        `[CHL] Backend connected ${deviceA.id} <-> ${deviceB.id}`
    );

    return result;
}


function getNormalizedPosition(device) {

    return {
        x: device.position.x / CHL.floor.clientWidth,
        y: device.position.y / CHL.floor.clientHeight
    };
}

function getPixelPosition(normalizedPosition) {

    return {
        x: normalizedPosition.x * CHL.floor.clientWidth,
        y: normalizedPosition.y * CHL.floor.clientHeight
    };
}

window._deviceCounters = window._deviceCounters || {};

function getNextDeviceNumber(prefix, devices) {
    if (window._deviceCounters[prefix] === undefined) {
        let max = -1;
        devices.forEach(device => {
            if (!device.id.startsWith(prefix)) return;
            const number = Number(device.id.slice(prefix.length));
            if (!Number.isNaN(number)) max = Math.max(max, number);
        });
        window._deviceCounters[prefix] = max;
    }
    window._deviceCounters[prefix] += 1;
    return window._deviceCounters[prefix];
}




