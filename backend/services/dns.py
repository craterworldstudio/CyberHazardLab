import threading
import traceback
import json
from .base import ServiceDaemon


class DNSServerDaemon(ServiceDaemon):

    def _get_config(self):
        cfg = {}
        if hasattr(self.host, "services"):
            for s in self.host.services:
                if s.name.upper() in ("DNS", "DNS_SERVER") and getattr(s, "config", None):
                    cfg = dict(s.config)
                    break
        elif hasattr(self, "_service_model") and getattr(self._service_model, "config", None):
            cfg = dict(self._service_model.config)
        else:
            cfg = dict(getattr(self, "config", {}) or {})
            
        # If tsig_key is not set in config, check if /etc/bind/db.local specifies one via comment
        if not cfg.get("tsig_key") and hasattr(self.host, "vfs"):
            try:
                db_file = self.host.vfs.path_to_tree("/etc/bind/db.local")
                if db_file and hasattr(db_file, "contents") and db_file.contents:
                    content = "\n".join(db_file.contents) if isinstance(db_file.contents, list) else str(db_file.contents)
                    for line in content.split("\n"):
                        line = line.strip()
                        if line.startswith("; TSIG Key Required for AXFR:"):
                            extracted = line.split(":", 1)[1].strip()
                            if extracted:
                                cfg["tsig_key"] = extracted
                                break
            except Exception:
                pass
        return cfg

    def _sync_to_vfs(self):
        # Write config records into a simulated BIND zone file on VFS
        if not hasattr(self.host, "vfs"):
            return
            
        vfs = self.host.vfs
        etc_bind = vfs.path_to_tree("/etc/bind")
        if not etc_bind:
            vfs.curr_fol = vfs.tree
            etc = vfs.get_item("etc")
            if not etc:
                from backend.database.fs import Folder
                etc = Folder("etc")
                etc.parent = vfs.tree
                etc.path = "/etc"
                vfs.tree.add(etc)
            vfs.curr_fol = etc
            bind = vfs.get_item("bind")
            if not bind:
                from backend.database.fs import Folder
                bind = Folder("bind")
                bind.parent = etc
                bind.path = "/etc/bind"
                etc.add(bind)
            etc_bind = bind

        cfg = self._get_config()
        records = cfg.get("records", [])
        
        zone_content = "; BIND data file for local zone\n$TTL 604800\n"
        zone_content += "@   IN  SOA ns.local. admin.local. ( 2 604800 86400 2419200 604800 )\n"
        
        for rec in records:
            if isinstance(rec, dict):
                name = rec.get("name", "@")
                rtype = rec.get("type", "A").upper()
                target = rec.get("target", "")
                priority = rec.get("priority", "")
                port = rec.get("port", "")
                
                if rtype == "SRV":
                    if priority or port:
                        zone_content += f"{name}\tIN\t{rtype}\t{priority} 100 {port} {target}\n"
                    else:
                        zone_content += f"{name}\tIN\t{rtype}\t{target}\n"
                else:
                    zone_content += f"{name}\tIN\t{rtype}\t{target}\n"
                    
        # Check TSIG key
        if cfg.get("tsig_key"):
            zone_content += f"\n; TSIG Key Required for AXFR: {cfg['tsig_key']}\n"
            
        from backend.database.fs import File
        vfs.curr_fol = etc_bind
        db_file = vfs.get_item("db.local")
        if not db_file:
            db_file = File("db.local")
            db_file.set_path(etc_bind.path)
            etc_bind.add(db_file)
        db_file.contents = zone_content

    def _read_from_vfs(self):
        # Returns parsed records from the zone file
        if not hasattr(self.host, "vfs"):
            return []
            
        vfs = self.host.vfs
        db_file = vfs.path_to_tree("/etc/bind/db.local")
        if not db_file or not hasattr(db_file, "contents"):
            return []
            
        records = []
        lines = db_file.contents.split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("$") or line.startswith("@"):
                continue
            parts = [p for p in line.split() if p]
            if len(parts) >= 4 and parts[1] == "IN":
                name = parts[0]
                rtype = parts[2]
                if rtype == "SRV":
                    if len(parts) >= 7:
                        target = parts[-1]
                        port = parts[-2]
                    else:
                        target = parts[-1]
                        port = "0"
                    records.append({"name": name, "type": rtype, "target": target, "port": port})
                else:
                    target = parts[3]
                    records.append({"name": name, "type": rtype, "target": target})
        return records
        
    def _get_zone_file_content(self):
        if not hasattr(self.host, "vfs"):
            return ""
        db_file = self.host.vfs.path_to_tree("/etc/bind/db.local")
        if not db_file:
            return ""
        return getattr(db_file, "contents", "")

    def on_start(self, service_model):
        self._service_model = service_model
        self._stop_event = threading.Event()
        self._sync_to_vfs()
        self._schedule_health_check(delay=1)

    def on_stop(self, service_model):
        if hasattr(self, '_stop_event'):
            self._stop_event.set()
        if hasattr(self, '_health_timer') and self._health_timer is not None:
            self._health_timer.cancel()
            self._health_timer = None

    def reload_config(self, cfg):
        self.config = cfg
        self._sync_to_vfs()
        if hasattr(self, '_stop_event') and not self._stop_event.is_set():
            if hasattr(self, '_health_timer') and self._health_timer is not None:
                self._health_timer.cancel()
            self._schedule_health_check(delay=1)

    def _schedule_health_check(self, delay=None):
        if hasattr(self, '_stop_event') and self._stop_event.is_set():
            return
        cfg = self._get_config()
        interval = float(cfg.get('health_interval', 30))
        if delay is None:
            delay = interval
        self._health_timer = threading.Timer(delay, self._run_health_check)
        self._health_timer.daemon = True
        self._health_timer.start()

    def _run_health_check(self):
        if hasattr(self, '_stop_event') and self._stop_event.is_set():
            return
        try:
            records = self._read_from_vfs()
            network = getattr(self.host, 'network', None)
            orchestrator = getattr(network, 'orchestrator', None)

            # Update status in the original config model so UI can see it
            cfg = self._get_config()
            cfg_records = cfg.get("records", [])

            for idx, rec in enumerate(records):
                target = rec.get('target', '').strip()
                if not target:
                    if idx < len(cfg_records): cfg_records[idx]['status'] = 'OFFLINE'
                    continue

                rtype = rec.get('type', 'A').upper()
                reachable = False
                
                # For PTR records: name is the IP address (e.g. 10.0.0.2), target is hostname (e.g. nas.local).
                # We can check health by resolving the target hostname back to IP or checking the PTR IP (rec['name']).
                check_ip = None
                if rtype == 'PTR':
                    # First try to resolve target hostname back to an IP
                    resolved_ip = self._resolve(target.upper(), network, rtype="A")
                    if resolved_ip:
                        check_ip = resolved_ip
                    elif rec.get('name'):
                        check_ip = rec.get('name').strip()
                elif rtype == 'CNAME':
                    check_ip = self._resolve(target.upper(), network, rtype="A")
                    if not check_ip:
                        check_ip = target
                else:
                    check_ip = target

                if orchestrator and hasattr(orchestrator, 'ping') and check_ip:
                    try:
                        result = orchestrator.ping(self.host, check_ip, payload='dns_health', ttl=64)
                        if isinstance(result, dict) and result.get("type") == "ECHO_REPLY":
                            reachable = True
                        elif result is not None and 'SUCCESS' in str(result).upper():
                            reachable = True
                    except Exception:
                        reachable = False

                if not reachable and check_ip:
                    # Check local host interfaces directly
                    for intf in getattr(self.host, 'interfaces', []):
                        if getattr(intf, 'ip', None) == check_ip:
                            reachable = True
                            break
                    # Check network devices if attached
                    if not reachable and network and hasattr(network, 'devices'):
                        for dev in network.devices:
                            for intf in getattr(dev, 'interfaces', []):
                                if getattr(intf, 'ip', None) == check_ip:
                                    reachable = True
                                    break
                            if reachable:
                                break

                if idx < len(cfg_records): 
                    # If PTR record, default to STATIC/ONLINE if reverse target or IP exists
                    if rtype == 'PTR':
                        cfg_records[idx]['status'] = 'ONLINE' if (reachable or rec.get('target')) else 'UNRESPONSIVE'
                    else:
                        cfg_records[idx]['status'] = 'ONLINE' if reachable else 'UNRESPONSIVE'
        except Exception:
            traceback.print_exc()
        finally:
            self._schedule_health_check()

    def _resolve(self, query: str, network, rtype="A", depth=0) -> str:
        if depth > 10:
            return None 
            
        records = self._read_from_vfs()
        
        for rec in records:
            if rec.get('name', '').strip().upper() == query:
                rec_type = rec.get('type', 'A').upper()
                target = rec.get('target', '').strip()
                
                # Handling generic A or specific record queries
                if rec_type == 'CNAME' and rtype in ("A", "CNAME"):
                    return self._resolve(target.upper(), network, rtype, depth + 1)
                elif rec_type == rtype or (rtype == "A" and rec_type in ("A", "CNAME")):
                    if rec_type == "SRV":
                        return f"{target}:{rec.get('port', '0')}"
                    return target

        if rtype == "PTR":
            for rec in records:
                if rec.get("target") == query and rec.get("type") in ("A", "CNAME"):
                    return rec.get("name")

        all_devices = list(network.orchestrator.hosts.values()) + list(network.orchestrator.routers.values())
        for dev in all_devices:
            if dev.name.upper() == query:
                ip = getattr(dev, "get_ip", lambda: None)()
                if not ip and dev.interfaces:
                    ip = dev.interfaces[0].ip
                if ip:
                    return ip

        return None

    def handle_udp(self, payload, connection, packet):
        payload_str = str(payload).strip()
        if not payload_str:
            return None

        try:
            # Payload format: "TYPE QUERY [TSIG_KEY]" or just "QUERY" (defaults to A)
            parts = payload_str.split()
            query_type = "A"
            query_target = ""
            tsig_key = None
            
            if len(parts) >= 2 and parts[0].upper() in ("A", "CNAME", "SRV", "PTR", "AXFR"):
                query_type = parts[0].upper()
                query_target = parts[1].upper()
                if len(parts) >= 3:
                    tsig_key = parts[2]
            else:
                query_target = parts[0].upper()

            if query_type == "AXFR":
                cfg = self._get_config()
                req_key = cfg.get("tsig_key")
                if req_key and tsig_key != req_key:
                    return "DNS_ERROR: AXFR Transfer Failed - Invalid or Missing TSIG Key"
                return f"DNS_AXFR_RESPONSE:\\n{self._get_zone_file_content()}"

            network = connection.network
            resolved = self._resolve(query_target, network, rtype=query_type)
            
            if resolved:
                return f"DNS_RESPONSE: {query_type} {query_target} -> {resolved}"
            
            return f"DNS_NXDOMAIN: '{query_target}' not found."

        except Exception as e:
            traceback.print_exc()
            return f"DNS_ERROR: {str(e)}"
