from .base import ServiceDaemon

class DNSClientDaemon(ServiceDaemon):
    def on_start(self, service_model):
        self._service_model = service_model
        cfg = getattr(service_model, 'config', {}) or {}
        self.reload_config(cfg)

    def reload_config(self, cfg):
        self.config = cfg
        if isinstance(cfg, dict) and 'nameserver' in cfg:
            ns = str(cfg['nameserver']).strip()
            if ns:
                self.host.dns_server = ns
