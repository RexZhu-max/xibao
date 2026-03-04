from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.config import POSTER_DIR, POSTER_FONT_PATH


def _safe_name(name: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fa5]+", "_", name.strip())
    return safe[:30] or "staff"


def _pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        POSTER_FONT_PATH,
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if not path:
            continue
        font_path = Path(path)
        if font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _palette(rank: int) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    if rank == 1:
        return (255, 126, 29), (255, 179, 71)
    if rank == 2:
        return (90, 107, 132), (140, 158, 176)
    return (203, 95, 69), (232, 145, 116)


def _draw_gradient(width: int, height: int, start: tuple[int, int, int], end: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (width, height), start)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(1, height - 1)
        color = tuple(int(start[i] + (end[i] - start[i]) * ratio) for i in range(3))
        draw.line([(0, y), (width, y)], fill=color)
    return image


def generate_top3_posters(report_date: str, top_three: list[dict[str, Any]]) -> list[dict[str, str]]:
    outputs: list[dict[str, str]] = []

    for row in top_three:
        rank = int(row["rank"])
        bg_start, bg_end = _palette(rank)
        image = _draw_gradient(1080, 1440, bg_start, bg_end)
        draw = ImageDraw.Draw(image)

        title_font = _pick_font(92)
        name_font = _pick_font(120)
        metric_font = _pick_font(58)
        date_font = _pick_font(40)

        draw.text((90, 120), "每日业绩喜报", font=title_font, fill=(255, 255, 255))
        draw.text((90, 300), f"TOP {rank}", font=metric_font, fill=(255, 243, 214))
        draw.text((90, 430), str(row["employee_name"]), font=name_font, fill=(255, 255, 255))

        draw.rounded_rectangle((90, 700, 990, 1130), radius=36, fill=(255, 255, 255))
        draw.text((140, 770), f"成交量：{row['deal_count']}", font=metric_font, fill=(54, 58, 77))
        draw.text((140, 870), f"高意向客户：{row['high_intent_count']}", font=metric_font, fill=(54, 58, 77))
        draw.text((140, 970), f"私域新增：{row['private_domain_new']}", font=metric_font, fill=(54, 58, 77))

        draw.text((90, 1230), f"统计日期：{report_date}", font=date_font, fill=(245, 245, 245))
        draw.text((90, 1300), "销售团队自动生成", font=date_font, fill=(245, 245, 245))

        filename = f"{report_date}_top{rank}_{_safe_name(str(row['employee_name']))}.png"
        output_path = POSTER_DIR / filename
        image.save(output_path, format="PNG")

        outputs.append(
            {
                "rank": str(rank),
                "employee_name": str(row["employee_name"]),
                "url": f"/static/posters/{filename}",
            }
        )

    return outputs
