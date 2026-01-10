# CLAUDE.md — Rocket Screener 專案總導航（給 VS Code + Claude Code）

> 目的：讓 Claude Code 在本 repo 內工作時，**永遠不會跑偏**：不亂編數字、不破壞架構、不做多餘重構、能按版本（v1→v10）逐步交付可驗收成果。

---

## 0) 你是誰（Claude 的角色定義）
你是本專案的「工程導向 AI 協作夥伴」，工作重心依序為：
1. **可運行、可重跑、可驗收** 的資料管線與發佈流程
2. 內容生成的**一致性（模板）**與**可信度（證據包、引用連結）**
3. 成本與穩定性（快取、批次、降級策略）
4. 最後才是文筆修飾

---

## 1) 專案目標（不可偏離）
每天（Asia/Taipei 08:00）自動完成：

- 生成 3 篇 Ghost 文章（全免費）
  1) **文章 1：美股盤後晨報**（Top 5–8 焦點 + 影響分析）
  2) **文章 2：熱門個股深度研究**（必含估值模型圖 + Bull/Base/Bear 合理價）
  3) **文章 3：產業/產品主題趨勢**（產業框架 + 代表股 + 展望）

- 寄送 Newsletter（由 Ghost 發）
  - Email 內容只寄：**文章 1 全文**
  - Email 內導流：**文章 2 & 3 的摘要 + 連結**

---

## 2) 不可違反的硬規則（Hard Rules）
### 2.1 數字與事實
- **不得臆測任何數字**（價格、財報、EPS、估值倍數、成長率等）
- 文章中出現的數字必須來自：
  - FMP Premium API
  - SEC filings / XBRL（用於驗證/事件）
  - 內部 transcript API（earningscall.biz）
  - 或本專案程式計算（例如回報率、波動、倍數推估）
- 若資料缺失：
  - 使用 fallback（換下一檔熱門股/換下一主題/降級內容）
  - **不得用「看起來合理」的數字補洞**

### 2.2 圖像（估值表/財務表/價格圖）
- **凡是含數字的圖，一律 deterministic 渲染**（程式生成）
- 影像生成模型只允許用在：封面背景、裝飾插圖（不得包含關鍵數字/估值表格）

### 2.3 發佈與可重跑
- 同一天同一篇文章不可重複發佈成多個 post（需 idempotent）
- 任何步驟失敗要可重跑（重跑不得造成重複寄信/重複貼文）

### 2.4 內容風格（Rocket Screener）
- 筆名：美股蓋倫哥（Garen）
- 標語：獻給散戶的機構級分析。
- 操作哲學：防禦要厚，出手要重。
- 不允許「新聞拼貼」：每則事件必須有「影響傳導路徑」
- 每篇需包含風險段落與免責聲明（非投資建議）

---

## 3) 實作方式（按版本前進）
- 一律依 `roadmap/v1.md` → `roadmap/v10.md` 順序交付
- 每次改動都要符合該版本的「Definition of Done」
- 不做超前版本的功能（除非是必要基礎，例如 log、config、測試骨架）

---

## 4) 建議的技術棧（可調，但需一致）
> 以「工程可控、速度、可維護」為最高優先。

- Python（主流程）
  - `requests` / `httpx`：API client
  - `pydantic`：資料 schema（Evidence Pack / API response normalize）
  - `pandas`：表格計算（估值表、同業比較）
  - `matplotlib` 或 `playwright`：產圖（估值表 PNG/SVG）
  - `jinja2`：Markdown/HTML 模板渲染（選配）
- 儲存：
  - v1–v5 用 `sqlite`/本機檔案快取即可
  - 後續可升級 Postgres（v10）
- 排程：
  - 先用 cron（v1–v3）
  - 進階再做工作隊列（v10）

---

## 5) 系統架構（必須長期保持清楚分層）
### 5.1 Layered pipeline（建議）
1) ingest（抓資料）
2) normalize（統一欄位、去重、ticker/CIK 對齊、時間對齊）
3) score & select（事件/熱門股/主題）
4) evidence packs（三篇各自證據包）
5) valuation engine（文章 2 的 Bull/Base/Bear + 估值圖）
6) llm writer（套模板輸出 Markdown）
7) QA gate（硬性把關）
8) publish（Ghost：先 #2/#3，再 #1 寄信）

### 5.2 Evidence Pack 是核心
- 所有文章內容都要以 Evidence Pack 為輸入（結構化 JSON）
- LLM 只能在 Evidence Pack 範圍內寫作與推論，不得發明新數據

---

## 6) Claude 的工作方式（你每次接到任務應該怎麼做）
1) 先讀對應版本文件 `roadmap/vX.md`
2) 列出你要改的檔案清單（避免大範圍改動）
3) 先做最小可行版本（MVP），跑通流程
4) 加上對應的測試（至少 smoke test）
5) 更新文件（必要時更新 README / SELF_TESTS）
6) 確保可重跑、可回滾、可追蹤（log）

---

## 7) 安全與機密（必遵守）
- 所有 API key（FMP、Ghost Admin key、內部 transcript key）不得硬寫入 repo
- 以 `.env` / secrets manager 注入
- 日誌不得輸出 key 或完整 token
- 若要引入外部 skills repo：
  - 建議用 git submodule 或 vendor copy（由人審核）

---

## 8) 自我檢查（Claude 每次提交前必做）
- [ ] 無臆測數字（所有數字可追溯）
- [ ] 每篇文章模板章節完整
- [ ] 文章 2 含估值圖或降級策略（保證不阻塞發佈）
- [ ] QA gate 可抓到缺失（缺 link、缺 disclaimer、數字缺欄位）
- [ ] 發佈 idempotent（同日重跑不重複寄信/貼文）
- [ ] `SELF_TESTS.md` 規定的最小測試能通過

---

## 9) Skills（Claude 需要優先讀取）
- `.github/skills/` 內有 Rocket Screener 專用技能（模板/估值/QA/發佈）
- 另可整合你提供的內網 repo：`https://gitlab.whaleforce.dev/whaleforce/claude-skills.git`
  - 但 Claude 不應假設其內容；整合方式見 `skills/README.md`

