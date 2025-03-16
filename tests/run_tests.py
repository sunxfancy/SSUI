import unittest
import sys
import os

def run_all_tests():
    """运行tests目录下的所有测试用例"""
    # 获取tests目录的路径
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 将tests目录添加到Python路径中
    sys.path.insert(0, os.path.dirname(tests_dir))
    
    # 发现所有测试用例
    loader = unittest.TestLoader()
    suite = loader.discover(tests_dir, pattern='*_test.py')
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回测试结果，用于确定退出码
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_all_tests()
    # 如果测试失败，使用非零退出码
    sys.exit(0 if success else 1) 