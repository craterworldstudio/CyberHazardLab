import time
import uuid
import re
try:
    import yaml
except ImportError:
    yaml = None
from typing import Dict, Any, List, Optional


DEFAULT_YAML_RULES = [
    """id: rule-reverse-shell
title: Netcat Reverse Shell Execution
description: Detects interactive shell execution spawned via netcat or ncat
severity: CRITICAL
status: production
detection:
  selection_cmd:
    type: COMMAND_EXECUTED
    command|contains:
      - "nc "
      - "netcat"
      - "ncat"
    command|contains_all:
      - "-e"
  selection_netcat_sh:
    command|contains:
      - "nc -e"
      - "netcat -e"
      - "/bin/bash"
      - "/bin/sh"
  condition: selection_cmd or selection_netcat_sh
""",
    """id: rule-arp-spoof
title: ARP Poisoning / Spoofing Activity
description: Detects execution of ARP spoofing tools or IP-MAC cache conflicts
severity: CRITICAL
status: production
detection:
  selection_tool:
    type: COMMAND_EXECUTED
    command|contains:
      - "arpspoof"
      - "ettercap"
      - "bettercap"
  selection_cache_conflict:
    type: ARP_REPLY
    metadata.conflict: true
  condition: selection_tool or selection_cache_conflict
""",
    """id: rule-port-scan
title: Network Port Scanning
description: Detects network port scanning tools (nmap) or rapid multi-port probes
severity: HIGH
status: production
detection:
  selection_tool:
    type: COMMAND_EXECUTED
    command|contains:
      - "nmap"
  selection_probes:
    protocol:
      - TCP
      - SYN
  filter_dns:
    metadata.payload|contains: "dns_health"
  aggregation:
    field: dest_port
    distinct: true
    operator: ">="
    threshold: 4
    timeframe: 15s
    by: source
  condition: selection_tool or (selection_probes and not filter_dns)
""",
    """id: rule-icmp-sweep
title: ICMP Reconnaissance Sweep
description: Detects ICMP ping sweep targeting 4 or more distinct destinations within 15 seconds
severity: MEDIUM
status: production
detection:
  selection_icmp:
    protocol: ICMP
  filter_dns_health:
    metadata.payload|contains: "dns_health"
  aggregation:
    field: destination
    distinct: true
    operator: ">="
    threshold: 4
    timeframe: 15s
    by: source
  condition: selection_icmp and not filter_dns_health
""",
    """id: rule-ssh-brute-force
title: SSH Brute Force Attack
description: 3 or more SSH authentication failures from the same source within 60 seconds
severity: CRITICAL
status: production
detection:
  selection:
    type: SSH_AUTH_FAILED
  aggregation:
    operator: ">="
    threshold: 3
    timeframe: 60s
    by: source
  condition: selection
""",
    """id: rule-root-login
title: Direct Root Login / Privilege Escalation
description: Direct root user interactive session or superuser privilege escalation detected
severity: CRITICAL
status: production
detection:
  selection_su:
    type: COMMAND_EXECUTED
    command|contains:
      - "sudo su"
      - "sudo -i"
      - "su -"
      - "su root"
  selection_ssh_root:
    type: SSH_AUTH_SUCCESS
    metadata.user: root
  selection_root_event:
    type: ROOT_LOGIN
  condition: selection_su or selection_ssh_root or selection_root_event
""",
    """id: rule-ssh-success
title: SSH Interactive Login
description: Successful remote SSH authentication and interactive session opened
severity: LOW
status: production
detection:
  selection:
    type: SSH_AUTH_SUCCESS
  condition: selection
"""
]


