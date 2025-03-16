import unittest
import os
import tempfile
import yaml
from ss_executor.loader import SSLoader, SSProject, search_project_root

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
            
        self.project = SSProject(self.temp_dir)
        
    def test_version(self):
        """测试版本获取"""
        self.assertEqual(self.project.version(), '1.0.0')
        
    def test_dependencies(self):
        """测试依赖项解析"""
        deps = self.project.dependencies()
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

if __name__ == '__main__':
    unittest.main()
