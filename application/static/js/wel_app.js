document.addEventListener("DOMContentLoaded", () => {
    const buttons = document.querySelectorAll(".enter-button");

    buttons.forEach((button) => {
        button.addEventListener("click", () => {
            const isAlreadySelected = button.classList.contains("selected");

            if (isAlreadySelected) {
                // Second click: Execute redirection
                const destination = button.getAttribute("data-url");
                if (destination) {
                    window.location.href = destination;
                }
            } else {
                // First click: Unhighlight previous button and highlight current button
                buttons.forEach((btn) => btn.classList.remove("selected"));
                button.classList.add("selected");
            }
        });
    });
});


const telemetryLogs = [
    // --- ICMP & TRAFFIC TRACES ---
    "[16:47:02] ICMP_TIME_EXCEEDED_RECEIVED    | 10.0.1.1 -> 10.0.2.100                        (ICMP)       {}",
    "[16:47:02] PACKET_FORWARDED               | 10.0.2.100 -> 10.0.0.100                      (ICMP)       {'router': 'RUT-02', 'in_interface': 'eth1', 'out_interface': 'eth0'}",
    "[16:47:02] PACKET_FORWARDED               | 10.0.2.100 -> 10.0.0.100                      (ICMP)       {'router': 'RUT-01', 'in_interface': 'eth1', 'out_interface': 'eth0'}",
    "[16:47:02] ICMP_ECHO_REQUEST_RECEIVED     | 10.0.2.100 -> 10.0.0.100                      (ICMP)       {}",
    "[16:47:02] ICMP_ECHO_REPLY_SENT           | 10.0.0.100 -> 10.0.2.100                      (ICMP)       {}",
    
    // --- ROUTING TABLE DUMPS ---
    "[00:00:01] ROUTE_TABLE_DUMP               | RUT-01                                        (SYS)        [0.0.0.0/0 via 10.0.1.1 dev eth0]",
    "[00:00:01] ROUTE_TABLE_DUMP               | RUT-01                                        (SYS)        [10.0.0.0/24 dev eth1 proto kernel scope link]",
    "[00:00:01] ROUTE_TABLE_DUMP               | RUT-02                                        (SYS)        [10.0.2.0/24 dev eth0 proto kernel scope link]",
    "[00:00:01] ROUTE_TABLE_DUMP               | RUT-02                                        (SYS)        [172.16.0.0/16 via 10.0.2.1 dev eth1]",

    // --- SERVICE & SYSTEM INITIALIZATION ---
    "[15:03:45] DHCP_LEASE                     | DHCP -> 10.0.0.100                            (DHCP)       {'ip': '10.0.0.100', 'intf_name': 'eth0', 'gateway': '10.0.0.1'}",
    "[15:03:45] SERVICE_CREATED                | SYSTEM -> 10.0.0.100                          (UDP)        {'host': 'WEB-01', 'service': 'DNS', 'status': 'created'}",
    "[15:03:45] SERVICE_STARTED                | SYSTEM -> 10.0.0.100                          (UDP)        {'host': 'WEB-01', 'service': 'DNS'}",
    "[21:31:07] SERVICE_CREATED                | SYSTEM -> 10.0.0.100                          (TCP)        {'host': 'WEB-01', 'service': 'HTTP', 'status': 'created'}",
    "[21:31:07] SERVICE_STARTED                | SYSTEM -> 10.0.0.100                          (TCP)        {'host': 'WEB-01', 'service': 'HTTP'}",

    // --- ARP TABLE DUMPS & RESOLUTION ---
    "[15:03:45] ARP_CACHE_FLUSH                | SW-01                                         (ARP)        {'table': 'cam_table_0', 'cleared': 14}",
    "[15:03:45] ARP_REQUEST                    | 10.0.2.100 -> 10.0.2.1                        (ARP)        {'mac': '02:da:bf:38:b6:50'}",
    "[15:03:45] ARP_REPLY                      | 10.0.2.1 -> 10.0.2.100                        (ARP)        {'mac': '02:88:a3:c6:3f:62'}",
    "[15:03:45] ARP_TABLE_DUMP                 | 10.0.2.100                                    (ARP)        [10.0.2.1 -> 02:88:a3:c6:3f:62 REACHABLE]",
    "[15:03:45] ARP_TABLE_DUMP                 | 10.0.2.100                                    (ARP)        [10.0.2.50 -> 02:11:44:88:aa:bb STALE]",

    // --- SWITCH FRAME HANDLING ---
    "[15:03:45] FRAME_RECEIVED                 | 02:da:bf:38:b6:50 -> FF:FF:FF:FF:FF:FF        (ETHERNET)   {'switch': 'SW-02'}",
    "[15:03:45] FRAME_BROADCAST                | 02:da:bf:38:b6:50 -> FF:FF:FF:FF:FF:FF        (ETHERNET)   {'switch': 'SW-02', 'in_port': 1, 'out_ports': [2]}",
    "[15:03:45] FRAME_FORWARDED                | 02:88:a3:c6:3f:62 -> 02:da:bf:38:b6:50        (ETHERNET)   {'switch': 'SW-02', 'in_port': 2, 'out_port': 1}",

    // --- ANOMALY & SECURITY EVENTS ---
    "[15:03:45] UDP_PORT_UNREACHABLE           | 10.0.2.100 -> 10.0.0.100                      (UDP)        {'source_port': 49153, 'destination_port': 9999, 'reason': 'PORT_CLOSED'}",
    "[03:12:09] TCP_SYN_FLOOD_DETECTED         | 192.168.1.50 -> 10.0.0.100                    (TCP/80)     {'rate': '4500 pps', 'action': 'RATE_LIMIT'}",
    "[03:12:10] FIREWALL_DROP                  | 192.168.1.50 -> 10.0.0.100                    (TCP/445)    {'rule_id': 1042, 'chain': 'INPUT'}",
    "[03:12:11] PORT_SWEEP_ALERT               | 10.0.2.199 -> 10.0.2.0/24                     (SCAN)       {'ports_scanned': [21, 22, 23, 80, 443, 3389]}",
    "[03:12:12] MAC_SPOOFING_SUSPECTED         | 02:da:bf:38:b6:50                             (ETHERNET)   {'switch': 'SW-01', 'port': 3, 'conflict': '02:da:bf:38:b6:50'}",

    // --- INTERFACE & HARDWARE STATES ---
    "[08:15:00] INTF_STATE_CHANGE              | RUT-01                                        (SYS)        {'interface': 'eth1', 'status': 'UP', 'speed': '1000Mbps'}",
    "[08:15:01] INTF_STATE_CHANGE              | RUT-02                                        (SYS)        {'interface': 'eth0', 'status': 'LINK_FLAP', 'duration': '200ms'}"
];

