from typing import *
import torch
import torch.nn as nn
from .. import models
from collections.abc import Mapping


class StageModels(Mapping):
    """Inference weights loaded on demand and discarded without CPU offload."""
    def __init__(self, sources, loader):
        self.sources = sources
        self.loader = loader
        self.loaded = {}

    def __iter__(self):
        return iter(self.sources)

    def __len__(self):
        return len(self.sources)

    def __contains__(self, name):
        return name in self.sources

    def __getitem__(self, name):
        if name not in self.loaded:
            print(f"Loading stage model: {name}", flush=True)
            self.loaded[name] = self.loader(self.sources[name]).eval()
        return self.loaded[name]

    def release(self, model):
        for name, loaded in list(self.loaded.items()):
            if loaded is model:
                # Local sampler references may survive until the stage returns.
                # Meta discards storage without allocating another CPU copy.
                model.to('meta')
                del self.loaded[name]
                return
        raise ValueError('Model is not owned by this stage store')


class Pipeline:
    """
    A base class for pipelines.
    """
    def __init__(
        self,
        models: dict[str, nn.Module] = None,
    ):
        if models is None:
            return
        self.models = models
        for model in self.models.values():
            model.eval()

    @classmethod
    def from_pretrained(cls, path: str, config_file: str = "pipeline.json", low_ram: bool = False) -> "Pipeline":
        """
        Load a pretrained model.
        """
        import os
        import json
        is_local = os.path.exists(f"{path}/{config_file}")

        if is_local:
            config_file = f"{path}/{config_file}"
        else:
            from huggingface_hub import hf_hub_download
            config_file = hf_hub_download(path, config_file)

        with open(config_file, 'r') as f:
            args = json.load(f)['args']

        def load_model(source):
            from huggingface_hub.errors import EntryNotFoundError
            try:
                return models.from_pretrained(f"{path}/{source}")
            except (FileNotFoundError, EntryNotFoundError):
                # Memory/driver failures must not retry an unrelated hub path.
                return models.from_pretrained(source)

        sources = {k: v for k, v in args['models'].items()
                   if not hasattr(cls, 'model_names_to_load') or k in cls.model_names_to_load}
        if low_ram:
            new_pipeline = cls(None)
            new_pipeline.models = StageModels(sources, load_model)
            new_pipeline._pretrained_args = args
            return new_pipeline

        _models = {}
        for k, v in args['models'].items():
            if hasattr(cls, 'model_names_to_load') and k not in cls.model_names_to_load:
                continue
            try:
                _models[k] = models.from_pretrained(f"{path}/{v}")
            except Exception as e:
                _models[k] = models.from_pretrained(v)

        new_pipeline = cls(_models)
        new_pipeline._pretrained_args = args
        return new_pipeline

    def release_model(self, model):
        if isinstance(self.models, StageModels):
            self.models.release(model)
        else:
            model.cpu()

    @property
    def device(self) -> torch.device:
        if hasattr(self, '_device'):
            return self._device
        for model in self.models.values():
            if hasattr(model, 'device'):
                return model.device
        for model in self.models.values():
            if hasattr(model, 'parameters'):
                return next(model.parameters()).device
        raise RuntimeError("No device found.")

    def to(self, device: torch.device) -> None:
        for model in self.models.values():
            model.to(device)

    def cuda(self) -> None:
        self.to(torch.device("cuda"))

    def cpu(self) -> None:
        self.to(torch.device("cpu"))
