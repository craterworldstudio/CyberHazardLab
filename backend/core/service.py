from dataclasses import dataclass

@dataclass
class Service:
    name : str
    protocol : str
    port : int
    status : str = "stopped"     

