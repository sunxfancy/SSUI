from typing import Dict, List, Tuple
from collections import defaultdict

class FileOpenerManager:
    _instance = None
    
    def __init__(self):
        self._file_openers: Dict[str, List[Tuple[str, str, str]]] = defaultdict(list)

    @classmethod
    def instance(cls) -> 'FileOpenerManager':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_opener(self, opener_name: str, file_extension: str, url_template: str, url_rest: str = "") -> None:
        """
        注册一个文件打开器
        
        Args:
            file_extension: 文件扩展名（例如：'.txt', '.pdf'）
            url_template: URL模板，用于打开该类型的文件
        """
        if file_extension not in self._file_openers:
            self._file_openers[file_extension] = []
        self._file_openers[file_extension].append((opener_name, url_template, url_rest))
    
    def get_opener(self, file_extension: str) -> list[Tuple[str, str, str]]:
        return self._file_openers[file_extension]
    
    def get_all_openers(self) -> Dict[str, List[Tuple[str, str, str]]]:
        return self._file_openers
