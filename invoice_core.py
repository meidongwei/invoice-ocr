"""发票识别核心逻辑。"""

from __future__ import annotations

import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

import pdfplumber

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
INVOICE_SUFFIXES = IMAGE_SUFFIXES | {".pdf"}
CSV_FIELDS = ["源文件", "发票类型", "销售方名称", "发票号码", "合计税额"]

INVOICE_TYPE_SPECIAL = "电子发票（增值税专用发票）"
INVOICE_TYPE_NORMAL = "电子发票（普通发票）"
INVOICE_TYPE_RAILWAY = "电子发票（铁路电子客票）"
KNOWN_INVOICE_TYPES = (
    INVOICE_TYPE_SPECIAL,
    INVOICE_TYPE_NORMAL,
    INVOICE_TYPE_RAILWAY,
)

_ocr_engine = None


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_app_root() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent


def get_cache_dir() -> Path:
    if is_frozen():
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            cache = base / "发票识别" / "models"
        elif sys.platform == "darwin":
            cache = Path.home() / "Library" / "Application Support" / "发票识别" / "models"
        else:
            cache = Path.home() / ".local" / "share" / "发票识别" / "models"
        cache.mkdir(parents=True, exist_ok=True)
        _seed_bundled_models(cache)
    else:
        cache = get_app_root() / ".paddlex"
        cache.mkdir(parents=True, exist_ok=True)
    return cache


def _seed_bundled_models(cache: Path) -> None:
    bundled = get_app_root() / ".paddlex"
    if not bundled.exists():
        return
    marker = cache / ".seeded"
    if marker.exists():
        return
    import shutil

    for item in bundled.iterdir():
        target = cache / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        elif not target.exists():
            shutil.copy2(item, target)
    marker.write_text("ok", encoding="utf-8")


def get_default_output_dir() -> Path:
    for name in ("Desktop", "桌面"):
        desktop = Path.home() / name
        if desktop.exists():
            return desktop
    if sys.platform == "win32":
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            for name in ("Desktop", "桌面"):
                desktop = Path(userprofile) / name
                if desktop.exists():
                    return desktop
    docs = Path.home() / "Documents"
    if docs.exists():
        return docs
    return Path.home()


def _disable_onednn() -> None:
    """强制禁用 Paddle 的 OneDNN/PIR executor，解决部分 CPU 的 ConvertPirAttribute 报错。"""
    for key in (
        "FLAGS_use_mkldnn",
        "FLAGS_enable_pir_in_executor",
        "FLAGS_use_new_executor",
        "FLAGS_new_ir",
    ):
        os.environ[key] = "0"


def setup_environment() -> None:
    os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(get_cache_dir()))
    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    _disable_onednn()


setup_environment()


def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        # 在 import paddle 之前最后确认环境变量已设置
        _disable_onednn()

        from paddleocr import PaddleOCR

        _ocr_engine = PaddleOCR(lang="ch")
    return _ocr_engine


def extract_text_from_pdf(path: Path) -> str:
    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if text.strip():
                parts.append(text)
    return "\n".join(parts)


def extract_text_from_image(path: Path) -> str:
    ocr = get_ocr_engine()
    result = ocr.ocr(str(path))
    if not result:
        return ""

    lines: list[str] = []
    for item in result:
        rec_texts = item.get("rec_texts") if isinstance(item, dict) else None
        if rec_texts:
            lines.extend(rec_texts)
            continue
        if isinstance(item, list):
            for block in item:
                if isinstance(block, (list, tuple)) and len(block) >= 2:
                    text_info = block[1]
                    if isinstance(text_info, (list, tuple)) and text_info:
                        lines.append(str(text_info[0]))
    return "\n".join(lines)


def ocr_pdf(path: Path, temp_dir: Path) -> str:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(path))
    parts: list[str] = []
    temp_dir.mkdir(parents=True, exist_ok=True)
    try:
        for page_index in range(len(pdf)):
            page = pdf[page_index]
            bitmap = page.render(scale=2)
            pil_image = bitmap.to_pil()
            temp_path = temp_dir / f"page_{page_index}.png"
            try:
                pil_image.save(temp_path)
                parts.append(extract_text_from_image(temp_path))
            finally:
                if temp_path.exists():
                    temp_path.unlink()
    finally:
        pdf.close()
    return "\n".join(parts)


def extract_text(path: Path, temp_dir: Path | None = None) -> str:
    suffix = path.suffix.lower()
    work_dir = temp_dir or (get_cache_dir() / "tmp")
    if suffix == ".pdf":
        text = extract_text_from_pdf(path)
        if text.strip():
            return text
        return ocr_pdf(path, work_dir)
    if suffix in IMAGE_SUFFIXES:
        return extract_text_from_image(path)
    raise ValueError(f"不支持的文件类型: {path.suffix}")


def _clean_amount(raw: str) -> str:
    return raw.replace(",", "").replace("￥", "").replace("¥", "").strip()


