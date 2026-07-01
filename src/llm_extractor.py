"""LLM Extractor — 调用 DeepSeek API 从年报中提取结构化企业状态."""
import json
import requests
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, LLM_MODEL


def extract_enterprise_objects(full_text, company_name, filing_year, filing_date=""):
    """从 10-K 文本中提取结构化企业对象."""
    max_chars = 60000
    if len(full_text) > max_chars:
        half = max_chars // 2
        text = full_text[:half] + "\n\n[...truncated...]\n\n" + full_text[-half:]
    else:
        text = full_text

    prompt = """You are an enterprise intelligence analyst. Analyze the following SEC 10-K annual report and extract structured enterprise objects.

For each category below, extract ALL relevant items. Be specific and factual — only extract what is explicitly stated in the text.

## Categories to Extract

### 1. Doctrine (企业信条)
Mission statements, core values, strategic vision.

### 2. Capabilities (核心能力)
Key technologies, products, platforms, competitive advantages.

### 3. Strategy (战略方向)
Strategic initiatives, market expansion, investment priorities.

### 4. Risks (风险因素)
Material risk factors. Categorize as: Market/Competition, Regulatory, Operational, Financial, Technology, Geopolitical.

### 5. Active Obligations (义务与承诺)
Debt, leases, legal contingencies, contractual commitments.

### 6. Management Decisions (管理层决策)
Acquisitions, divestitures, restructuring, partnerships.

### 7. Financial Health (财务健康)
Revenue, Operating Income, Net Income, R&D Spend, Cash, Total Assets, Total Liabilities.

## Output Format

Return a JSON object. Example structure:

{
  "company": "Company Name",
  "filing_year": 2024,
  "enterprise_objects": {
    "doctrine": [
      {"id": "d1", "content": "text here", "confidence": "high", "source_section": "Business"}
    ],
    "capabilities": [
      {"id": "c1", "content": "text here", "confidence": "high", "category": "product"}
    ],
    "strategy": [
      {"id": "s1", "content": "text here", "confidence": "high", "timeframe": "long-term"}
    ],
    "risks": [
      {"id": "r1", "content": "text here", "confidence": "high", "category": "Market"}
    ],
    "obligations": [
      {"id": "o1", "content": "text here", "confidence": "high", "type": "debt"}
    ],
    "management_decisions": [
      {"id": "m1", "content": "text here", "confidence": "high", "type": "acquisition"}
    ],
    "financial_health": {
      "revenue": {"value": 100000000000, "currency": "USD"},
      "operating_income": {"value": null, "currency": "USD"},
      "net_income": {"value": null, "currency": "USD"},
      "rd_spend": {"value": null, "currency": "USD"},
      "cash_and_equivalents": {"value": null, "currency": "USD"},
      "total_assets": {"value": null, "currency": "USD"},
      "total_liabilities": {"value": null, "currency": "USD"}
    }
  },
  "summary": "One paragraph summary."
}

IMPORTANT: Return ONLY valid JSON. No markdown, no explanation, no backticks.

--- BEGIN 10-K TEXT ---
%s
--- END 10-K TEXT ---
""" % text

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": "You are an enterprise intelligence analyst. Extract structured enterprise objects from SEC filings. Output ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 8192,
    }

    headers = {
        "Authorization": "Bearer " + DEEPSEEK_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=180)
        resp.raise_for_status()
        result = resp.json()
        content = result["choices"][0]["message"]["content"].strip()

        if content.startswith("```"):
            lines = content.split("\n", 1)
            if len(lines) > 1:
                content = lines[1]
            content = content.rsplit("```", 1)[0] if "```" in content else content
            content = content.strip()

        parsed = json.loads(content)
        parsed["company"] = company_name
        parsed["filing_year"] = filing_year
        if filing_date:
            parsed["filing_date"] = filing_date
        return parsed, None

    except json.JSONDecodeError as e:
        return None, "JSON parse error: " + str(e)
    except Exception as e:
        return None, "API error: " + str(e)
