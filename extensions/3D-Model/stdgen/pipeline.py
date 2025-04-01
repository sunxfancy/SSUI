from dataclasses import dataclass
import io
import os
import random
from typing import Dict, Optional
import numpy as np
import glob
import torch
from rembg import remove
from PIL import Image
from transformers import (
    CLIPTextModel,
    CLIPTokenizer,
    CLIPImageProcessor,
    CLIPVisionModelWithProjection,
)
from torchvision import transforms

from .multiview.pipeline_multiclass import StableUnCLIPImg2ImgPipeline
from .canonicalize.models.unet_mv2d_condition import UNetMV2DConditionModel
from .canonicalize.models.unet_mv2d_ref import UNetMV2DRefModel
from .canonicalize.pipeline_canonicalize import CanonicalizationPipeline
from einops import rearrange
from torchvision.utils import save_image
from diffusers import AutoencoderKL, DDIMScheduler
from tqdm.auto import tqdm
from accelerate.utils import set_seed
import matplotlib.pyplot as plt
from pathlib import Path
from torch.utils.data import Dataset, DataLoader

weight_dtype = torch.float16
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class BkgRemover:
    def __init__(self, force_cpu: Optional[bool] = True):
        # rembg 会自动处理设备选择，不需要特别指定
        pass

    def remove_background(
        self,
        img: np.ndarray,
        alpha_min: float,
        alpha_max: float,
    ) -> Image.Image:
        # 将 numpy 数组转换为 PIL Image
        if isinstance(img, np.ndarray):
            img = Image.fromarray(img)

        # 使用 rembg 移除背景
        img_after = remove(img, alpha_matting=True)

        # 处理 alpha 通道阈值
        img_array = np.array(img_after)
        alpha = img_array[:, :, 3]

        # 应用 alpha_min 和 alpha_max 阈值
        alpha[alpha < alpha_min * 255] = 0
        alpha[alpha > alpha_max * 255] = 255
        img_array[:, :, 3] = alpha

        return Image.fromarray(img_array, mode="RGBA")


