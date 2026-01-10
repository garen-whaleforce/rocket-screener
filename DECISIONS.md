# Rocket Screener｜關鍵決策與技術選型（彙整）

本文件整理目前已確定的產品決策、資料源、模型選型方向與工程原則，作為後續開發一致性依據。

---

## 1) 產品決策
### 日更節奏
- 台灣時間 08:00 自動生成與推送
- 每日三篇文章（1/2/3）
- 不做中午補強（transcript 取得足夠即時）

### Newsletter
- 只寄「文章 1 全文」
- 文章 2、3 只在 email 內提供摘要 + 連結導流

### 會員策略
- 目前全免費（先衝流量、建立信任）
- 未來再把文章 2（或 2+3）轉會員/付費（以 config/feature flag 切換）

---

## 2) 資料源與工具
- FMP Premium：行情/財務/估值/新聞等
- SEC：filings/XBRL（事件偵測 + 數字驗證）
- 13F：季度資料（Smart Money Snapshot）
- Earnings call transcript：內部 API（earningscall.biz），法說後約 1 小時可取得

---

## 3) Universe（選股池）
- S&P 500 constituents
- 大型熱門股
- 主題股
- 科技股
- AI 股

> Universe 要可版本化與可解釋：不要完全交給 LLM 決定。

---

## 4) 估值與合理價推估（核心賣點）
### 原則
- 所有數字 deterministic（資料源或程式計算）
- Bull/Base/Bear 必須對應不同假設
- 文章內必有「估值表圖（像 Excel）」
- 必須輸出 downside（防禦厚度）與 upside（出手價值）

### 三層價格
- 短期（2–4 週）：波動/事件區間
- 中期（3–6 月）：Forward 倍數法（核心）
- 長期（12–24 月）：FCF multiple 或簡化 DCF

---

## 5) 模型選型（原則）
### 文本 LLM（產文/抽取）
- 建議採兩段式：抽取（便宜）→ 寫作（主力）
- LLM 僅用於：
  - 結構化摘要（transcript）
  - 文章敘事與推論（必須基於 Evidence Pack）
- LLM 不得直接產生「硬數字」

### 圖像（封面/視覺）
- 含數字圖（估值表、財務表、價格圖）：一律程式渲染
- 影像生成模型可用於封面背景/插圖，但不得包含關鍵數字/表格

---

## 6) 工程原則（避免營運事故）
- Idempotency：同日重跑不得重複發文/寄信
- QA Gate：缺 link、缺 disclaimer、缺估值區間，一律擋下
- 降級策略：任何單點失敗不得造成 08:00 空窗
- 可追溯：每篇文章記錄資料 hash + prompt/template version（v10）

