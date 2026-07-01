"""Comparator — 跨年对比引擎，追踪企业状态变化."""
import json
from collections import defaultdict
from . import models


def build_company_object_map(company_id, years=None):
    """构建公司各年份的对象映射，用于对比."""
    conn = models.get_connection()
    cur = conn.cursor()

    if years:
        placeholders = ",".join("?" * len(years))
        query = f"""
            SELECT f.year, eo.object_type, eo.object_id, eo.content,
                   eo.confidence, eo.category, eo.metadata
            FROM enterprise_objects eo
            JOIN filings f ON eo.filing_id = f.id
            WHERE f.company_id = ? AND f.year IN ({placeholders})
            ORDER BY f.year, eo.object_type
        """
        cur.execute(query, [company_id] + list(years))
    else:
        cur.execute("""
            SELECT f.year, eo.object_type, eo.object_id, eo.content,
                   eo.confidence, eo.category, eo.metadata
            FROM enterprise_objects eo
            JOIN filings f ON eo.filing_id = f.id
            WHERE f.company_id = ?
            ORDER BY f.year, eo.object_type
        """, (company_id,))

    # 按年份+类型分组
    by_year = defaultdict(lambda: defaultdict(list))
    for row in cur.fetchall():
        by_year[row["year"]][row["object_type"]].append({
            "object_id": row["object_id"],
            "content": row["content"],
            "confidence": row["confidence"],
            "category": row["category"],
            "metadata": row["metadata"],
        })

    conn.close()
    return dict(by_year)


def build_financials_map(company_id, years=None):
    """构建各年份的财务数据映射."""
    conn = models.get_connection()
    cur = conn.cursor()

    if years:
        placeholders = ",".join("?" * len(years))
        query = f"""
            SELECT f.year, fm.metric_name, fm.value, fm.currency, fm.note
            FROM financial_metrics fm
            JOIN filings f ON fm.filing_id = f.id
            WHERE f.company_id = ? AND f.year IN ({placeholders})
            ORDER BY f.year
        """
        cur.execute(query, [company_id] + list(years))
    else:
        cur.execute("""
            SELECT f.year, fm.metric_name, fm.value, fm.currency, fm.note
            FROM financial_metrics fm
            JOIN filings f ON fm.filing_id = f.id
            WHERE f.company_id = ?
            ORDER BY f.year
        """, (company_id,))

    by_year = defaultdict(dict)
    for row in cur.fetchall():
        by_year[row["year"]][row["metric_name"]] = {
            "value": row["value"],
            "currency": row["currency"],
            "note": row["note"],
        }

    conn.close()
    return dict(by_year)


def compare_objects(objects_old, objects_new):
    """比较两个年份同一类型的企业对象，找出变更。"""
    changes = []

    # Build content lookup for old and new
    old_contents = {item["content"]: item for item in objects_old}
    new_contents = {item["content"]: item for item in objects_new}

    # 新增的（在旧中没有，在新中有）
    for content, item in new_contents.items():
        if content not in old_contents:
            changes.append({
                "change_type": "added",
                "content_before": "",
                "content_after": content,
                "object_id": item.get("object_id", ""),
                "category": item.get("category", ""),
                "confidence": item.get("confidence", "medium"),
            })

    # 移除的（在旧中有，在新中没有）
    for content, item in old_contents.items():
        if content not in new_contents:
            changes.append({
                "change_type": "removed",
                "content_before": content,
                "content_after": "",
                "object_id": item.get("object_id", ""),
                "category": item.get("category", ""),
                "confidence": item.get("confidence", "medium"),
            })

    # 修改的（相同 object_id 不同内容）
    old_by_id = {}
    new_by_id = {}
    for item in objects_old:
        if item.get("object_id"):
            old_by_id[item["object_id"]] = item
    for item in objects_new:
        if item.get("object_id"):
            new_by_id[item["object_id"]] = item

    common_ids = set(old_by_id.keys()) & set(new_by_id.keys())
    for oid in common_ids:
        old_item = old_by_id[oid]
        new_item = new_by_id[oid]
        if old_item["content"] != new_item["content"]:
            changes.append({
                "change_type": "modified",
                "content_before": old_item["content"],
                "content_after": new_item["content"],
                "object_id": oid,
                "category": new_item.get("category", old_item.get("category", "")),
                "confidence": new_item.get("confidence", "medium"),
            })

    return changes


