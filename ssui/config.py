
class SSUIConfig:
    """This class is used to store the configuration of the SSUI system."""
    
    def __init__(self):
        self._is_prepare = False
        self._config = {}
        self._update = {}
        self._current = None
    
    def __call__(self, name):
        if self._config.get(name) is None:
            self._config[name] = {}
        self._current = name
        return self
    
    def __getitem__(self, name):
        print('getitem: ', self._current, name)
        print('current config: ', self._config)
        if self.is_prepare():
            return self._config[self._current][name]
        else:
            if self._update.get(self._current) is not None:
                if self._update[self._current].get(name) is not None:
                    return self._update[self._current][name]
            return self._config[self._current][name]['default']
    
    def __contains__(self, name):
        if self.is_prepare():
            return self._config[self._current].get(name) is not None
        else:
            return self._update[self._current].get(name) is not None or self._config[self._current].get(name) is not None

    def __setitem__(self, name, value):
        if self.is_prepare():
            self._config[self._current][name] = value
        else:
            if self._update.get(self._current) is not None:
                self._update[self._current][name] = value
            else:
                self._update[self._current] = {name: value}
    
    def is_prepare(self):
        return self._is_prepare
    
    def set_prepared(self, is_prepare: bool = True):
        self._is_prepare = is_prepare