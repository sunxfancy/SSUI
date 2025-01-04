import importlib
import importlib.util
import importlib.machinery
import inspect
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from ssui.annotation import get_callables, reset_callables

class SSLoader:
    def __init__(self):
        self.callables = []

    def load(self, path):
        file_path = os.path.abspath(path)
        # Define the module name and file path
        module_name = file_path.split("/")[-1].split(".")[0]

        # Create a module specification
        self.spec = importlib.util.spec_from_file_location(module_name, file_path)

        # Check if spec is None (e.g., file not found)
        if self.spec is None:
            raise FileNotFoundError(f"Could not find module at: {file_path}")

        # Create a module object from the specification
        self.module = importlib.util.module_from_spec(self.spec)

        # Get the module's loader and execute the module
        loader = importlib.machinery.SourceFileLoader(module_name, file_path)
        self.spec.loader = loader

    # Execute the module and get the callables
    def Execute(self):
        reset_callables()
        M = self.spec.loader.exec_module(self.module)
        self.callables = get_callables()
        if M.config:
            self.config = M.config

    # Prepare call the target function
    def GetConfig(self, name: str, args: dict):
        callable = None
        for func in self.callables:
            if func.__name__ == name:
                callable = func
                break
        
        if callable:
            self.config.set_prepared()
            callable(*args)

    def Show(self):
        print(self.callables)
        for func, param_types, return_type in self.callables:
            param_type = {param: param_types[param].__module__ + '.' + param_types[param].__name__ for param in param_types}
            return_type = [return_type.__name__]
            print(f"API: {func.__name__}")
            print(f"Parameters: {param_type}")
            print(f"Return type: {return_type}")
            print()


if __name__ == '__main__':
    loader = SSLoader()
    loader.load(sys.argv[1])
    loader.Execute()
    loader.Show()