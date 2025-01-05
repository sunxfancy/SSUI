import os
from typing import List


class Sandbox:
    def __init__(self, base_path: str, module_path: str, app_path: str):
        self.default_level = "app" if app_path else "module"
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

    def get_path(self, level=None):
        if level is None:
            level = self.default_level
        if level == "base":
            return self.base_path()
        elif level == "module":
            return self.module_path()
        elif level == "app":
            return self.app_path()
        raise ValueError(
            f"Invalid level({level}), only 'base', 'module', 'app' are allowed"
        )

    def install_package(self, package: str, level=None):
        if level is None:
            level = self.default_level
        path = self.get_path(level)
        # install package in venv (using pip)
        if path:
            pip = os.path.join(path, "Scripts", "pip.exe")
            os.system(f"{pip} install {package}")

    def install_requirements(self, requirements: str, level=None):
        if level is None:
            level = self.default_level
        path = self.get_path(level)
        # install package in venv (using pip)
        if path:
            pip = os.path.join(path, "Scripts", "pip.exe")
            os.system(f"{pip} install --require-hashes --no-deps -r {requirements}")

    def run_script(self, script_path: str, level=None):
        if level is None:
            level = self.default_level
        path = self.get_path(level)
        # run script in venv
        if path:
            python = os.path.join(path, "Scripts", "python.exe")
            os.system(f"{python} {script_path}")
        
    
    def start_process(self, script_path: str, callable: str, args: dict):
        pass


class VenvManager:
    def __init__(self, path: str):
        self.path = path
        self.venvs = {}
        self.app_venvs = {}  # index with project path
        self.detect_existing_venvs()

    def detect_existing_venvs(self):
        module_path = os.path.join(self.path, "module")
        app_path = os.path.join(self.path, "app")

        if os.path.exists(module_path):
            for name in os.listdir(module_path):
                self.venvs[name] = os.path.join(module_path, name)
        if os.path.exists(app_path):
            for name in os.listdir(app_path):
                self.app_venvs[name] = os.path.join(app_path, name)

    def create_for_module(self, name: str) -> Sandbox:
        if name in self.venvs:
            return Sandbox(self.get_base_path(), self.get_module_path(name), None)
        path = self.get_module_path(name)
        self.run_venv(path)
        self.create_pth(path, [path, self.get_base_path()])
        self.venvs[name] = path
        return Sandbox(self.get_base_path(), path, None)

    def create_for_app(self, module_path: str, name: str) -> Sandbox:
        if name in self.app_venvs:
            return Sandbox(self.get_base_path(), module_path, self.app_venvs[name])
        path = self.get_app_path(name)
        self.run_venv(path)
        self.create_pth(path, [path, module_path, self.get_base_path()])
        self.app_venvs[name] = path
        return Sandbox(self.get_base_path(), module_path, path)

    def run_venv(self, path: str):
        python = self.get_python_bin()
        os.system(f"{python} -m venv {path}")

    def create_pth(self, path: str, search_paths: List[str]):
        pth_path = os.path.join(path, "Lib", "site-packages", "ss.pth")
        with open(pth_path, "w") as f:
            for p in search_paths:
                p = os.path.join(p, "Lib", "site-packages")
                p = os.path.abspath(p)
                f.write(p + "\n")

    def get_python_root(self):
        return os.path.join(self.path, "python")

    def get_python_bin(self):
        return os.path.join(self.get_python_root(), "python.exe")

    def get_base_path(self):
        return os.path.join(self.path, "base")

    def get_module_path(self, name: str):
        return os.path.join(self.path, "module", name)

    def get_app_path(self, path: str):
        return os.path.join(self.path, "app", path)


if __name__ == "__main__":
    import sys

    build_path = os.path.join(os.path.dirname(__file__), "..", ".build")
    manager = VenvManager(build_path)
    module = manager.create_for_module("shared")
    app = manager.create_for_app(manager.get_module_path("shared"), "app1")

    module.install_package("obj2html")
    app.install_package("obj2stl")
    app.install_package("numpy==1.26")

    app.run_script(sys.argv[1])
    