from typing import List, Optional, Tuple

from ssui import workflow
from ssui.config import SSUIConfig
from ssui_llm.Qwen import Chat, QwenModel

config = SSUIConfig()


@workflow
def chat(model: QwenModel, prompt: str, history: Optional[List[Tuple[str, str]]] = None) -> Tuple[str, List[Tuple[str, str]]]:
    return Chat(config("Chat"), model, prompt, history)
