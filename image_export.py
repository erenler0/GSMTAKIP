"""
image_export.py
----------------
Farkli ekranlardaki verileri estetik JPG gorseller olarak disari aktarmak
icin kullanilan yardimci fonksiyonlar (Pillow + Matplotlib).
"""

import io
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

_TITLE_FONT_CANDIDATES = ["DejaVuSans-Bold.ttf"]
_TEXT_FONT_CANDIDATES = ["DejaVuSans.ttf"]


def _load_font(candidates, size):
    for name in candidates:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_info_card_jpg(title, fields: dict, subtitle=None):
    """Tek bir kesinti/saha bilgisini gosteren kart. fields: {etiket: deger}."""
    width = 900
    height = 180 + 55 * len(fields)
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    font_title = _load_font(_TITLE_FONT_CANDIDATES, 34)
    font_label = _load_font(_TITLE_FONT_CANDIDATES, 22)
    font_value = _load_font(_TEXT_FONT_CANDIDATES, 22)
    font_sub = _load_font(_TEXT_FONT_CANDIDATES, 18)

    draw.rectangle([0, 0, width, 90], fill=(20, 60, 110))
    draw.text((30, 25), str(title), font=font_title, fill=(255, 255, 255))
    if subtitle:
        draw.text((30, 102), str(subtitle), font=font_sub, fill=(70, 70, 70))

    y = 140
    for label, value in fields.items():
        draw.text((30, y), f"{label}:", font=font_label, fill=(20, 60, 110))
        wrapped = textwrap.wrap(str(value) if value is not None else "-", width=55) or ["-"]
        for j, line in enumerate(wrapped):
            draw.text((280, y + j * 26), line, font=font_value, fill=(30, 30, 30))
        y += max(45, 26 * len(wrapped) + 15)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf


def generate_table_jpg(df, title="Rapor"):
    """Bir DataFrame'i tablo goruntusune donusturur (JPEG)."""
    if df is None or df.empty:
        df = df.copy() if df is not None else __import__("pandas").DataFrame({"Bilgi": ["Veri yok"]})

    n_rows = max(len(df), 1)
    n_cols = max(len(df.columns), 1)
    fig_height = max(2.2, 0.42 * (n_rows + 2))
    fig_width = max(8, 1.6 * n_cols)

    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")
    ax.set_title(title, fontsize=15, fontweight="bold", pad=16)

    table = ax.table(
        cellText=df.astype(str).values,
        colLabels=df.columns,
        loc="center",
        cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(9)
    table.scale(1, 1.4)

    for (row, _col), cell in table.get_celld().items():
        if row == 0:
            cell.set_facecolor("#14406e")
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor("#f5f7fa" if row % 2 == 0 else "#ffffff")

    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="jpg", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_diff_report_jpg(added, removed):
    """Excel senkronizasyonu sonrasi eklenen/silinen saha fark raporu (JPEG)."""
    added = list(added) if added else []
    removed = list(removed) if removed else []
    lines_added = added if added else ["(Yok)"]
    lines_removed = removed if removed else ["(Yok)"]

    height = 170 + 24 * (len(lines_added) + len(lines_removed) + 4)
    img = Image.new("RGB", (820, height), "white")
    draw = ImageDraw.Draw(img)

    font_title = _load_font(_TITLE_FONT_CANDIDATES, 28)
    font_h = _load_font(_TITLE_FONT_CANDIDATES, 20)
    font_t = _load_font(_TEXT_FONT_CANDIDATES, 16)

    draw.rectangle([0, 0, 820, 70], fill=(20, 60, 110))
    draw.text((20, 20), "Saha Senkronizasyonu - Fark Raporu", font=font_title, fill="white")

    y = 90
    draw.text((20, y), f"Eklenen Sahalar ({len(added)}):", font=font_h, fill=(0, 130, 0))
    y += 30
    for name in lines_added:
        draw.text((30, y), f"+ {name}", font=font_t, fill=(0, 100, 0))
        y += 24

    y += 20
    draw.text((20, y), f"Silinen Sahalar ({len(removed)}):", font=font_h, fill=(160, 0, 0))
    y += 30
    for name in lines_removed:
        draw.text((30, y), f"- {name}", font=font_t, fill=(140, 0, 0))
        y += 24

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return buf
