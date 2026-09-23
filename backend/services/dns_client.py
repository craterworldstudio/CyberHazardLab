from .base import ServiceDaemon

class DNSClientDaemon(ServiceDaemon):
    def on_start(self, service_model):
        if hasattr(self, 'config') and 'nameserver' in self.config:
            ns = self.config['nameserver'].strip()
            if ns:
                self.host.dns_server = ns