def canonicalize(
    input_dir: str,
    output_dir: str,
    pretrained_model_path: str,
    validation: Dict,
    local_crossattn: bool = True,
    unet_from_pretrained_kwargs=None,
    unet_condition_type=None,
    use_noise=True,
    noise_d=256,
    seed: int = 42,
    timestep: int = 40,
    width_input: int = 640,
    height_input: int = 1024,
):
    def inference(
        validation_pipeline,
        bkg_remover,
        input_image,
        vae,
        feature_extractor,
        image_encoder,
        unet,
        ref_unet,
        tokenizer,
        text_encoder,
        pretrained_model_path,
        generator,
        validation,
        val_width,
        val_height,
        unet_condition_type,
        use_noise=True,
        noise_d=256,
        crop=False,
        seed=100,
        timestep=20,
    ):
        set_seed(seed)

        totensor = transforms.ToTensor()

        prompts = "high quality, best quality"
        prompt_ids = tokenizer(
            prompts,
            max_length=tokenizer.model_max_length,
            padding="max_length",
            truncation=True,
            return_tensors="pt",
        ).input_ids[0]

        # (B*Nv, 3, H, W)
        B = 1
        if input_image.mode != "RGBA":
            # remove background
            input_image = bkg_remover.remove_background(input_image, 0.1, 0.9)
        imgs_in = process_image(input_image, totensor, val_width, val_height)
        imgs_in = rearrange(
            imgs_in.unsqueeze(0).unsqueeze(0), "B Nv C H W -> (B Nv) C H W"
        )

        with torch.autocast(
            "cuda" if torch.cuda.is_available() else "cpu", dtype=weight_dtype
        ):
            imgs_in = imgs_in.to(device=device)
            # B*Nv images
            out = validation_pipeline(
                prompt=prompts,
                image=imgs_in.to(weight_dtype),
                generator=generator,
                num_inference_steps=timestep,
                prompt_ids=prompt_ids,
                height=val_height,
                width=val_width,
                unet_condition_type=unet_condition_type,
                use_noise=use_noise,
                **validation,
            )
            out = rearrange(out, "B C f H W -> (B f) C H W", f=1)

        img_buf = io.BytesIO()
        save_image(out[0], img_buf, format="PNG")
        img_buf.seek(0)
        img = Image.open(img_buf)

        torch.cuda.empty_cache()
        return img

    def set_seed(seed):
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)

    def process_image(image, totensor, width, height):
        assert image.mode == "RGBA"

        # Find non-transparent pixels
        non_transparent = np.nonzero(np.array(image)[..., 3])
        min_x, max_x = non_transparent[1].min(), non_transparent[1].max()
        min_y, max_y = non_transparent[0].min(), non_transparent[0].max()
        image = image.crop((min_x, min_y, max_x, max_y))

        # paste to center
        max_dim = max(image.width, image.height)
        max_height = int(max_dim * 1.2)
        max_width = int(max_dim / (height / width) * 1.2)
        new_image = Image.new("RGBA", (max_width, max_height))
        left = (max_width - image.width) // 2
        top = (max_height - image.height) // 2
        new_image.paste(image, (left, top))

        image = new_image.resize((width, height), resample=Image.BICUBIC)
        image = np.array(image)
        image = image.astype(np.float32) / 255.0
        assert image.shape[-1] == 4  # RGBA
        alpha = image[..., 3:4]
        bg_color = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        image = image[..., :3] * alpha + bg_color * (1 - alpha)
        return totensor(image)

    tokenizer = CLIPTokenizer.from_pretrained(
        pretrained_model_path, subfolder="tokenizer"
    )
    text_encoder = CLIPTextModel.from_pretrained(
        pretrained_model_path, subfolder="text_encoder"
    )
    image_encoder = CLIPVisionModelWithProjection.from_pretrained(
        pretrained_model_path, subfolder="image_encoder"
    )
    feature_extractor = CLIPImageProcessor()
    vae = AutoencoderKL.from_pretrained(pretrained_model_path, subfolder="vae")
    unet = UNetMV2DConditionModel.from_pretrained_2d(
        pretrained_model_path,
        subfolder="unet",
        local_crossattn=local_crossattn,
        **unet_from_pretrained_kwargs,
    )
    ref_unet = UNetMV2DRefModel.from_pretrained_2d(
        pretrained_model_path,
        subfolder="ref_unet",
        local_crossattn=local_crossattn,
        **unet_from_pretrained_kwargs,
    )

    text_encoder.to(device, dtype=weight_dtype)
    image_encoder.to(device, dtype=weight_dtype)
    vae.to(device, dtype=weight_dtype)
    ref_unet.to(device, dtype=weight_dtype)
    unet.to(device, dtype=weight_dtype)

    vae.requires_grad_(False)
    unet.requires_grad_(False)
    ref_unet.requires_grad_(False)

    # set pipeline
    noise_scheduler = DDIMScheduler.from_pretrained(
        pretrained_model_path, subfolder="scheduler-zerosnr"
    )
    validation_pipeline = CanonicalizationPipeline(
        vae=vae,
        text_encoder=text_encoder,
        tokenizer=tokenizer,
        unet=unet,
        ref_unet=ref_unet,
        feature_extractor=feature_extractor,
        image_encoder=image_encoder,
        scheduler=noise_scheduler,
    )
    validation_pipeline.set_progress_bar_config(disable=True)

    bkg_remover = BkgRemover()

    def canonicalize(image, width, height, seed, timestep):
        generator = torch.Generator(device=device).manual_seed(seed)
        return inference(
            validation_pipeline,
            bkg_remover,
            image,
            vae,
            feature_extractor,
            image_encoder,
            unet,
            ref_unet,
            tokenizer,
            text_encoder,
            pretrained_model_path,
            generator,
            validation,
            width,
            height,
            unet_condition_type,
            use_noise=use_noise,
            noise_d=noise_d,
            crop=True,
            seed=seed,
            timestep=timestep,
        )

    img_paths = sorted(glob.glob(os.path.join(input_dir, "*.png")))
    os.makedirs(output_dir, exist_ok=True)

    for path in tqdm(img_paths):
        img_input = Image.open(path)
        if (
            np.array(img_input).shape[-1] == 4
            and np.array(img_input)[..., 3].min() == 255
        ):
            # convert to RGB
            img_input = img_input.convert("RGB")
        img_output = canonicalize(img_input, width_input, height_input, seed, timestep)
        img_output.save(
            os.path.join(output_dir, f"{os.path.basename(path).split('.')[0]}.png")
        )


