import unittest
import sys
import os
import argparse

def run_all_tests():
    """运行tests目录下的所有测试用例"""
    # 获取tests目录的路径
    tests_dir = os.path.dirname(os.path.abspath(__file__))
    extensions_dir = os.path.abspath(os.path.join(tests_dir, "..", "extensions"))
    for extension in os.listdir(extensions_dir):
        extension_dir = os.path.join(extensions_dir, extension)
        if os.path.isdir(extension_dir):
            sys.path.insert(0, extension_dir)
    
    # 将tests目录添加到Python路径中
    sys.path.insert(0, os.path.dirname(tests_dir))
    
    # 发现所有测试用例
    loader = unittest.TestLoader()
    suite = loader.discover(tests_dir, pattern='*_test.py')
    
    # 添加命令行参数解析
    parser = argparse.ArgumentParser(description='运行测试')
    parser.add_argument('--test', type=str, help='指定要运行的单个测试名称')
    args = parser.parse_args()
    
    # 根据参数决定运行哪些测试
    if args.test:
        # 只运行指定的测试
        specific_test = unittest.defaultTestLoader.loadTestsFromName(args.test)
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(specific_test)
    else:
        # 运行所有测试
        runner = unittest.TextTestRunner(verbosity=2)
        result = runner.run(suite)
    
    # 返回测试结果，用于确定退出码
    return result.wasSuccessful()

if __name__ == '__main__':
    success = run_all_tests()
    # 如果测试失败，使用非零退出码
    sys.exit(0 if success else 1) 