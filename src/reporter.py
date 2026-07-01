"""Reporter — 生成企业状态追踪报告（Markdown + JSON）。"""
import os
import json
from datetime import datetime
from collections import defaultdict
from . import models
from config import OUTPUT_DIR


def generate_company_report(company_id, company_name, ticker, years):
    """生成单个公司的完整状态报告。"""
    conn = models.get_connection()
    cur = conn.cursor()

    # 获取各年份的 filing
    cur.execute("""
        SELECT * FROM filings
        WHERE company_id = ? AND year IN ({})
        ORDER BY year
    """.format(",".join("?" * len(years))), [company_id] + list(years))
    filings = [dict(r) for r in cur.fetchall()]

    # 获取各年份的企业对象
    cur.execute("""
        SELECT f.year, eo.*
        FROM enterprise_objects eo
        JOIN filings f ON eo.filing_id = f.id
        WHERE f.company_id = ? AND f.year IN ({})
        ORDER BY f.year, eo.object_type
    """.format(",".join("?" * len(years))), [company_id] + list(years))
    objects = [dict(r) for r in cur.fetchall()]

    # 获取财务数据
    cur.execute("""
        SELECT f.year, fm.*
        FROM financial_metrics fm
        JOIN filings f ON fm.filing_id = f.id
        WHERE f.company_id = ? AND f.year IN ({})
        ORDER BY f.year
    """.format(",".join("?" * len(years))), [company_id] + list(years))
    financials = [dict(r) for r in cur.fetchall()]

    # 获取变更记录
    cur.execute("""
        SELECT * FROM changes
        WHERE company_id = ?
        ORDER BY year_to, object_type
    """, (company_id,))
    changes = [dict(r) for r in cur.fetchall()]

    conn.close()

    # 按年份组织数据
    by_year = defaultdict(lambda: {"objects": defaultdict(list), "financials": {}})
    for obj in objects:
        by_year[obj["year"]]["objects"][obj["object_type"]].append(obj)
    for fin in financials:
        by_year[fin["year"]]["financials"][fin["metric_name"]] = fin

    # 生成 Markdown
    md = []
    md.append(f"# {company_name} ({ticker}) — 企业状态追踪报告")
    md.append(f"")
    md.append(f"> **报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    md.append(f"> **覆盖年份**: {', '.join(str(y) for y in sorted(years))}")
    md.append(f"")

    # ======== 概览 ========
    md.append("## 📊 概览")
    md.append("")
    md.append("| 指标 | " + " | ".join(str(y) for y in sorted(years)) + " |")
    md.append("|" + " --- |" * (len(years) + 1))

    metrics_order = ["revenue", "net_income", "operating_income", "rd_spend",
                     "cash_and_equivalents", "total_assets", "total_liabilities"]
    metric_labels = {
        "revenue": "营收", "net_income": "净利润", "operating_income": "营业利润",
        "rd_spend": "研发投入", "cash_and_equivalents": "现金及等价物",
        "total_assets": "总资产", "total_liabilities": "总负债",
    }

    for metric in metrics_order:
        row = [metric_labels.get(metric, metric)]
        for y in sorted(years):
            fin = by_year[y]["financials"].get(metric, {})
            val = fin.get("value")
            if val is not None:
                if abs(val) >= 1_000_000_000_000:
                    row.append(f"${val/1_000_000_000_000:.2f}T")
                elif abs(val) >= 1_000_000_000:
                    row.append(f"${val/1_000_000_000:.2f}B")
                elif abs(val) >= 1_000_000:
                    row.append(f"${val/1_000_000:.2f}M")
                else:
                    row.append(f"${val:,.0f}")
            else:
                row.append("—")
        md.append("| " + " | ".join(row) + " |")

    md.append("")

    # ======== 变更摘要 ========
    md.append("## 🔄 关键变更")
    md.append("")

    # 按类型和变更程度分组
    high_changes = [c for c in changes if c["significance"] == "high"]
    if high_changes:
        md.append("### 高重要性变更")
        md.append("")
        for c in high_changes:
            md.append(f"- **{c['object_type']}** ({c['year_from']}→{c['year_to']}): "
                      f"[{c['change_type']}] {c['content_after'][:100]}")
        md.append("")

    # 按类型汇总
    type_labels = {
        "doctrine": "企业信条", "capability": "核心能力", "strategy": "战略方向",
        "risk": "风险因素", "obligation": "义务承诺", "decision": "管理层决策",
        "financial": "财务数据",
    }
    md.append("### 各维度变更数量")
    md.append("")
    md.append("| 维度 | 新增 | 移除 | 修改 |")
    md.append("| --- | ---: | ---: | ---: |")

    change_stats = defaultdict(lambda: defaultdict(int))
    for c in changes:
        change_stats[c["object_type"]][c["change_type"]] += 1

    for obj_type in ["doctrine", "capability", "strategy", "risk", "obligation", "decision", "financial"]:
        stats = change_stats.get(obj_type, {})
        if stats:
            label = type_labels.get(obj_type, obj_type)
            md.append(f"| {label} | {stats.get('added', 0)} | {stats.get('removed', 0)} | {stats.get('modified', 0)} |")

    md.append("")

    # ======== 逐年详细 ========
    for y in sorted(years):
        md.append(f"## 📄 {y} 年状态快照")
        md.append("")

        objs = by_year[y]["objects"]

        for obj_type in ["doctrine", "capability", "strategy", "risk", "obligation", "decision"]:
            items = objs.get(obj_type, [])
            if not items:
                continue
            label = type_labels.get(obj_type, obj_type)
            md.append(f"### {label}")
            md.append("")
            for item in items:
                conf_icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}
                icon = conf_icon.get(item.get("confidence", "medium"), "⚪")
                md.append(f"- {icon} {item['content'][:200]}")
            md.append("")

    # 财务数据表
    fins = by_year[y]["financials"]
    if fins:
        md.append(f"### 财务数据")
        md.append("")
        md.append("| 指标 | 值 |")
        md.append("| --- | --- |")
        for metric in metrics_order:
            fin = fins.get(metric, {})
            val = fin.get("value")
            if val is not None:
                if abs(val) >= 1_000_000_000_000:
                    md.append(f"| {metric_labels.get(metric, metric)} | ${val/1_000_000_000_000:.2f}T |")
                elif abs(val) >= 1_000_000_000:
                    md.append(f"| {metric_labels.get(metric, metric)} | ${val/1_000_000_000:.2f}B |")
                elif abs(val) >= 1_000_000:
                    md.append(f"| {metric_labels.get(metric, metric)} | ${val/1_000_000:.2f}M |")
                else:
                    md.append(f"| {metric_labels.get(metric, metric)} | ${val:,.0f} |")
        md.append("")

    # ======== 轨迹总结 ========
    md.append("## 📈 企业轨迹总结")
    md.append("")

    # 用 LLM 总结？暂时用规则总结
    strategic_shifts = [c for c in changes if c["object_type"] in ("strategy", "doctrine", "decision")]
    if strategic_shifts:
        md.append("### 战略变化")
        md.append("")
        for c in strategic_shifts[:10]:
            md.append(f"- **{c['year_from']}→{c['year_to']}** ({c['object_type']}): "
                      f"{c['content_before'][:80] if c['content_before'] else '(新)'} → "
                      f"{c['content_after'][:80]}")
        md.append("")

    # 风险变化
    risk_changes = [c for c in changes if c["object_type"] == "risk" and c["change_type"] == "added"]
    if risk_changes:
        md.append("### 新出现风险")
        md.append("")
        for c in risk_changes[:5]:
            md.append(f"- **{c['year_to']}**: {c['content_after'][:150]}")
        md.append("")

    md.append("---")
    md.append(f"*由 Enterprise State Tracker 自动生成 | {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return "\n".join(md)


def export_json(company_id, years):
    """导出结构化 JSON 数据。"""
    conn = models.get_connection()
    cur = conn.cursor()

    cur.execute("SELECT * FROM companies WHERE id = ?", (company_id,))
    company = dict(cur.fetchone())

    # 获取所有数据
    cur.execute("""
        SELECT f.*, eo.*
        FROM enterprise_objects eo
        JOIN filings f ON eo.filing_id = f.id
        WHERE f.company_id = ? AND f.year IN ({})
        ORDER BY f.year, eo.object_type
    """.format(",".join("?" * len(years))), [company_id] + list(years))
    objects = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT f.year, fm.*
        FROM financial_metrics fm
        JOIN filings f ON fm.filing_id = f.id
        WHERE f.company_id = ? AND f.year IN ({})
        ORDER BY f.year
    """.format(",".join("?" * len(years))), [company_id] + list(years))
    financials = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT * FROM changes
        WHERE company_id = ?
        ORDER BY year_to, object_type
    """, (company_id,))
    changes = [dict(r) for r in cur.fetchall()]

    conn.close()

    # 序列化（Row → dict 转换）
    def serialize(obj):
        if isinstance(obj, dict):
            return {k: serialize(v) for k, v in obj.items()}
        elif hasattr(obj, "keys"):  # sqlite3.Row
            return {k: serialize(obj[k]) for k in obj.keys()}
        else:
            return obj

    data = {
        "report_metadata": {
            "generated_at": datetime.now().isoformat(),
            "company": serialize(company),
            "years": sorted(years),
        },
        "objects": [serialize(o) for o in objects],
        "financials": [serialize(f) for f in financials],
        "changes": [serialize(c) for c in changes],
    }

    return data


def generate_reports(company_id, company_name, ticker, years):
    """生成完整报告集。"""
    os.makedirs(str(OUTPUT_DIR), exist_ok=True)

    # Markdown 报告
    md = generate_company_report(company_id, company_name, ticker, years)
    md_path = OUTPUT_DIR / f"{ticker.lower()}_enterprise_report.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"  📝 Markdown 报告: {md_path}")

    # JSON 导出
    data = export_json(company_id, years)
    json_path = OUTPUT_DIR / f"{ticker.lower()}_enterprise_data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    print(f"  📊 JSON 数据: {json_path}")

    return str(md_path), str(json_path)


if __name__ == "__main__":
    print("Reporter module loaded.")
