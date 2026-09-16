with open("application/static/js/wel_app.js", "r") as f:
    content = f.read()

# We want to replace the whole fake generator logic.
# The generator starts at: const telemetryLogs = [
# And ends around line 127.
start_idx = content.find("const telemetryLogs = [")
if start_idx != -1:
    new_logic = """
    // ========================================================
    // LIVE EVENT TELEMETRY (WEL)
    // ========================================================
    
    let renderedEvents = new Set();
    
    window.addEventListener("simulation-events-updated", (e) => {
        const events = e.detail;
        const streamContainer = document.querySelector(".telemetry-stream");
        if (!streamContainer) return;
        
        const maxVisibleLines = 100;
        
        events.forEach(ev => {
            // Create a unique key for the event (so we don't re-render it every poll)
            const eventKey = ev.timestamp + ev.type + ev.source;
            if (renderedEvents.has(eventKey)) return;
            renderedEvents.add(eventKey);
            
            // Format time
            const d = new Date(ev.timestamp);
            const timeStr = d.toTimeString().split(' ')[0];
            
            // Format metadata
            let metaStr = "{}";
            if (ev.metadata && Object.keys(ev.metadata).length > 0) {
                metaStr = JSON.stringify(ev.metadata).replace(/"/g, "'");
            }
            
            const typeStr = (ev.type || "UNKNOWN").padEnd(30, ' ');
            const sourceStr = String(ev.source || "SYS").padEnd(15, ' ');
            const destStr = String(ev.destination || "SYS").padEnd(30, ' ');
            const protoStr = String(ev.protocol || "SYS").padEnd(10, ' ');
            
            const formattedLog = `[${timeStr}] ${typeStr} | ${sourceStr} -> ${destStr} (${protoStr}) ${metaStr}`;
            
            const line = document.createElement("div");
            line.className = "telemetry-line";
            
            if (ev.severity === "WARNING" || ev.severity === "ERROR" || formattedLog.includes("UNREACHABLE") || formattedLog.includes("DROP")) {
                line.innerHTML = `<span class="event-warn">${formattedLog}</span>`;
            } else if (ev.severity === "INFO" && (formattedLog.includes("ROUTE") || formattedLog.includes("ARP"))) {
                line.innerHTML = `<span class="event-cyan">${formattedLog}</span>`;
            } else {
                line.innerHTML = `<span class="event-info">${formattedLog}</span>`;
            }
            
            streamContainer.appendChild(line);
            
            if (streamContainer.children.length > maxVisibleLines) {
                streamContainer.removeChild(streamContainer.firstChild);
            }
            
            streamContainer.scrollTop = streamContainer.scrollHeight;
        });
    });
});
"""
    content = content[:start_idx] + new_logic
    
    with open("application/static/js/wel_app.js", "w") as f:
        f.write(content)