document.addEventListener("DOMContentLoaded", () => {
    const streamContainer = document.getElementById("telemetryStream");
    const maxVisibleLines = 45;

    // Helper: Generate current real-time HH:MM:SS timestamp
    function getFormattedTime() {
        const now = new Date();
        return now.toTimeString().split(' ')[0];
    }

    // Helper: Pick a random element from an array
    function getRandomItem(arr) {
        return arr[Math.floor(Math.random() * arr.length)];
    }

    // Helper: Generate random IP address
    function getRandomIP() {
        return `10.0.${Math.floor(Math.random() * 3)}.${Math.floor(Math.random() * 200 + 1)}`;
    }

    function addTelemetryLine() {
        if (!streamContainer) return;

        // 1. Pick a base template randomly
        const baseLog = getRandomItem(telemetryLogs);

        // 2. Inject real-time timestamp and randomized IPs/Ports on the fly
        const timestamp = getFormattedTime();
        let formattedLog = baseLog.replace(/\[\d{2}:\d{2}:\d{2}\]/, `[${timestamp}]`);

        const line = document.createElement("div");
        line.className = "telemetry-line";

        // 3. Apply color highlights based on event type
        if (formattedLog.includes("UNREACHABLE") || formattedLog.includes("FLOOD") || formattedLog.includes("ALERT") || formattedLog.includes("DROP")) {
            line.innerHTML = `<span class="event-warn">${formattedLog}</span>`;
        } else if (formattedLog.includes("ROUTE_TABLE_DUMP") || formattedLog.includes("ARP_TABLE_DUMP")) {
            line.innerHTML = `<span class="event-cyan">${formattedLog}</span>`;
        } else if (formattedLog.includes("SERVICE_") || formattedLog.includes("DHCP_") || formattedLog.includes("INTF_STATE")) {
            line.innerHTML = `<span class="event-info">${formattedLog}</span>`;
        } else {
            line.innerHTML = `<span class="event-muted">${formattedLog}</span>`;
        }

        streamContainer.appendChild(line);

        // Maintain performance limit
        if (streamContainer.children.length > maxVisibleLines) {
            streamContainer.removeChild(streamContainer.firstChild);
        }

        // 4. Trigger next event at a RANDOM time interval (between 30ms and 210ms)
        const randomDelay = Math.floor(Math.random() * 180) + 30;
        setTimeout(addTelemetryLine, randomDelay);
    }

    // Start the recursive random ticker
    addTelemetryLine();
});