class SOCDetectionEngine:
    """
    SOC Detection Engine.
    Receives ingested log events from the SIEM Collector,
    evaluates Sigma-inspired YAML detection rules, tracks sliding-window history,
    and raises high-fidelity alerts in the SOC Lab.
    """

    def __init__(self, simulation=None):
        self.simulation = simulation
        self._history = []  # List of (timestamp, event_data)
        self._alert_cooldowns = {}
        self.max_alerts = 250
        self.rules: List[Dict[str, Any]] = []
        self._init_rules()

    def _init_rules(self):
        """Loads or initializes default YAML detection rules in simulation soc_state."""
        sim = self.simulation
        if not sim:
            for raw_yaml in DEFAULT_YAML_RULES:
                r = self.parse_yaml_rule(raw_yaml)
                if r:
                    self.rules.append(r)
            return

        if not hasattr(sim, "soc_state") or not isinstance(sim.soc_state, dict):
            sim.soc_state = {}

        sim.soc_state.setdefault("alerts", [])
        sim.soc_state.setdefault("incidents", [])
        sim.soc_state.setdefault("ingested_events", [])
        sim.soc_state.setdefault("total_events_count", len(sim.soc_state["ingested_events"]))

        existing_rules = sim.soc_state.get("rules", [])
        parsed_rules = []

        if not existing_rules:
            for raw_yaml in DEFAULT_YAML_RULES:
                r = self.parse_yaml_rule(raw_yaml)
                if r:
                    parsed_rules.append(r)
            sim.soc_state["rules"] = parsed_rules
        else:
            for item in existing_rules:
                if isinstance(item, dict) and "yaml" in item:
                    r = self.parse_yaml_rule(item["yaml"], existing_id=item.get("id"))
                    if r:
                        parsed_rules.append(r)
                elif isinstance(item, dict):
                    # Convert legacy dict rule to YAML rule
                    r = self._legacy_to_yaml_rule(item)
                    parsed_rules.append(r)

            # Ensure default attack rules exist
            existing_ids = {r.get("id") for r in parsed_rules}
            for raw_yaml in DEFAULT_YAML_RULES:
                r = self.parse_yaml_rule(raw_yaml)
                if r and r.get("id") not in existing_ids:
                    parsed_rules.append(r)

            sim.soc_state["rules"] = parsed_rules

        self.rules = sim.soc_state["rules"]

    def _legacy_to_yaml_rule(self, leg: dict) -> dict:
        r_id = leg.get("id") or f"rule-{uuid.uuid4().hex[:8]}"
        name = leg.get("name") or leg.get("title") or "Custom Detection Rule"
        sev = leg.get("severity", "HIGH").upper()
        desc = leg.get("description", "")
        cond = leg.get("condition", "")

        # Check if condition has aggregation
        agg_yaml = ""
        sel_cond = "selection"
        if "|" in cond:
            parts = cond.split("|", 1)
            agg_expr = parts[1].strip()
            # Try parsing aggregation
            m = re.match(r"(count\([^\)]*\))\s*([><!=]+)\s*(\d+)\s+within\s+(\d+)s(?:\s+by\s+([a-zA-Z0-9_]+))?", agg_expr, re.IGNORECASE)
            if m:
                fn_call, op, threshold_str, window_sec_str, group_by_field = m.groups()
                distinct_flag = "distinct" in fn_call.lower()
                m_field = re.search(r"distinct\s+([a-zA-Z0-9_]+)", fn_call)
                f_name = m_field.group(1) if m_field else "destination"
                agg_yaml = f"""  aggregation:
    operator: "{op}"
    threshold: {threshold_str}
    timeframe: {window_sec_str}s
    by: "{group_by_field or 'source'}"
    distinct: {str(distinct_flag).lower()}
    field: "{f_name}"
"""

        raw_yaml = f"""id: {r_id}
title: "{name}"
description: "{desc}"
severity: {sev}
status: production
detection:
  selection:
    type|contains: "EVENT"
{agg_yaml}  condition: {sel_cond}
"""
        parsed = self.parse_yaml_rule(raw_yaml, existing_id=r_id)
        if parsed:
            return parsed
        return leg

    @classmethod
    def parse_yaml_rule(cls, raw_yaml: str, existing_id: Optional[str] = None) -> Optional[dict]:
        """Parses and validates a Sigma-style YAML detection rule string."""
        if not raw_yaml or not raw_yaml.strip():
            return None

        if yaml is not None:
            try:
                doc = yaml.safe_load(raw_yaml)
            except Exception as e:
                raise ValueError(f"YAML syntax error: {e}")
        else:
            try:
                import json
                doc = json.loads(raw_yaml)
            except Exception:
                doc = {}
                for line in raw_yaml.splitlines():
                    if ":" in line and not line.strip().startswith("#"):
                        k, v = line.split(":", 1)
                        doc[k.strip()] = v.strip().strip('"').strip("'")

        if not isinstance(doc, dict):
            raise ValueError("Root YAML must be an object/dictionary.")

        rule_id = str(doc.get("id") or existing_id or f"rule-{uuid.uuid4().hex[:8]}")
        title = str(doc.get("title") or doc.get("name") or "Untitled Rule").strip()
        severity = str(doc.get("severity") or doc.get("level") or "HIGH").upper()
        if severity not in ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL", "WARNING"):
            severity = "HIGH"
        if severity == "WARNING":
            severity = "HIGH"

        description = str(doc.get("description") or "").strip()
        status = str(doc.get("status") or "production").strip()
        enabled = bool(doc.get("enabled", True))
        detection = doc.get("detection")

        if not isinstance(detection, dict):
            raise ValueError("Rule must specify a 'detection' section with selections and condition.")

        condition = str(detection.get("condition") or "selection").strip()
        if not condition:
            condition = "selection"

        aggregation = detection.get("aggregation")
        if aggregation and not isinstance(aggregation, dict):
            raise ValueError("'aggregation' in detection must be a dictionary.")

        return {
            "id": rule_id,
            "name": title,
            "title": title,
            "severity": severity,
            "description": description,
            "status": status,
            "enabled": enabled,
            "detection": detection,
            "condition": condition,
            "yaml": raw_yaml.strip()
        }

    def _get_ev_val(self, ev: dict, field_path: str):
        """Extracts field value from event using dot notation and standard aliases."""
        if not isinstance(ev, dict):
            return None

        parts = field_path.split(".")
        curr = ev
        for part in parts:
            if isinstance(curr, dict):
                if part in curr:
                    curr = curr[part]
                elif part == "metadata" and "metadata" in curr and isinstance(curr["metadata"], dict):
                    curr = curr["metadata"]
                else:
                    curr = None
                    break
            else:
                curr = None
                break

        if curr is not None:
            return curr

        # Fallbacks for common aliases
        meta = ev.get("metadata", {}) or {}
        if field_path in ("command", "cmd", "cmdline"):
            return ev.get("command") or meta.get("command") or meta.get("cmd") or ev.get("message")
        if field_path in ("user", "username"):
            return ev.get("user") or meta.get("user")
        if field_path in ("dest_port", "port"):
            return ev.get("port") or meta.get("port")
        if field_path in ("destination", "dest", "target", "dst"):
            return ev.get("destination") or ev.get("dest") or meta.get("destination") or meta.get("target")
        if field_path in ("source", "src"):
            return ev.get("source") or ev.get("src") or meta.get("source")
        if field_path == "protocol":
            return ev.get("protocol") or meta.get("protocol")
        if field_path == "conflict":
            return meta.get("conflict")

        return None

    def _match_selection_block(self, block: dict, event: dict) -> bool:
        """Evaluates a selection block against an event."""
        if not isinstance(block, dict):
            return False

        for key, expected in block.items():
            if "|" in key:
                field_name, modifier = key.split("|", 1)
                modifier = modifier.lower().strip()
            else:
                field_name = key
                modifier = "exact"

            actual_val = self._get_ev_val(event, field_name)
            str_actual = str(actual_val or "")
            str_actual_lower = str_actual.lower()

            if modifier == "exact":
                if isinstance(expected, list):
                    # Membership
                    exp_strs = [str(x).lower() for x in expected]
                    if str_actual_lower not in exp_strs:
                        return False
                elif isinstance(expected, bool):
                    if bool(actual_val) != expected:
                        return False
                else:
                    if str_actual_lower != str(expected).lower():
                        return False

            elif modifier == "contains":
                if isinstance(expected, list):
                    matched_any = any(str(sub).lower() in str_actual_lower for sub in expected)
                    if not matched_any:
                        return False
                else:
                    if str(expected).lower() not in str_actual_lower:
                        return False

            elif modifier == "contains_all":
                if isinstance(expected, list):
                    matched_all = all(str(sub).lower() in str_actual_lower for sub in expected)
                    if not matched_all:
                        return False
                else:
                    if str(expected).lower() not in str_actual_lower:
                        return False

            elif modifier == "startswith":
                if isinstance(expected, list):
                    matched_any = any(str_actual_lower.startswith(str(sub).lower()) for sub in expected)
                    if not matched_any:
                        return False
                else:
                    if not str_actual_lower.startswith(str(expected).lower()):
                        return False

            elif modifier == "endswith":
                if isinstance(expected, list):
                    matched_any = any(str_actual_lower.endswith(str(sub).lower()) for sub in expected)
                    if not matched_any:
                        return False
                else:
                    if not str_actual_lower.endswith(str(expected).lower()):
                        return False

            elif modifier in ("in", "list"):
                exp_list = expected if isinstance(expected, list) else [expected]
                exp_strs = [str(x).lower() for x in exp_list]
                if str_actual_lower not in exp_strs:
                    return False

            elif modifier == "regex":
                try:
                    if not re.search(str(expected), str_actual, re.IGNORECASE):
                        return False
                except Exception:
                    return False

        return True

    def _evaluate_condition(self, condition: str, selection_results: Dict[str, bool]) -> bool:
        """Evaluates boolean condition expression over selection names."""
        expr = condition.strip()
        # Clean boolean tokens
        expr = re.sub(r"\bAND\b", "and", expr, flags=re.IGNORECASE)
        expr = re.sub(r"\bOR\b", "or", expr, flags=re.IGNORECASE)
        expr = re.sub(r"\bNOT\b", "not", expr, flags=re.IGNORECASE)

        # Replace any 1 of selection_* or all of selection_*
        if "1 of " in expr:
            expr = re.sub(r"1 of (selection\w*)", r"any([\1])", expr)
        if "all of " in expr:
            expr = re.sub(r"all of (selection\w*)", r"all([\1])", expr)

        try:
            return bool(eval(expr, {"__builtins__": {}}, selection_results))
        except Exception:
            # Fallback: if all matched selections are true
            return any(selection_results.values()) if "or" in condition else all(selection_results.values())

    def _eval_aggregation(self, agg_config: dict, selection_func, current_event: dict) -> bool:
        """Evaluates stateful sliding-window aggregations."""
        if not isinstance(agg_config, dict):
            return True

        op = agg_config.get("operator", ">=")
        threshold = int(agg_config.get("threshold", 1))
        tf_str = str(agg_config.get("timeframe", "60s")).lower().replace("s", "")
        window_sec = float(tf_str) if tf_str.isdigit() else 60.0
        group_by = agg_config.get("by", "source")
        distinct = bool(agg_config.get("distinct", False))
        field = agg_config.get("field", "destination")

        now = time.time()
        group_val = self._get_ev_val(current_event, group_by) if group_by else None

        relevant_events = []
        for ts, ev in self._history:
            if (now - ts) > window_sec:
                continue
            if group_by and group_val is not None:
                ev_group_val = self._get_ev_val(ev, group_by)
                if ev_group_val != group_val:
                    continue
            if selection_func and not selection_func(ev):
                continue
            relevant_events.append(ev)

        if distinct and field:
            values = set()
            for ev in relevant_events:
                val = self._get_ev_val(ev, field)
                if val:
                    values.add(str(val))
            metric_val = len(values)
        else:
            metric_val = len(relevant_events)

        if op == ">=":
            return metric_val >= threshold
        elif op == ">":
            return metric_val > threshold
        elif op == "==":
            return metric_val == threshold
        elif op == "<=":
            return metric_val <= threshold
        elif op == "<":
            return metric_val < threshold
        return False

    def match_rule(self, rule: dict, event: dict) -> bool:
        """Evaluates a single YAML rule against an incoming event."""
        if not rule.get("enabled", True):
            return False

        detection = rule.get("detection")
        if not detection:
            return False

        # 1. Evaluate all selections and filters
        selection_results = {}
        for block_name, block_content in detection.items():
            if block_name in ("condition", "aggregation"):
                continue
            if isinstance(block_content, dict):
                selection_results[block_name] = self._match_selection_block(block_content, event)

        # 2. Evaluate condition expression
        cond_expr = detection.get("condition") or "selection"
        base_match = self._evaluate_condition(cond_expr, selection_results)
        if not base_match:
            return False

        # 3. Evaluate aggregation if configured
        aggregation = detection.get("aggregation")
        if aggregation:
            # If a command/tool execution matched directly, allow immediate alert
            if selection_results.get("selection_tool") or selection_results.get("selection_cmd"):
                return True

            # Pass a selector function that checks if past events also match non-filter selections
            def history_selector(past_ev):
                for b_name, b_cont in detection.items():
                    if b_name.startswith("filter"):
                        if isinstance(b_cont, dict) and self._match_selection_block(b_cont, past_ev):
                            return False
                    elif b_name.startswith("selection"):
                        if isinstance(b_cont, dict) and not self._match_selection_block(b_cont, past_ev):
                            return False
                return True

            return self._eval_aggregation(aggregation, history_selector, event)

        return True

    def process_event(self, event_data: dict):
        """Processes incoming ingested log event through the SOC detection pipeline."""
        if not event_data:
            return

        now = time.time()
        self._history.append((now, event_data))
        # Keep sliding window clean (max 5 minutes or 2000 events)
        if len(self._history) > 2000 or (self._history and now - self._history[0][0] > 300):
            self._history = [(t, ev) for (t, ev) in self._history if now - t <= 300]

        # Evaluate all active rules
        sim = self.simulation
        rules = sim.soc_state.get("rules", self.rules) if (sim and hasattr(sim, "soc_state")) else self.rules

        for rule in rules:
            try:
                if self.match_rule(rule, event_data):
                    self._trigger_alert(rule, event_data)
            except Exception:
                pass

    def _trigger_alert(self, rule: dict, event_data: dict):
        """Creates and stores a SOC Alert with deduplication/cooldown."""
        rule_id = rule.get("id", "")
        src = event_data.get("source") or event_data.get("host") or "unknown"
        cooldown_key = f"{rule_id}:{src}"
        now = time.time()

        detection = rule.get("detection", {})
        is_aggregated = bool(detection.get("aggregation"))

        # Cooldown: suppress duplicate alerts within 30s for aggregated rules, 5s for single-hit rules
        cd_window = 30 if is_aggregated else 5
        if cooldown_key in self._alert_cooldowns and (now - self._alert_cooldowns[cooldown_key]) < cd_window:
            return
        self._alert_cooldowns[cooldown_key] = now

        severity = rule.get("severity", "HIGH").upper()
        alert = {
            "id": f"alt-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}",
            "rule_id": rule_id,
            "rule_name": rule.get("title") or rule.get("name") or "Security Alert",
            "severity": severity,
            "event": event_data,
            "status": "NEW",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        sim = self.simulation
        if sim and hasattr(sim, "soc_state"):
            alerts = sim.soc_state.setdefault("alerts", [])
            alerts.insert(0, alert)
            if len(alerts) > self.max_alerts:
                alerts.pop()

            # Update host threat level for both target victim and attacking source
            meta = event_data.get("metadata", {}) or {}
            src_dev = self.resolve_device(sim, event_data.get("source")) or self.resolve_device(sim, event_data.get("host"))
            dst_dev = self.resolve_device(sim, meta.get("host")) or self.resolve_device(sim, event_data.get("destination"))

            for target_device in filter(None, {src_dev, dst_dev}):
                if severity == "CRITICAL":
                    target_device.soc_threat_level = "Compromised"
                elif severity in ("HIGH", "WARNING", "MEDIUM") and getattr(target_device, "soc_threat_level", "Normal") != "Compromised":
                    target_device.soc_threat_level = "Suspicious"

    @staticmethod
    def resolve_device(sim, name_or_ip):
        """Resolves device object from hostname, device id, or IP string."""
        if not sim or not name_or_ip:
            return None
        name_str = str(name_or_ip).split(":")[0].strip()
        dev = sim.hosts.get(name_str) or sim.routers.get(name_str) or sim.switches.get(name_str)
        if not dev and getattr(sim, "network", None) and hasattr(sim.network, "get_host_by_ip"):
            dev = sim.network.get_host_by_ip(name_str)
        return dev

    @classmethod
    def recalculate_threat_levels(cls, sim):
        """Recalculates all device threat levels dynamically based on active unresolved alerts."""
        if not sim or not hasattr(sim, "soc_state"):
            return

        active_alerts = [a for a in sim.soc_state.get("alerts", []) if a.get("status") != "RESOLVED"]
        all_devs = list(sim.hosts.values()) + list(sim.routers.values())

        device_max_sev = {}
        for alert in active_alerts:
            sev = (alert.get("severity") or "INFO").upper()
            ev = alert.get("event", {}) or {}
            meta = ev.get("metadata", {}) or {}

            associated_devs = {
                cls.resolve_device(sim, ev.get("source")),
                cls.resolve_device(sim, ev.get("host")),
                cls.resolve_device(sim, ev.get("destination")),
                cls.resolve_device(sim, meta.get("host"))
            }

            for d in associated_devs:
                if d:
                    cur_rank = {"CRITICAL": 3, "HIGH": 2, "WARNING": 2, "MEDIUM": 1, "LOW": 0, "INFO": 0}.get(sev, 0)
                    prev_rank = device_max_sev.get(d.name, -1)
                    if cur_rank > prev_rank:
                        device_max_sev[d.name] = cur_rank

        for dev in all_devs:
            rank = device_max_sev.get(dev.name, -1)
            if rank >= 3:
                dev.soc_threat_level = "Compromised"
            elif rank >= 1:
                dev.soc_threat_level = "Suspicious"
            else:
                dev.soc_threat_level = "Normal"
