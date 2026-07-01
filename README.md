# Enterprise State Tracker 🏢📊

> **追踪企业年报状态的演变 — 不只是摘要，而是维护一个持续演进的企业知识模型**

## 项目背景

大多数文档处理系统只做"一次性摘要"。本项目的目标是构建一个 **持续推理系统**：当你喂入一家公司多年的 SEC 10-K 年报后，系统不是分别输出摘要，而是**维护一个随时间演进的企业状态模型**，告诉你什么是新的、什么变了、什么消失了。

## 核心能力

| 能力 | 说明 |
|------|------|
| 📥 **SEC 自动下载** | 从 EDGAR API 自动获取 10-K 年报 |
| 📄 **PDF/HTML/TXT 解析** | 支持多种格式文档解析 |
| 🤖 **LLM 结构化提取** | 调用 DeepSeek API，提取 7 个维度的企业对象 |
| 🗄️ **持久化存储** | SQLite 存储企业状态快照 |
| 🔄 **跨年对比引擎** | 追踪新增/移除/修改的企业状态 |
| 📊 **报告生成** | Markdown 报告 + JSON 数据导出 |

## 提取的企业维度

- **Doctrine（企业信条）**: 使命、愿景、核心价值观
- **Capabilities（核心能力）**: 技术、产品、平台、专利
- **Strategy（战略方向）**: 战略举措、市场扩张、投资重点
- **Risks（风险因素）**: 市场/监管/运营/财务风险
- **Obligations（义务承诺）**: 债务、租赁、法律纠纷
- **Management Decisions（管理层决策）**: 并购、重组、合作
- **Financial Health（财务健康）**: 营收、利润、资产、负债

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行完整 pipeline（下载 → 提取 → 对比 → 报告）
python run.py

# 3. 仅下载（不调用 LLM，节省 API 费用）
python run.py --download-only

# 4. 仅处理特定公司
python run.py --companies microsoft
python run.py --companies microsoft amazon

# 5. 查看已下载文件
python run.py --show-manifest
```

## 项目结构

```
enterprise-state-tracker/
├── run.py                 # 运行入口
├── config.py              # 配置（API Key、目标公司、年份）
├── requirements.txt       # Python 依赖
├── src/
│   ├── pdf_loader.py      # PDF 解析（复用 pdf-data-extractor）
│   ├── sec_downloader.py  # SEC EDGAR 下载器
│   ├── llm_extractor.py   # DeepSeek 结构化提取
│   ├── models.py          # SQLite 数据模型
│   ├── comparator.py      # 跨年对比引擎
│   ├── reporter.py        # 报告生成
│   └── pipeline.py        # 主流程编排
├── data/
│   ├── filings/           # 下载的 10-K 文件
│   └── enterprise.db      # 状态数据库
└── output/                # 报告输出
```

## 示例输出

运行完成后，`output/` 目录下会生成：
- `msft_enterprise_report.md` — Microsoft 企业状态追踪报告
- `amzn_enterprise_report.md` — Amazon 企业状态追踪报告
- `msft_enterprise_data.json` — 结构化 JSON 数据
- `amzn_enterprise_data.json` — 结构化 JSON 数据

## 技术栈

- **Python 3.10+**: 核心语言
- **PyMuPDF (fitz)**: PDF 解析
- **DeepSeek API**: 结构化信息提取（替代 OpenAI）
- **SQLite**: 本地持久化存储
- **requests**: SEC EDGAR API 通信

## 体系架构

```
SEC EDGAR (10-K)
     ↓ 下载
PDF / HTML / TXT
     ↓ 解析
纯文本
     ↓ DeepSeek API
结构化企业对象 (JSON)
     ↓ 存储
SQLite (企业状态数据库)
     ↓ 对比引擎
跨年变更记录
     ↓ 报告
Markdown 报告 + JSON 导出
```

## 借鉴来源

本项目参考了以下开源项目和文档：
- [pdf-data-extractor](https://github.com/zhangyi-pd/pdf-data-extractor) — PDF 解析模块复用
- SEC EDGAR API 文档
- DeepSeek API 文档

## 许可

MIT
