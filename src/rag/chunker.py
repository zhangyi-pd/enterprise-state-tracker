"""Chunker — 将文档分割为可检索的块，保留元数据。"""
import os
import re
from typing import List, Dict, Any


def chunk_text(text: str, source: str, chunk_size: int = 1500, overlap: int = 200) -> List[Dict[str, Any]]:
    """将文本分割为重叠块。超长段落也会被切分。"""
    chunks = []
    paragraphs = re.split(r"\n\s*\n", text)
    current_chunk = ""
    chunk_id = 0
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        
        # 处理超长段落（大于 chunk_size）
        if len(para) > chunk_size:
            # 先把当前累积的 chunk 保存
            if current_chunk:
                chunks.append({
                    "id": source + "_chunk_" + str(chunk_id),
                    "text": current_chunk.strip(),
                    "source": source,
                    "char_count": len(current_chunk),
                    "chunk_index": chunk_id,
                })
                chunk_id += 1
                current_chunk = ""
            
            # 按句子切分超长段落
            sentences = re.split(r"(?<=[.!?])\s+", para)
            temp = ""
            for sent in sentences:
                if len(temp) + len(sent) > chunk_size and temp:
                    chunks.append({
                        "id": source + "_chunk_" + str(chunk_id),
                        "text": temp.strip(),
                        "source": source,
                        "char_count": len(temp),
                        "chunk_index": chunk_id,
                    })
                    chunk_id += 1
                    temp = sent
                else:
                    temp = (temp + " " + sent) if temp else sent
            if temp.strip():
                current_chunk = temp
            continue
        
        # 正常段落
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append({
                "id": source + "_chunk_" + str(chunk_id),
                "text": current_chunk.strip(),
                "source": source,
                "char_count": len(current_chunk),
                "chunk_index": chunk_id,
            })
            chunk_id += 1
            if overlap > 0 and len(current_chunk) > overlap:
                current_chunk = current_chunk[-overlap:] + "\n" + para
            else:
                current_chunk = para
        else:
            current_chunk = (current_chunk + "\n" + para) if current_chunk else para
    
    if current_chunk.strip():
        chunks.append({
            "id": source + "_chunk_" + str(chunk_id),
            "text": current_chunk.strip(),
            "source": source,
            "char_count": len(current_chunk),
            "chunk_index": chunk_id,
        })
    return chunks


def chunk_html_file(filepath: str, chunk_size: int = 1500, overlap: int = 200) -> List[Dict[str, Any]]:
    """从 HTML 申报文件读取并分块。"""
    import warnings
    from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
    warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
    
    filename = os.path.basename(filepath)
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "lxml-xml")
    
    for tag in soup(["script", "style", "nav", "footer", "header", "meta", "link"]):
        tag.decompose()
    
    text = soup.get_text(separator="\n")
    noise = ("http://", "https://", "us-gaap:", "msft:", "amzn:", "srt:", "dei:", "invest:")
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if not line or any(line.startswith(p) for p in noise):
            continue
        if line in ("true", "false") or (line.startswith("P") and re.match(r"^P\d+[YMD]", line)):
            continue
        lines.append(line)
    
    return chunk_text("\n".join(lines), filename, chunk_size, overlap)


def chunk_all_filings(filings_dir: str) -> List[Dict[str, Any]]:
    """对目录下所有 HTML 申报文件分块。"""
    import glob
    all_chunks = []
    for fp in sorted(glob.glob(os.path.join(filings_dir, "*.html"))):
        print("  分块: " + os.path.basename(fp), end="")
        chunks = chunk_html_file(fp)
        print(" -> " + str(len(chunks)) + " 个块")
        all_chunks.extend(chunks)
    return all_chunks
