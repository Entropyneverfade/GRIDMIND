"""原创 GRIDMIND 电网图标：深蓝网格与青色 M 形能量路径。"""

from pathlib import Path

from PIL import Image, ImageDraw


def main():
    """高分辨率抗锯齿绘制，再生成Windows多尺寸ICO。"""
    root = Path(__file__).resolve().parent
    scale = 4
    size = 256 * scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    s = lambda v: round(v * scale)
    draw.rounded_rectangle((s(12), s(12), s(244), s(244)), radius=s(52), fill="#122341")
    # 小刻度仍可辨的发光网络：两横两纵，交点表示调度节点。
    for x in (75, 128, 181):
        draw.line((s(x), s(43), s(x), s(213)), fill="#245270", width=s(2))
    for y in (75, 128, 181):
        draw.line((s(43), s(y), s(213), s(y)), fill="#245270", width=s(2))
    for x, y in ((75, 75), (181, 75), (75, 181), (181, 181)):
        draw.ellipse((s(x - 5), s(y - 5), s(x + 5), s(y + 5)), fill="#27D8C4")
    path = [(51, 185), (77, 92), (113, 149), (142, 85), (179, 155), (205, 70)]
    points = [(s(x), s(y)) for x, y in path]
    draw.line(points, fill="#0C5273", width=s(24), joint="curve")
    draw.line(points, fill="#3EE7DA", width=s(14), joint="curve")
    draw.ellipse((s(196), s(61), s(214), s(79)), fill="#F6F8FF")
    icon = image.resize((256, 256), Image.Resampling.LANCZOS)
    icon.save(root / "gridmind.png")
    icon.save(root / "gridmind.ico", format="ICO",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main()
