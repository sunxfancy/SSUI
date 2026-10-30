"""Infer the conversation protocol from resolved workflow annotations."""
import types
from typing import Union, get_args, get_origin

from server.models import ConversationInfo


def _unwrap(annotation):
    if get_origin(annotation) in (Union, types.UnionType):
        members = [item for item in get_args(annotation) if item is not type(None)]
        if len(members) == 1:
            return members[0]
    return annotation


def _pairs(annotation):
    annotation = _unwrap(annotation)
    if get_origin(annotation) is not list:
        return False
    args = get_args(annotation)
    return (len(args) == 1 and get_origin(args[0]) is tuple
            and get_args(args[0]) == (str, str))


def infer_conversation(params, returns):
    """Only unambiguous text + context signatures opt into conversation UI.

    Pair histories can be returned or accumulated from a plain string response.
    String contexts must be named history/context and returned explicitly.
    """
    contexts = [(name, "pairs") for name, annotation in params.items() if _pairs(annotation)]
    contexts += [(name, "text") for name, annotation in params.items()
                 if name in ("history", "context") and _unwrap(annotation) is str]
    if len(contexts) != 1:
        return None
    history, kind = contexts[0]
    texts = [name for name, annotation in params.items()
             if annotation is str and name not in (history, "system_prompt", "system")]
    preferred = [name for name in texts if name in ("prompt", "message", "text", "query", "input")]
    if len(preferred) == 1:
        prompt = preferred[0]
    elif len(texts) == 1:
        prompt = texts[0]
    else:
        return None
    outputs = get_args(returns) if get_origin(returns) is tuple else (returns,)
    if not outputs or outputs[0] is not str:
        return None
    if len(outputs) == 1 and kind == "pairs":
        context_output = None
    elif len(outputs) == 2 and ((_pairs(outputs[1]) and kind == "pairs")
                                or (outputs[1] is str and kind == "text")):
        context_output = 1
    else:
        return None
    return ConversationInfo(prompt_param=prompt, context_param=history,
                            context_kind=kind, context_output=context_output)
