from typing import Any, Dict

class BaseStrategy:
    def __init__(self, name: str, parameters: Dict = None):
        self.name = name
        self.parameters = parameters or {} 