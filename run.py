"""Enterprise State Tracker — 运行入口."""
import sys
import os

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
from src.pipeline import run_pipeline
from src.sec_downloader import download_all_filings, load_manifest
from config import COMPANIES, YEARS


def main():
    parser = argparse.ArgumentParser(
        description="Enterprise State Tracker — 追踪企业年报状态的演变"
    )
    parser.add_argument("--skip-download", action="store_true",
                        help="跳过下载，使用已有文件")
    parser.add_argument("--skip-extraction", action="store_true",
                        help="跳过 LLM 提取，使用已有数据")
    parser.add_argument("--years", type=int, nargs="+", default=YEARS,
                        help=f"目标年份（默认: {YEARS}）")
    parser.add_argument("--companies", type=str, nargs="+",
                        choices=[k.lower() for k in COMPANIES.keys()],
                        help="目标公司（默认: 全部）")
    parser.add_argument("--download-only", action="store_true",
                        help="仅下载，不处理")
    parser.add_argument("--show-manifest", action="store_true",
                        help="显示已下载文件清单")

    args = parser.parse_args()

    if args.show_manifest:
        manifest = load_manifest()
        if manifest:
            print(f"\n📋 已下载 {len(manifest)} 份申报文件:")
            for item in manifest:
                exists = "✅" if os.path.exists(item.get("path", "")) else "❌"
                print(f"  {exists} {item['company']} {item['year']} — {item.get('file', 'N/A')}")
        else:
            print("暂无已下载的文件。运行 python run.py 下载。")
        return

    if args.download_only:
        download_all_filings(args.years)
        return

    # 公司名字映射
    companies_subset = None
    if args.companies:
        name_map = {k.lower(): k for k in COMPANIES}
        companies_subset = [name_map[c] for c in args.companies]

    # 运行完整 pipeline
    run_pipeline(
        target_years=args.years,
        companies_subset=companies_subset,
        skip_download=args.skip_download,
        skip_extraction=args.skip_extraction,
    )


if __name__ == "__main__":
    main()