def multiview(
    input_dir: str,
    output_dir: str,
    pretrained_path: str,
    seed: int = 12345,
    num_levels: int = 3,
    width_input: int = 640,
    height_input: int = 1024,
):
    os.environ["OPENCV_IO_ENABLE_OPENEXR"] = "1"
    VIEWS = ["front", "front_right", "right", "back", "left", "front_left"]

    class SingleImageData(Dataset):
        def __init__(
            self,
            input_dir,
            prompt_embeds_path="./multiview/fixed_prompt_embeds_6view",
            image_transforms=[],
            total_views=6,
            ext="png",
            return_paths=True,
        ) -> None:
            """Create a dataset from a folder of images.
            If you pass in a root directory it will be searched for images
            ending in ext (ext can be a list)
            """
            self.input_dir = Path(input_dir)
            self.return_paths = return_paths
            self.total_views = total_views

            self.paths = glob.glob(str(self.input_dir / f"*.{ext}"))

            print("============= length of dataset %d =============" % len(self.paths))
            self.tform = image_transforms
            self.normal_text_embeds = torch.load(
                f"{prompt_embeds_path}/normal_embeds.pt"
            )
            self.color_text_embeds = torch.load(f"{prompt_embeds_path}/clr_embeds.pt")

        def __len__(self):
            return len(self.paths)

        def load_rgb(self, path, color):
            img = plt.imread(path)
            img = Image.fromarray(np.uint8(img * 255.0))
            new_img = Image.new("RGB", (1024, 1024))
            # white background
            width, height = img.size
            new_width = int(width / height * 1024)
            img = img.resize((new_width, 1024))
            new_img.paste((255, 255, 255), (0, 0, 1024, 1024))
            offset = (1024 - new_width) // 2
            new_img.paste(img, (offset, 0))
            return new_img

        def __getitem__(self, index):
            data = {}
            filename = self.paths[index]

            if self.return_paths:
                data["path"] = str(filename)
            color = 1.0
            cond_im_rgb = self.process_im(self.load_rgb(filename, color))
            cond_im_rgb = torch.stack([cond_im_rgb] * self.total_views, dim=0)

            data["image_cond_rgb"] = cond_im_rgb
            data["normal_prompt_embeddings"] = self.normal_text_embeds
            data["color_prompt_embeddings"] = self.color_text_embeds
            data["filename"] = filename.split("/")[-1]

            return data

        def process_im(self, im):
            im = im.convert("RGB")
            return self.tform(im)

        def tensor_to_image(self, tensor):
            return Image.fromarray(np.uint8(tensor.numpy() * 255.0))

    def convert_to_numpy(tensor):
        return (
            tensor.mul(255)
            .add_(0.5)
            .clamp_(0, 255)
            .permute(1, 2, 0)
            .to("cpu", torch.uint8)
            .numpy()
        )

    def save_image(tensor, fp):
        ndarr = convert_to_numpy(tensor)
        save_image_numpy(ndarr, fp)
        return ndarr

    def save_image_numpy(ndarr, fp):
        im = Image.fromarray(ndarr)
        # pad to square
        if im.size[0] != im.size[1]:
            size = max(im.size)
            new_im = Image.new("RGB", (size, size))
            # set to white
            new_im.paste((255, 255, 255), (0, 0, size, size))
            new_im.paste(im, ((size - im.size[0]) // 2, (size - im.size[1]) // 2))
            im = new_im
        # resize to 1024x1024
        im = im.resize((1024, 1024), Image.LANCZOS)
        im.save(fp)

    def run_multiview_infer(
        dataloader, pipeline, seed, height, width, save_dir, num_levels=3
    ):
        if seed is None:
            generator = None
        else:
            generator = torch.Generator(device=pipeline.unet.device).manual_seed(seed)

        images_cond = []
        for _, batch in tqdm(enumerate(dataloader)):
            torch.cuda.empty_cache()
            images_cond.append(batch["image_cond_rgb"][:, 0].cuda())
            imgs_in = torch.cat([batch["image_cond_rgb"]] * 2, dim=0).cuda()
            num_views = imgs_in.shape[1]
            imgs_in = rearrange(
                imgs_in, "B Nv C H W -> (B Nv) C H W"
            )  # (B*Nv, 3, H, W)

            target_h, target_w = imgs_in.shape[-2], imgs_in.shape[-1]

            normal_prompt_embeddings, clr_prompt_embeddings = (
                batch["normal_prompt_embeddings"].cuda(),
                batch["color_prompt_embeddings"].cuda(),
            )
            prompt_embeddings = torch.cat(
                [normal_prompt_embeddings, clr_prompt_embeddings], dim=0
            )
            prompt_embeddings = rearrange(prompt_embeddings, "B Nv N C -> (B Nv) N C")

            # B*Nv images
            unet_out = pipeline(
                imgs_in,
                None,
                prompt_embeds=prompt_embeddings,
                generator=generator,
                guidance_scale=3.0,
                output_type="pt",
                num_images_per_prompt=1,
                height=height,
                width=width,
                num_inference_steps=40,
                eta=1.0,
                num_levels=num_levels,
            )

            for level in range(num_levels):
                out = unet_out[level].images
                bsz = out.shape[0] // 2

                normals_pred = out[:bsz]
                images_pred = out[bsz:]

                cur_dir = save_dir
                os.makedirs(cur_dir, exist_ok=True)

                for i in range(bsz // num_views):
                    scene = batch["filename"][i].split(".")[0]
                    scene_dir = os.path.join(cur_dir, scene, f"level{level}")
                    os.makedirs(scene_dir, exist_ok=True)

                    img_in_ = images_cond[-1][i].to(out.device)
                    for j in range(num_views):
                        view = VIEWS[j]
                        idx = i * num_views + j
                        normal = normals_pred[idx]
                        color = images_pred[idx]

                        ## save color and normal---------------------
                        normal_filename = f"normal_{j}.png"
                        rgb_filename = f"color_{j}.png"
                        save_image(normal, os.path.join(scene_dir, normal_filename))
                        save_image(color, os.path.join(scene_dir, rgb_filename))

        torch.cuda.empty_cache()

    def load_multiview_pipeline(pretrained_path):
        pipeline = StableUnCLIPImg2ImgPipeline.from_pretrained(
            pretrained_path,
            torch_dtype=torch.float16,
        )
        pipeline.unet.enable_xformers_memory_efficient_attention()
        if torch.cuda.is_available():
            pipeline.to(device)
        return pipeline

    set_seed(seed)
    pipeline = load_multiview_pipeline(pretrained_path)
    if torch.cuda.is_available():
        pipeline.to(device)

    image_transforms = [
        transforms.Resize(int(max(height_input, width_input))),
        transforms.CenterCrop((height_input, width_input)),
        transforms.ToTensor(),
        transforms.Lambda(lambda x: x * 2.0 - 1),
    ]
    image_transforms = transforms.Compose(image_transforms)

    prompt_embeds_path = os.path.join(os.path.dirname(__file__), "multiview", "fixed_prompt_embeds_6view")
    dataset = SingleImageData(
        prompt_embeds_path=prompt_embeds_path,
        image_transforms=image_transforms,
        input_dir=input_dir,
        total_views=6,
    )
    dataloader = torch.utils.data.DataLoader(
        dataset, batch_size=1, shuffle=False, num_workers=0
        
    )
    os.makedirs(output_dir, exist_ok=True)

    with torch.no_grad():
        run_multiview_infer(
            dataloader,
            pipeline,
            seed=seed,
            height=height_input,
            width=width_input,
            save_dir=output_dir,
            num_levels=num_levels,
        )