def parse_invoice_type(text: str) -> str:
    compact = re.sub(r"\s+", "", text)
    # 按更具体的类型优先匹配，避免“电子发票”被泛化
    patterns = [
        (INVOICE_TYPE_RAILWAY, r"电子发票[（(]铁路电子客票[）)]"),
        (INVOICE_TYPE_SPECIAL, r"电子发票[（(]增值税专用发票[）)]"),
        (INVOICE_TYPE_NORMAL, r"电子发票[（(]普通发票[）)]"),
    ]
    for label, pattern in patterns:
        if re.search(pattern, compact):
            return label

    # OCR 常见残缺写法
    if "铁路电子客票" in compact or "铁路客票" in compact:
        return INVOICE_TYPE_RAILWAY
    if "增值税专用发票" in compact or "专用发票" in compact:
        return INVOICE_TYPE_SPECIAL
    if "普通发票" in compact:
        return INVOICE_TYPE_NORMAL
    return ""


def parse_invoice_number(text: str) -> str:
    match = re.search(r"发票号码[：:\s]*([0-9]{8,})", text)
    if match:
        return match.group(1)
    # 铁路电子客票常见写法
    match = re.search(r"(?:发票号码|票号|电子客票号)[：:\s]*([0-9A-Za-z]{8,})", text)
    return match.group(1) if match else ""


def _normalize_party_name(raw: str) -> str:
    name = raw.strip()
    name = re.split(r"[\n\r]|统一社会信用代码|纳税人识别号|购\s*买|销\s*售", name)[0]
    name = re.sub(r"\s+", "", name)
    name = re.sub(r"^[：:\s]+", "", name)
    return name.strip(" ：:，,;；")


def _collect_party_names(text: str) -> list[str]:
    names = [_normalize_party_name(item) for item in re.findall(r"名称[：:]\s*(.+)", text)]
    return [item for item in names if item]


def parse_seller_name(text: str, invoice_type: str = "") -> str:
    if invoice_type == INVOICE_TYPE_RAILWAY:
        for pattern in (
            r"销售方名称[：:]\s*(.+)",
            r"销\s*名称[：:]\s*(.+?)(?:\s*购|\s*信|\s*统一|\n|$)",
            r"填开单位[：:]\s*(.+)",
            r"开票单位[：:]\s*(.+)",
        ):
            match = re.search(pattern, text)
            if match:
                name = _normalize_party_name(match.group(1))
                if name:
                    return name
        return ""

    # 1) 明确的“销 名称：xxx”（PDF 文本层常见）
    inline_seller = re.search(
        r"销\s*名称[：:]\s*(.+?)(?:\s*购|\s*信|\s*统一社会信用代码|\n|$)",
        text,
        re.S,
    )
    if inline_seller:
        name = _normalize_party_name(inline_seller.group(1))
        if name:
            return name

    # 2) 同一行：购 名称：A  销 名称：B
    inline_pair = re.search(
        r"购\s*名称[：:]\s*(.+?)\s+销\s*名称[：:]\s*(.+?)(?:\s|$)",
        text,
    )
    if inline_pair:
        name = _normalize_party_name(inline_pair.group(2))
        if name:
            return name

    names = _collect_party_names(text)

    # 3) 电子发票常见 OCR 版式：
    #    购买方信息
    #    销售方信息
    #    名称：购买方
    #    名称：销售方
    # 此时必须取“销售方信息”之后的第二个名称，而不是第一个。
    buyer_pos = text.find("购买方信息")
    seller_pos = text.find("销售方信息")
    if buyer_pos != -1 and seller_pos != -1 and len(names) >= 2:
        # 标签都在名称之前（你这张通行费发票就是这种）
        first_name_match = re.search(r"名称[：:]", text)
        if first_name_match and first_name_match.start() > max(buyer_pos, seller_pos):
            return names[1]
        # 标签夹在两个名称之间：名称A ... 销售方信息 ... 名称B
        if seller_pos > buyer_pos:
            after_seller = text[seller_pos:]
            after_names = _collect_party_names(after_seller)
            if after_names:
                # 若销售方信息后仍先出现购买方名称，再取下一个
                if len(after_names) >= 2 and after_names[0] == names[0]:
                    return after_names[1]
                # 销售方信息后的第一个名称，且不是购买方名称
                if after_names[0] != names[0]:
                    return after_names[0]
                if len(after_names) >= 2:
                    return after_names[1]

    # 4) 常规：两个名称时，第二个为销售方
    if len(names) >= 2:
        return names[1]

    return ""


def _extract_amounts_from_text(chunk: str) -> list[str]:
    amounts: list[str] = []
    for match in re.finditer(r"[¥￥]?\s*(\d[\d,]*\.?\d*|\.\d+)", chunk):
        value = _clean_amount(match.group(1))
        if value:
            amounts.append(value)
    return amounts


