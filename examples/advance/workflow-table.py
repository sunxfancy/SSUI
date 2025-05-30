from ssui import workflow, Prompt, Image, Mesh
from ssui_image.Flux import FluxModel, FluxClip, FluxLatent, FluxDenoise, FluxLatentDecode
from ssui.config import SSUIConfig
from ssui_3dmodel.Trellis import TrellisModel, GenModel
from typing import List, Tuple
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import PIL.Image

config = SSUIConfig()


@workflow
def txt2img(model: FluxModel, positive: Prompt, negative: Prompt, table_data: List[List[str]]) -> Image:
    positive, negative = FluxClip(config("Prompt To Condition"), model, positive, negative)
    latent = FluxLatent(config("Create Empty Latent"))
    latent = FluxDenoise(config("Denoise"), model, latent, positive, negative)

    bg = FluxLatentDecode(config("Latent to Image"), model, latent)
    image = render_table_to_image(table_data)

    # 计算居中位置
    bg_img = bg._image
    table_img = image._image
    x = (bg_img.width - table_img.width) // 2
    y = (bg_img.height - table_img.height) // 2
    
    # 将表格居中并添加到背景上
    bg_img.paste(table_img, (x, y), table_img)

    return bg


@workflow
def render_table_to_image(table_data: List[List[str]], cell_padding: int = 10, font_size: int = 20) -> Image:
    """
    将表格数据渲染成图片
    
    Args:
        table_data: 二维列表，包含表格数据
        cell_padding: 单元格内边距
        font_size: 字体大小
    
    Returns:
        Image: 渲染后的表格图片
    """
    # 计算表格尺寸
    rows = len(table_data)
    cols = len(table_data[0]) if rows > 0 else 0
    
    # 创建字体对象
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except:
        font = ImageFont.load_default()
    
    # 计算每个单元格的宽度和高度
    cell_widths = []
    cell_heights = []
    
    for col in range(cols):
        max_width = 0
        for row in range(rows):
            text = str(table_data[row][col])
            bbox = font.getbbox(text)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
            max_width = max(max_width, width)
            if col == 0:  # 只需要计算一次行高
                cell_heights.append(height)
    
    cell_widths = [max_width + 2 * cell_padding for _ in range(cols)]
    cell_heights = [height + 2 * cell_padding for height in cell_heights]
    
    # 计算总宽度和高度
    total_width = sum(cell_widths)
    total_height = sum(cell_heights)
    
    # 创建图片
    image = PIL.Image.new('RGB', (total_width, total_height), 'white')
    draw = ImageDraw.Draw(image)
    
    # 绘制表格
    x, y = 0, 0
    for row in range(rows):
        for col in range(cols):
            # 绘制单元格边框
            draw.rectangle([x, y, x + cell_widths[col], y + cell_heights[row]], outline='black')
            
            # 绘制文本
            text = str(table_data[row][col])
            text_bbox = font.getbbox(text)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            text_x = x + (cell_widths[col] - text_width) // 2
            text_y = y + (cell_heights[row] - text_height) // 2
            
            draw.text((text_x, text_y), text, fill='black', font=font)
            
            x += cell_widths[col]
        x = 0
        y += cell_heights[row]
    
    # 创建SSUI Image对象
    return Image(image)


