"""Run SAM 3.1 image segmentation in a separate, official SAM3 environment.

Example: python scripts/sam31_image.py image.jpg "red car" output_dir
"""

import argparse
import json
from pathlib import Path

import torch
from PIL import Image
from sam3.model.sam3_image_processor import Sam3Processor
from sam3.model_builder import build_sam3_image_model, download_ckpt_from_hf


def main() -> None:
    parser = argparse.ArgumentParser(description="Segment an image using SAM 3.1")
    parser.add_argument("image", type=Path)
    parser.add_argument("prompt")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--checkpoint", type=Path, help="Local SAM 3.1 checkpoint; downloads from Hugging Face if omitted")
    parser.add_argument("--threshold", type=float, default=0.5)
    args = parser.parse_args()

    if not 0 <= args.threshold <= 1:
        parser.error("--threshold must be between 0 and 1")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    checkpoint = str(args.checkpoint) if args.checkpoint else download_ckpt_from_hf(version="sam3.1")
    model = build_sam3_image_model(device=device, checkpoint_path=checkpoint, load_from_HF=False)
    processor = Sam3Processor(model, device=device, confidence_threshold=args.threshold)

    with Image.open(args.image) as source:
        image = source.convert("RGB")
    with torch.inference_mode():
        result = processor.set_text_prompt(args.prompt, processor.set_image(image))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    instances = []
    for index, (mask, box, score) in enumerate(zip(result["masks"], result["boxes"], result["scores"])):
        mask_file = f"mask_{index:04d}.png"
        mask_image = Image.fromarray((mask.squeeze().cpu().numpy() > 0.5).astype("uint8") * 255)
        mask_image.save(args.output_dir / mask_file)
        instances.append({"mask": mask_file, "box": box.cpu().tolist(), "score": float(score.cpu())})

    (args.output_dir / "results.json").write_text(
        json.dumps({"prompt": args.prompt, "image": str(args.image), "instances": instances}, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
