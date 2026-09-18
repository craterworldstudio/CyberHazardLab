from dataclasses import dataclass

@dataclass
class Service:
    name : str
    protocol : str
    port : int
    status : str = "stopped"
    config : dict = None
    enabled : bool = True

    def __post_init__(self):
        if self.config is None:
            self.config = {}

