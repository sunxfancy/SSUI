

class Slider:
    def __init__(self, min, max, step, labels=None):
        self.min = min
        self.max = max
        self.step = step
        if labels is not None:
            self.labels = labels
        
class Select:
    def __init__(self, *args):
        self.options = args

class Switch:
    def __init__(self):
        pass