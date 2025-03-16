
class SSUIConfig:
    """This class is used to store the configuration of the SSUI system."""
    
    def __init__(self):
        self._is_prepare = False
        self._config = {}
        self._current = None
    
    def __call__(self, name):
        self._config[name] = {}
        self._current = name
        return self
    
    def __getitem__(self, name):
        return self._config[self._current][name]
    
    def __setitem__(self, name, value):
        self._config[self._current][name] = value
    
    def is_prepare(self):
        return self._is_prepare
    
    def set_prepared(self, is_prepare: bool = True):
        self._is_prepare = is_prepare