def compare_years(company_id, years):
    """对指定年份序列执行全量对比."""
    sorted_years = sorted(years)
    if len(sorted_years) < 2:
        return []

    obj_map = build_company_object_map(company_id, sorted_years)
    fin_map = build_financials_map(company_id, sorted_years)

    all_changes = []

    # 逐对对比
    for i in range(len(sorted_years) - 1):
        y_old = sorted_years[i]
        y_new = sorted_years[i + 1]

        old_objs = obj_map.get(y_old, {})
        new_objs = obj_map.get(y_new, {})

        all_types = set(list(old_objs.keys()) + list(new_objs.keys()))

        for obj_type in sorted(all_types):
            changes = compare_objects(
                old_objs.get(obj_type, []),
                new_objs.get(obj_type, [])
            )
            for ch in changes:
                all_changes.append({
                    "company_id": company_id,
                    "object_type": obj_type,
                    "year_from": y_old,
                    "year_to": y_new,
                    "change_type": ch["change_type"],
                    "content_before": ch["content_before"],
                    "content_after": ch["content_after"],
                    "significance": _calc_significance(ch, obj_type),
                    "metadata": json.dumps({
                        "object_id": ch.get("object_id", ""),
                        "category": ch.get("category", ""),
                    }, ensure_ascii=False),
                })

    # 财务对比
    for i in range(len(sorted_years) - 1):
        y_old = sorted_years[i]
        y_new = sorted_years[i + 1]

        old_fins = fin_map.get(y_old, {})
        new_fins = fin_map.get(y_new, {})

        for metric in set(list(old_fins.keys()) + list(new_fins.keys())):
            old_val = old_fins.get(metric, {}).get("value")
            new_val = new_fins.get(metric, {}).get("value")
            if old_val is not None and new_val is not None and old_val != new_val:
                pct = ((new_val - old_val) / abs(old_val)) * 100 if old_val != 0 else 0
                all_changes.append({
                    "company_id": company_id,
                    "object_type": "financial",
                    "year_from": y_old,
                    "year_to": y_new,
                    "change_type": "modified",
                    "content_before": f"{metric}: {old_val:,.0f}",
                    "content_after": f"{metric}: {new_val:,.0f} ({pct:+.1f}%)",
                    "significance": "high" if abs(pct) > 20 else "medium" if abs(pct) > 10 else "low",
                    "metadata": json.dumps({"metric": metric, "pct_change": round(pct, 1)},
                                           ensure_ascii=False),
                })

    return all_changes


def _calc_significance(change, obj_type):
    """评估变更重要性."""
    if change["change_type"] == "added":
        return "high"  # 新增通常更重要
    elif change["change_type"] == "removed":
        return "medium"
    elif change["change_type"] == "modified":
        return "medium"
    return "low"


def store_changes(all_changes):
    """存储变更记录到数据库."""
    conn = models.get_connection()
    cur = conn.cursor()

    for ch in all_changes:
        cur.execute("""
            INSERT INTO changes
            (company_id, object_type, year_from, year_to, change_type,
             content_before, content_after, significance, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            ch["company_id"],
            ch["object_type"],
            ch["year_from"],
            ch["year_to"],
            ch["change_type"],
            ch["content_before"],
            ch["content_after"],
            ch["significance"],
            ch["metadata"],
        ))

    conn.commit()
    conn.close()


def get_summary_stats(company_id):
    """获取公司的变更统计摘要."""
    conn = models.get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT object_type, change_type, COUNT(*) as cnt
        FROM changes
        WHERE company_id = ?
        GROUP BY object_type, change_type
        ORDER BY object_type, change_type
    """, (company_id,))

    stats = defaultdict(lambda: defaultdict(int))
    for row in cur.fetchall():
        stats[row["object_type"]][row["change_type"]] = row["cnt"]

    conn.close()
    return dict(stats)


if __name__ == "__main__":
    print("Comparator module loaded. Run via pipeline.")
