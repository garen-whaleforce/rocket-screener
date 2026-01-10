# Rocket Screener Skills

本目錄包含 Rocket Screener 專案專用的 Claude Skills。

## 目錄結構

```
.github/skills/
├── README.md                    # 本文件
├── rocket-screener/             # 專案專用 skills
│   ├── brand-voice/             # 品牌語氣與寫作風格
│   ├── article-templates/       # 三篇文章模板規範
│   ├── valuation-engine/        # 估值引擎與出圖規範
│   ├── news-selection/          # 新聞挑選與事件打分
│   ├── ghost-publish/           # Ghost 發佈規範
│   ├── qa-gate/                 # QA 把關規則
│   └── ops-runbook/             # 營運手冊
└── _whaleforce/                 # (Optional) 內網共用 skills submodule
```

## 整合內網 skills repo

如果你要整合 whaleforce 內網 skills：

```bash
# 方式 1：Git submodule（推薦）
git submodule add https://gitlab.whaleforce.dev/whaleforce/claude-skills.git .github/skills/_whaleforce

# 方式 2：已複製到 ~/.claude/skills（你目前的方式）
# Claude Code 會自動讀取 ~/.claude/skills 內的所有 skills
```

## 優先順序

Claude Code 讀取 skills 時的優先順序：
1. 專案內 `.github/skills/rocket-screener/` — 專案專用，最高優先
2. 專案內 `.github/skills/_whaleforce/` — 內網共用
3. 用戶目錄 `~/.claude/skills/` — 全局共用

## 現有可用的 whaleforce skills

你的 `~/.claude/skills/` 已包含：
- `earningcall-api` — 財報電話會議 transcript API
- `sec-filings` — SEC 10-K/10-Q/13F 查詢
- `postgres-database` — 股價/財報資料庫
- `backtester-api` — 回測服務
- `performance-metrics` — Sharpe/報酬率計算
- `neo4j-knowledge-graph` — 知識圖譜查詢

這些都可以直接在 Rocket Screener 開發過程中使用。
