
class SSUIConfig:
    """This class is used to store the configuration of the SSUI system."""
    
    def __init__(self):
        self._is_prepare = False
    
    def __call__(self, name):
        pass
    
    def is_prepare(self):
        return self._is_prepare
    
    def set_prepared(self):
        self._is_prepare = True