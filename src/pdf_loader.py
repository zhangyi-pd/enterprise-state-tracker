"""PDF Loader — 复用 pdf-data-extractor 的 PDF 解析能力."""
# 直接从 pdf-data-extractor 复制核心逻辑，独立为一个模块
import os
import fitz  # PyMuPDF


def load_pdf(filepath):
    """加载 PDF 文件."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"PDF not found: {filepath}")
    return fitz.open(filepath)


def is_scanned(doc, threshold=0.1):
    """检测是否为扫描件（无可提取文本）。"""
    total = sum(len(page.get_text().strip()) for page in doc)
    avg = total / max(len(doc), 1)
    return avg < threshold * 100


def extract_text(doc):
    """提取每页文本及块元信息。"""
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text()
        pages.append({
            "page": i + 1,
            "text": text.strip(),
            "char_count": len(text.strip()),
        })
    return pages


def extract_full_text(filepath):
    """一键提取 PDF 全文。"""
    doc = load_pdf(filepath)
    scanned = is_scanned(doc)
    if scanned:
        print(f"  [WARN] {os.path.basename(filepath)} 是扫描件，建议先用 OCR 处理")
    pages = extract_text(doc)
    doc.close()
    full = "\n".join(p["text"] for p in pages if p.get("text"))
    return full, pages, scanned
