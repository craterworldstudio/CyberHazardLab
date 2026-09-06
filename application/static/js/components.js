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
