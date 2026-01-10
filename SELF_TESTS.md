# SELF_TESTS.md — Rocket Screener 自我測試與發佈前把關（QA Gate）

本文件定義「發佈前必過的把關」與「最低自動測試集合」。目標是：
- 防止亂編數字、缺來源、模板破壞、重複寄信等營運事故
- 讓每日 08:00 任務失敗時能快速定位原因並重跑

---

## 1) 發佈前 QA Gate（Hard Fail）
> 任何一條不符合：**不得發佈、不得寄信**。

### 1.1 全局（所有文章通用）
- [ ] `date` 與文章標題/slug 一致（例如 `YYYY/MM/DD`、`YYYYMMDD`）
- [ ] 文章包含固定免責聲明（全文一致，可用 checksum 驗）
- [ ] Markdown 結構合法（至少：有 H1）
- [ ] 文章內所有 URL 為合法格式（`http://` 或 `https://`）

### 1.2 文章 1（盤後晨報）
- [ ] Top events 數量 **5–8**
- [ ] 每則事件至少 **1 個來源連結**
- [ ] 有「市場快照」區塊且包含：
  - 指數（至少 SPX/NDX/DJI 任一）
  - 10Y / DXY / Oil / Gold / BTC（可依資料可得性微調，但要固定欄位）
- [ ] 有「今晚必看」或「下一步觀察」段落

### 1.3 文章 2（熱門個股深度）
- [ ] 必有章節：公司概覽 / 基本面 / 財務面 / 動能 / 競爭 / 估值 / 催化與風險
- [ ] 必有 Bull/Base/Bear 價格區間（至少中期 3–6m）
- [ ] 估值圖：
  - [ ] 有 PNG 圖 URL 且成功上傳（優先）
  - 或（fallback）Markdown 表格存在且不為空
- [ ] 不允許出現「具體數字」卻無來源欄位（Evidence Pack 需有對應 key）

### 1.4 文章 3（產業/主題）
- [ ] 必有：驅動因子（至少 3 點）、產業鏈/供應鏈框架、代表股表格（≥3 檔）
- [ ] 必有：展望情境（Base/Bull/Bear 或等價三情境）
- [ ] 若有產業鏈圖：圖 URL 必存在；若無，必有 fallback（更完整表格）

### 1.5 發佈與寄信（Ghost）
- [ ] 同日重跑必須 update 同一 slug，而不是 create 新 post（idempotent）
- [ ] 只有文章 1 publish 時帶 `newsletter`（寄信）
- [ ] 文章 2/3 publish 不得帶 `newsletter`（避免誤寄）

---

## 2) 自動測試（最低集合）
> 建議用 `pytest`；CI 先做 smoke + unit，後續再做 integration。

### 2.1 Unit tests（必做）
- scoring：
  - event_scoring 在固定輸入下輸出穩定（分數排序不抖動）
  - hot_stock_scoring 在固定輸入下可重現
- dedupe：
  - 相同 URL/相似標題合併規則正確
- valuation engine：
  - 在固定 inputs 下輸出 Bull/Base/Bear 價格區間符合公式
  - downside/upside 計算正確

### 2.2 Snapshot tests（必做）
- 文章 1/2/3 的 Markdown 輸出：
  - H1 存在
  - 固定章節標題存在（避免模板被改壞）
  - 免責聲明存在

### 2.3 Integration smoke（建議）
- `--dry-run`：
  - 能產出 3 篇文章到 `out/`
  - 能產出 `qa_report.json` / `qa_report.md`
- `--publish`（staging 環境）：
  - 能建立/更新 3 篇文章
  - 同日重跑不新增重複 post
  - 只有文章 1 寄信（staging 可用測試 segment）

---

## 3) QA 報告格式（建議）
輸出 `qa_report.json`（機器可讀）與 `qa_report.md`（人類可讀）。

### JSON（示意）
```json
{
  "date": "YYYY-MM-DD",
  "status": "pass|fail",
  "errors": [{"code": "A1_NO_LINK", "message": "Event #3 missing source url"}],
  "warnings": [{"code": "SEC_MISMATCH", "message": "Revenue differs from SEC by 2.1%"}],
  "artifacts": {
    "article1_path": "out/article1.md",
    "article2_valuation_png": "out/valuation.png"
  }
}
```

---

## 4) 常見營運事故與對策（務必內建）
- **transcript 未到**：文章 2 改用上一季財報 + 既有資料（但不要亂寫管理層語句）
- **估值圖生成失敗**：降級 Markdown 表格（不阻塞發佈）
- **FMP 失敗**：只用市場快照 + 已有快取事件，並在 log 記錄
- **Ghost 發佈失敗**：不得寄信；保留 out/ 文章與 qa_report 供重跑

---

## 5) 推薦的日常作業（你每天只要做這些）
- 看 `qa_report.md` 是否 PASS
- 抽查：
  - 文章 1 任一事件連結是否可開
  - 文章 2 估值圖是否對齊當天數字
- 若 FAIL：只重跑失敗步驟（不要全系統重跑）

