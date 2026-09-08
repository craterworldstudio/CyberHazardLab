def reset(self):
    self.state = {
        "version": 1,
        "simulation": {
            "devices": [],
            "links": [],
            "interfaces": {},
            "subnets": {},
            "routes": {},
            "services": {}
        },
        "layout": {}
    }

    self.save()