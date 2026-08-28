import json
import tempfile
import unittest
from pathlib import Path

from backend.model_manager.config import BaseModelType
from backend.model_manager.probe import PipelineFolderProbe, VaeFolderProbe


class Flux2ProbeTest(unittest.TestCase):
    def test_pipeline_probe_recognizes_flux2_transformer(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp)
            (model_path / "transformer").mkdir()
            (model_path / "transformer" / "config.json").write_text(
                json.dumps({"_class_name": "Flux2Transformer2DModel"}),
                encoding="utf-8",
            )

            self.assertEqual(
                PipelineFolderProbe(model_path).get_base_type(),
                BaseModelType.Flux2,
            )

    def test_vae_probe_recognizes_flux2_vae(self):
        with tempfile.TemporaryDirectory() as tmp:
            model_path = Path(tmp)
            (model_path / "config.json").write_text(
                json.dumps({"_class_name": "AutoencoderKLFlux2"}),
                encoding="utf-8",
            )

            self.assertEqual(
                VaeFolderProbe(model_path).get_base_type(),
                BaseModelType.Flux2,
            )


if __name__ == "__main__":
    unittest.main()
