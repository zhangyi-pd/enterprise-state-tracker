import os
from pathlib import Path

# 项目根目录
ROOT = Path(__file__).parent

# DeepSeek API — 通过环境变量设定
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
LLM_MODEL = "deepseek-chat"

# 数据目录
DATA_DIR = ROOT / "data"
FILINGS_DIR = DATA_DIR / "filings"
DB_PATH = DATA_DIR / "enterprise.db"
OUTPUT_DIR = ROOT / "output"

# 目标公司
COMPANIES = {
    "Microsoft": {"cik": "0000789019", "ticker": "MSFT"},
    "Amazon": {"cik": "0001018724", "ticker": "AMZN"},
}

# 目标年份
YEARS = [2023, 2024, 2025]

# SEC 请求头
SEC_HEADERS = {
    "User-Agent": "EnterpriseStateTracker/1.0 (798583170@qq.com)",
    "Accept": "text/html,application/json",
}
