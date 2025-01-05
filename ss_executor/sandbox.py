import os

class Sandbox:
    def __init__(self, base_path: str, module_path: str, app_path: str):
        self.paths = [base_path, module_path, app_path]
        
    def base_path(self):
        return self.paths[0]
    
    def module_path(self):
        return self.paths[1]
    
    def app_path(self):
        return self.paths[2]
        
    def check_env(self):
        for path in self.paths:
            if not os.path.exists(path):
                os.makedirs(path)
                # create venv

    def create_venv(self, path):
        pass
    
    def install_package(self, package_name: str, level='app'):
        if level == 'base':
            path = self.base_path
        elif level == 'app':
            path = self.app_path
        elif level == 'module':
            path = self.module_path
        
        # install package in venv (using pip)
        
    def start_process(self, script_path: str, callable: str, args: dict):
        pass

class VenvManager:
    def __init__(self, path: str):
        self.venvs = {}
        self.app_venvs = {} # index with project path
    
    def create_for_module(self, name: str):
        pass
    
    def create_for_app(self, path: str):
        pass