def parse_total_tax(text: str, invoice_type: str = "") -> str:
    lines_all = [line.strip() for line in text.splitlines() if line.strip()]

    # 铁路电子客票：合计税额按票价处理
    if invoice_type == INVOICE_TYPE_RAILWAY or "铁路电子客票" in re.sub(r"\s+", "", text):
        for pattern in (
            r"票价[：:\s]*[¥￥]?\s*([\d,]+\.?\d*)",
            r"票\s*价[：:\s]*[¥￥]?\s*([\d,]+\.?\d*)",
        ):
            match = re.search(pattern, text)
            if match:
                return _clean_amount(match.group(1))
        return ""

    # 1) 同一行：合 计 ¥金额 ¥税额（放宽空白容忍）
    total_line = re.search(
        r"合\s*计\s*[^\n]*?[¥￥]?\s*(\d[\d,]*\.?\d*|\.\d+)\s*[¥￥]?\s*(\d[\d,]*\.?\d*|\.\d+)",
        text,
    )
    if total_line:
        return _clean_amount(total_line.group(2))

    # 2) "合"或"计"作为独立行：向后2行取第2个值，没有则向前1行取
    for i, line in enumerate(lines_all):
        if "价税合计" in line:
            continue
        if line not in ("合", "计", "合 计") and not re.fullmatch(r"合\s*计", line):
            continue

        # 向后取2行，遇价税合计/大写/小写即停
        backward_chunks = []
        for j in range(i + 1, min(i + 3, len(lines_all))):
            if any(k in lines_all[j] for k in ("价税合计", "大写", "小写")):
                break
            backward_chunks.append(lines_all[j])

        backward_amounts = _extract_amounts_from_text("\n".join(backward_chunks))
        if len(backward_amounts) >= 2:
            return backward_amounts[1]
        if len(backward_amounts) == 1:
            return backward_amounts[0]

        # 向前取1行
        if i > 0:
            forward_amounts = _extract_amounts_from_text(lines_all[i - 1])
            if forward_amounts:
                return forward_amounts[0]

    # 3) 包含"合"的行，跨行"计"字搜索（向后找金额）
    for i, line in enumerate(lines_all):
        if "合" not in line or "价税合计" in line:
            continue

        has_ji = "计" in line
        if not has_ji:
            for j in range(i + 1, min(i + 3, len(lines_all))):
                if "计" in lines_all[j] and "价税合计" not in lines_all[j]:
                    has_ji = True
                    break
        if not has_ji:
            continue

        row_chunks = [line]
        for j in range(i + 1, min(i + 5, len(lines_all))):
            next_line = lines_all[j]
            if any(k in next_line for k in ("价税合计", "大写", "小写")):
                break
            row_chunks.append(next_line)

        amounts = _extract_amounts_from_text("\n".join(row_chunks))
        if len(amounts) >= 2:
            return amounts[-1]
        if len(amounts) == 1:
            return amounts[0]

    # 4) 全文正则："合计"到"价税合计"之间，最多 4 行
    total_section = re.search(
        r"合\s*计([^\n]*(?:\n[^\n]*){0,3})(?:价税合计|$)",
        text,
    )
    if total_section:
        amounts = _extract_amounts_from_text(total_section.group(1))
        if len(amounts) >= 2:
            return amounts[-1]
        if len(amounts) == 1:
            return amounts[0]

    return ""


def parse_invoice(text: str, source_file: str) -> dict[str, str]:
    invoice_type = parse_invoice_type(text)
    return {
        "源文件": source_file,
        "发票类型": invoice_type,
        "销售方名称": parse_seller_name(text, invoice_type),
        "发票号码": parse_invoice_number(text),
        "合计税额": parse_total_tax(text, invoice_type),
    }


def next_output_path(directory: Path) -> Path:
    today = datetime.now().strftime("%Y%m%d")
    sequence = 1
    while True:
        candidate = directory / f"{today}_{sequence:03d}.csv"
        if not candidate.exists():
            return candidate
        sequence += 1


def export_csv(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as fp:
        writer = csv.DictWriter(fp, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def warmup_ocr_engine(on_status: Callable[[str], None] | None = None) -> None:
    if on_status:
        on_status("正在加载识别引擎，首次使用可能需要 30~60 秒…")
    get_ocr_engine()
    if on_status:
        on_status("识别引擎加载完成。")


def process_invoices(
    file_paths: list[Path],
    output_dir: Path,
    on_progress: Callable[[int, int, str], None] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> tuple[list[dict[str, str]], Path]:
    rows: list[dict[str, str]] = []
    total = len(file_paths)
    temp_dir = get_cache_dir() / "tmp"

    needs_ocr = any(path.suffix.lower() in IMAGE_SUFFIXES for path in file_paths)
    if needs_ocr:
        warmup_ocr_engine(on_status)

    for index, file_path in enumerate(file_paths, start=1):
        if on_progress:
            on_progress(index, total, file_path.name)
        text = extract_text(file_path, temp_dir=temp_dir)
        rows.append(parse_invoice(text, file_path.name))

    if on_status:
        on_status("正在生成 CSV 文件…")

    output_path = next_output_path(output_dir)
    export_csv(rows, output_path)
    return rows, output_path
