from typing import List, Optional, Tuple

from ssui import workflow
from ssui.config import SSUIConfig
from ssui_llm.Text import Chat, TextModel

config = SSUIConfig()


@workflow
def chat(model: TextModel, prompt: str,
         history: Optional[List[Tuple[str, str]]] = None,
         system_prompt: str = "") -> Tuple[str, List[Tuple[str, str]]]:
    return Chat(config("Chat"), model, prompt, history, system_prompt)
