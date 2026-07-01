"""SEC Downloader — 从 SEC EDGAR 下载 10-K 年报."""
import os
import sys
import io
# 控制台输出 UTF-8（Windows GBK 兼容）
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import time
import json
import requests
from pathlib import Path
from config import COMPANIES, YEARS, FILINGS_DIR, SEC_HEADERS

# SEC EDGAR API 端点
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

def _cik_url(cik):
    """SEC EDGAR URL 中 CIK 不带前导零."""
    return str(int(cik))

def get_company_submissions(cik):
    """获取公司所有 SEC 提交记录."""
    url = SUBMISSIONS_URL.format(cik=cik)
    resp = requests.get(url, headers=SEC_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()

def find_10k_filings(cik, target_years=None):
    """查找指定年份的 10-K 年报."""
    data = get_company_submissions(cik)
    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    docs = recent.get("primaryDocument", [])
    accession_numbers = recent.get("accessionNumber", [])

    results = []
    cik_url = _cik_url(cik)
    for i, form in enumerate(forms):
        if form != "10-K":
            continue
        year = int(dates[i][:4]) if i < len(dates) else 0
        if target_years and year not in target_years:
            continue
        acc_no = accession_numbers[i].replace("-", "") if i < len(accession_numbers) else ""
        primary_doc = docs[i] if i < len(docs) else ""
        # SEC EDGAR URL 使用不带前导零的 CIK
        html_url = f"https://www.sec.gov/Archives/edgar/data/{cik_url}/{acc_no}/{primary_doc}"
        results.append({
            "year": year,
            "date": dates[i] if i < len(dates) else "",
            "form": form,
            "accession": accession_numbers[i] if i < len(accession_numbers) else "",
            "html_url": html_url,
            "primary_document": primary_doc,
        })
    return results

def download_filing(url, save_path):
    """下载一份申报文件."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    resp = requests.get(url, headers=SEC_HEADERS, timeout=60)
    resp.raise_for_status()
    with open(save_path, "wb") as f:
        f.write(resp.content)
    return save_path

def download_all_filings(target_years=None):
    """下载所有目标公司的 10-K 年报."""
    if target_years is None:
        target_years = YEARS

    manifest = []
    for company_name, info in COMPANIES.items():
        cik = info["cik"]
        ticker = info["ticker"]
        print(f"\n{'='*60}")
        print(f"  {company_name} ({ticker})")
        print(f"{'='*60}")

        filings = find_10k_filings(cik, target_years)
        print(f"  找到 {len(filings)} 份 10-K 年报")

        for f in filings:
            year = f["year"]
            fname = f"{ticker}_{year}_10-K.html"
            save_path = os.path.join(FILINGS_DIR, fname)
            if os.path.exists(save_path):
                size = os.path.getsize(save_path)
                print(f"  [OK] {year} 已存在 ({size//1024} KB)")
            else:
                try:
                    print(f"  [下载] {year} 10-K...", end=" ")
                    download_filing(f["html_url"], save_path)
                    size = os.path.getsize(save_path)
                    print(f"OK ({size//1024} KB)")
                except Exception as e:
                    print(f"失败: {e}")
                    continue

            manifest.append({
                "company": company_name,
                "ticker": ticker,
                "year": year,
                "file": fname,
                "path": save_path,
                "date": f["date"],
                "url": f["html_url"],
            })
            time.sleep(0.5)

    manifest_path = os.path.join(FILINGS_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\n清单已保存: {manifest_path}")
    return manifest

def load_manifest():
    """加载已下载的文件清单."""
    manifest_path = os.path.join(FILINGS_DIR, "manifest.json")
    if os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

if __name__ == "__main__":
    download_all_filings()
