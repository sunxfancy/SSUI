import asyncio
import unittest
import os
import tempfile
import yaml
from pathlib import Path
from ss_executor.loader import SSLoader, SSProject, search_project_root
from ss_executor.__main__ import convert_task_param, convert_task_return
from ss_executor.model import Task
from ss_executor.scheduler import TaskScheduler
from ssui.base import Audio, Mesh, Voice
from tests.utils import should_run_model_tests

class TestSSLoader(unittest.TestCase):
    def setUp(self):
        self.loader = SSLoader()
        
    def test_load_nonexistent_file(self):
        """测试加载不存在的文件"""
        with self.assertRaises(FileNotFoundError):
            self.loader.load("nonexistent_file.py")
            
    def test_show_empty_loader(self):
        """测试显示空加载器的信息"""
        self.loader.callables = []
        self.loader.Show()  # 不应抛出异常

    def test_load_and_execute(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'examples', 'basic', 'workflow-sd1.py')
        self.loader.load(path)
        self.loader.Execute()
        self.loader.GetConfig('txt2img')

    def test_convert_nested_list_parameters(self):
        params = {
            "items": [
                {
                    "function": "ssui.base.Prompt.create",
                    "params": {"text": "first"},
                },
                {
                    "function": "ssui.base.Prompt.create",
                    "params": {"text": "second"},
                },
            ]
        }
        result = convert_task_param(params)
        self.assertEqual([item.text for item in result], ["first", "second"])

    def test_convert_primitive_task_return(self):
        result = convert_task_return(("output/motion.npz",), "workflow.py")
        self.assertEqual(result, ["output/motion.npz"])

    def _task_script(self, root):
        Path(root, "ssproject.yaml").write_text(
            "ssui_version: 1.0.0\ndependencies: []\n", encoding="utf-8"
        )
        script = Path(root, "workflow.py")
        script.write_text("", encoding="utf-8")
        return str(script)

    def test_convert_audio_and_voice_returns(self):
        with tempfile.TemporaryDirectory() as root:
            script = self._task_script(root)
            audio = convert_task_return(Audio("wav", audio=b"RIFF-test"), script)
            self.assertEqual(audio["type"], "audio")
            self.assertTrue(Path(audio["path"]).is_file())

            voice = convert_task_return(Voice("mp3", audio=b"voice", text="hello"), script)
            self.assertEqual(voice["text"], "hello")
            self.assertEqual(Path(voice["path"]).read_bytes(), b"voice")

    def test_convert_mesh_return(self):
        class FakeMesh:
            def export(self, path):
                Path(path).write_bytes(b"glTF")

        with tempfile.TemporaryDirectory() as root:
            result = convert_task_return(Mesh(FakeMesh()), self._task_script(root))
            self.assertEqual(result["type"], "mesh")
            self.assertEqual(result["format"], "glb")
            self.assertEqual(Path(result["path"]).read_bytes(), b"glTF")
        

class TestSSProject(unittest.TestCase):
    def setUp(self):
        # 创建临时目录和配置文件
        self.temp_dir = tempfile.mkdtemp()
        self.config_data = {
            'ssui_version': '1.0.0',
            'dependencies': [
                'package1 = 1.0.0',
                'package2 = 2.0.0'
            ]
        }
        
        with open(os.path.join(self.temp_dir, 'ssproject.yaml'), 'w') as f:
            yaml.dump(self.config_data, f)
            
        self.project = SSProject(path=self.temp_dir)
        
    def test_version(self):
        """测试版本获取"""
        self.assertEqual(self.project.version(), '1.0.0')
        
    def test_dependencies(self):
        """测试依赖项解析"""
        deps = self.project.dependencies_map()
        self.assertEqual(deps['package1'], '1.0.0')
        self.assertEqual(deps['package2'], '2.0.0')
        
    def test_search_project_root(self):
        """测试项目根目录搜索"""
        # 在临时目录下创建子目录
        sub_dir = os.path.join(self.temp_dir, 'sub', 'subsub')
        os.makedirs(sub_dir)
        
        # 测试从子目录搜索
        found_root = search_project_root(sub_dir)
        self.assertEqual(found_root, self.temp_dir)
        
    def tearDown(self):
        # 清理临时文件
        import shutil
        shutil.rmtree(self.temp_dir)

class TestScheduler(unittest.TestCase):
    def test_Task(self):
        task = Task(script="test.py", callable="test")
        self.assertEqual(task.script, "test.py")
        self.assertEqual(task.callable, "test")

        str = task.model_dump_json()
        task2 = Task.model_validate_json(str)
        self.assertEqual(task2.script, "test.py")
        self.assertEqual(task2.callable, "test")

    @unittest.skipIf(not should_run_model_tests(), "Skipping integration test")
    def test_scheduler_async(self):
        scheduler = TaskScheduler()
        async def run_scheduler():
            await scheduler.start()
            await scheduler.run_task(Task(script="test.py", callable="test"))
            await scheduler.stop()
        asyncio.run(run_scheduler())


