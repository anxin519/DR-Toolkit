"""生成 DICOM 运维工具图标"""
from PIL import Image, ImageDraw, ImageFont
import os

def make_icon():
    sizes = [256, 128, 64, 48, 32, 16]
    images = []

    for size in sizes:
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 背景圆角矩形（深蓝色）
        pad = size // 10
        r = size // 6
        bg_color = (30, 90, 160, 255)
        draw.rounded_rectangle([pad, pad, size - pad, size - pad],
                                radius=r, fill=bg_color)

        # 十字（白色，模拟医疗十字）
        cx, cy = size // 2, size // 2
        arm_w = max(size // 8, 2)
        arm_l = size // 3
        cross_color = (255, 255, 255, 255)
        # 横
        draw.rectangle([cx - arm_l, cy - arm_w, cx + arm_l, cy + arm_w], fill=cross_color)
        # 竖
        draw.rectangle([cx - arm_w, cy - arm_l, cx + arm_w, cy + arm_l], fill=cross_color)

        # 右下角小标记（橙色圆点，代表"数据/信号"）
        dot_r = max(size // 8, 3)
        dot_x = size - pad - dot_r - size // 12
        dot_y = size - pad - dot_r - size // 12
        draw.ellipse([dot_x - dot_r, dot_y - dot_r,
                      dot_x + dot_r, dot_y + dot_r],
                     fill=(255, 160, 30, 255))

        images.append(img)

    # 保存为 ICO
    images[0].save(
        'icon.ico',
        format='ICO',
        sizes=[(s, s) for s in sizes],
        append_images=images[1:]
    )
    print(f"图标已生成: icon.ico  ({os.path.getsize('icon.ico') // 1024} KB)")

if __name__ == '__main__':
    make_icon()
