"""Internal Kimodo CLI wrapper with an opt-in local text-encoder override."""

import os


def _configure_text_encoder_override() -> None:
    base_model = os.environ.get("SSUI_KIMODO_TEXT_ENCODER_BASE")
    if not base_model:
        return

    from kimodo.model.load_model import TEXT_ENCODER_PRESETS
    from kimodo.model.llm2vec.llm2vec import LLM2Vec

    TEXT_ENCODER_PRESETS["llm2vec"]["kwargs"]["base_model_name_or_path"] = (
        base_model
    )

    # The supported fallback is the same Llama 3 Instruct base with the MNTP
    # adapter merged. Its local config intentionally has no upstream repo name,
    # so preserve the instruction framing expected by the official encoder.
    original_prepare = LLM2Vec.prepare_for_tokenization

    def prepare_for_tokenization(self, text):
        if "Llama-3-8B-Instruct-LLM2Vec-mntp-merged" in base_model:
            return (
                "<|start_header_id|>user<|end_header_id|>\n\n"
                + text.strip()
                + "<|eot_id|>"
            )
        return original_prepare(self, text)

    LLM2Vec.prepare_for_tokenization = prepare_for_tokenization


def main() -> None:
    import torch
    requested = os.environ.get('SSUI_KIMODO_DEVICE','auto')
    device = requested
    if device == 'auto':
        device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
    if device == 'cuda' and not torch.cuda.is_available():
        raise RuntimeError('CUDA was requested but is unavailable')
    if device == 'mps':
        from _kimodo_mps import main as mps_main
        mps_main()
        return
    if requested not in ('auto','cuda','cpu'):
        raise ValueError(f'Unsupported Kimodo device: {requested}')
    if requested == 'cpu':
        from kimodo.scripts import generate
        original_load = generate.load_model
        def load_cpu(*args, **kwargs):
            kwargs['device'] = 'cpu'
            return original_load(*args, **kwargs)
        generate.load_model = load_cpu
    if os.environ.get('TEXT_ENCODER_DEVICE') == 'auto':
        os.environ['TEXT_ENCODER_DEVICE'] = device
    _configure_text_encoder_override()
    from kimodo.scripts.generate import main as kimodo_main

    kimodo_main()


if __name__ == "__main__":
    main()
