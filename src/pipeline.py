"""Pipeline — 主流程编排：下载 → 解析 → 提取 → 存储 → 对比 → 报告."""
import os, sys, json, time, re, warnings
from datetime import datetime
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
from config import COMPANIES, YEARS, FILINGS_DIR
from . import models, sec_downloader, llm_extractor, comparator, reporter


def extract_html_text(filepath):
    """从 SEC 10-K HTML/XML 中提取可读文本，过滤 XBRL 噪声."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        soup = BeautifulSoup(f.read(), "lxml-xml")

    for tag in soup(["script", "style", "nav", "footer", "header", "meta", "link"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    lines = []
    noise_prefixes = ("http://", "https://", "us-gaap:", "msft:", "amzn:",
                      "srt:", "dei:", "invest:", "Country:", "Domain:")
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if any(line.startswith(p) for p in noise_prefixes):
            continue
        if line in ("true", "false") or (line.startswith("P") and re.match(r"^P\d+[YMD]", line)):
            continue
        if "--" in line and len(line) < 20:
            continue
        if line.replace("-", "").replace("/", "").strip().isdigit():
            continue
        lines.append(line)
    return "\n".join(lines)


def run_pipeline(target_years=None, companies_subset=None, skip_download=False, skip_extraction=False):
    """运行完整 pipeline。"""
    if target_years is None:
        target_years = YEARS
    print("=" * 60)
    print("  Enterprise State Tracker Pipeline")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("  目标: " + str(companies_subset or list(COMPANIES.keys())))
    print("  年份: " + str(target_years))
    print("=" * 60)

    # Step 0
    print("\n[Step 0] 初始化数据库")
    models.init_if_needed()

    # Step 1
    if not skip_download:
        print("\n[Step 1] 下载 SEC 10-K 年报")
        manifest = sec_downloader.download_all_filings(target_years)
    else:
        print("\n[Step 1] 跳过下载")
        manifest = sec_downloader.load_manifest()

    if not manifest:
        print("  [FAIL] 无可用申报文件")
        return

    if companies_subset:
        manifest = [m for m in manifest if m["company"] in companies_subset]
    print("  共 %d 份文件待处理" % len(manifest))

    # Step 2
    if not skip_extraction:
        print("\n[Step 2] 解析 + LLM 提取")
        for item in manifest:
            filepath = item["path"]
            company_name = item["company"]
            ticker = item["ticker"]
            year = item["year"]
            print("\n  >> " + company_name + " (" + ticker + ") - " + str(year) + "年")

            if not os.path.exists(filepath):
                print("     [FAIL] 文件不存在: " + filepath)
                continue

            cik = COMPANIES.get(company_name, {}).get("cik", "")
            company_id = models.upsert_company(company_name, ticker, cik)
            filing_id = models.upsert_filing(
                company_id, year, "10-K",
                filing_date=item.get("date", ""),
                source_url=item.get("url", ""),
                file_path=filepath
            )
            if not filing_id:
                print("     [FAIL] 无法创建申报记录")
                continue

            filing = models.get_filing_by_id(filing_id)
            if filing and filing.get("status") == "processed":
                print("     [SKIP] 已处理")
                continue

            ext = os.path.splitext(filepath)[1].lower()
            if ext in (".html", ".htm", ".txt"):
                full_text = extract_html_text(filepath)
                print("     HTML已解析 (%d KB)" % (len(full_text) // 1024))
            elif ext == ".pdf":
                from . import pdf_loader
                full_text, pages, scanned = pdf_loader.extract_full_text(filepath)
                print("     PDF已解析 (%d KB)" % (len(full_text) // 1024))
            else:
                print("     [FAIL] 不支持格式: " + ext)
                continue

            if not full_text.strip():
                print("     [FAIL] 空文本")
                continue

            print("     调用 DeepSeek API...", end=" ")
            sys.stdout.flush()
            try:
                result, error = llm_extractor.extract_enterprise_objects(
                    full_text, company_name, year, item.get("date", "")
                )
                if error:
                    print("[FAIL]")
                    print("     " + error)
                    continue
                models.store_extraction_result(filing_id, result)
                print("[OK]")
                time.sleep(1)
            except Exception as e:
                print("[FAIL] " + str(e))
                continue

    # Step 3
    print("\n[Step 3] 跨年对比分析")
    for company_name, info in COMPANIES.items():
        if companies_subset and company_name not in companies_subset:
            continue
        cik = info.get("cik", "")
        company_id = models.upsert_company(company_name, info["ticker"], cik)
        print("\n  >> " + company_name)
        changes = comparator.compare_years(company_id, target_years)
        if changes:
            comparator.store_changes(changes)
            print("     发现 %d 项变更" % len(changes))
            stats = comparator.get_summary_stats(company_id)
            for ot, ct in stats.items():
                print("     " + ot + ": " + str(dict(ct)))
        else:
            print("     无变更")

    # Step 4
    print("\n[Step 4] 生成报告")
    for company_name, info in COMPANIES.items():
        if companies_subset and company_name not in companies_subset:
            continue
        company_id = models.upsert_company(company_name, info["ticker"])
        md_path, json_path = reporter.generate_reports(
            company_id, company_name, info["ticker"], target_years
        )

    print("\n" + "=" * 60)
    print("  [DONE] Pipeline 完成")
    print("  输出: " + os.path.abspath("output"))
    print("=" * 60)
