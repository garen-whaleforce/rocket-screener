# Rocket Screener（Rocket Screener 營運總戰略）｜v1–v10 實作路線圖（給 VS Code + Claude Code）

本資料夾包含你目前所有討論結論的「可工程化規格」，目標是讓你能在 VS Code + Claude Code 的協助下，**一步步把 Rocket Screener 做成可日更、可重跑、可擴張的內容生產系統**。

---

## 你目前已確定的產品與約束（不再變動的前提）

### 產出頻率與時間
- **每日 3 篇**（文章 1 / 2 / 3）
- 文章生成與推送時間：**台灣時間 08:00（Asia/Taipei）**
- 不做中午補強（transcript 取得足夠即時）

### Newsletter 規格
- **Email 內容 = 文章 1 完整全文**
- Email 內只放 **文章 2 & 3 的摘要 + 連結**（導流回 Ghost）

### Universe（選股池）
- 限定 Universe：**S&P 500 + 大型熱門股 + 主題股 + 科技股 + AI 股**

### 你擁有的資料/工具
- **FMP Premium key**（行情/財務/新聞/估值等）
- **SEC**（filings、XBRL 可做驗證/事件偵測）
- **13F**（季度資料，做 Smart Money/籌碼差異化）
- **Earnings call transcript（內部 API, earningscall.biz）**  
  - 法說後約 **1 小時**內即可取得 transcript（足以支撐 08:00）

### 品牌識別（Brand Identity）
- 筆名：**美股蓋倫哥（Garen）**
- 網站：**Rocket Screener**
- 核心標語：**獻給散戶的機構級分析。**
- 操作哲學：**防禦要厚，出手要重。**
- 文章風格：**硬核分析（Hardcore Analysis）**
- 必備要素（尤其文章 2/3）：
  - **非共識觀點**：講別人沒發現的細節
  - **估值模型**：文章內必有「像 Excel 的估值運算圖」
  - **情境推演**：Bull / Base / Bear 價格區間

---

## 本套文件怎麼用（建議順序）

1. 先讀 `CLAUDE.md`  
   - 這是給 Claude Code 的**總導航**與「硬規則」，避免跑偏、避免亂編數字。

2. 依序做 `roadmap/v1.md` → `roadmap/v10.md`  
   - 每個版本文件都有：目標、工作項、檔案清單、驗收標準（DoD）。

3. 將 `.github/skills/` 內的 skills 放進你的 repo  
   - 這些 skills 是讓 Claude 在開發與寫作時更穩定的「作業標準書」。

4. 依 `SELF_TESTS.md` 建立自動化把關  
   - 先做「硬性 QA Gate」，再談優化文筆與功能。

---

## 目錄結構（本資料夾）
- `CLAUDE.md`：Claude Code 專用導航/規範（最重要）
- `roadmap/v1.md` ~ `roadmap/v10.md`：分版本落地路線圖
- `.github/skills/`：建議的 Claude Skills（可直接放進你的專案）
- `SELF_TESTS.md`：自我測試與 QA Gate 規格（自動化把關）

---

## 推薦的落地節奏（你可以照此排程工作）
- **Week 1：做到 v3**（可日更三篇、可自動發佈、可寄晨報信）
- **Week 2：做到 v5**（估值圖 + transcript 結構化，內容硬核化）
- **Week 3：做到 v7**（SEC + 13F 差異化）
- **Week 4：做到 v9**（QA Gate + 自動測試，進入可長期營運狀態）
- v10 作為營運與擴張（監控、成本、未來會員牆切換）

---

## 注意事項（很重要）
- **數據圖（估值表、價格、財務數字）請務必 deterministic（程式渲染）**  
  影像生成模型可用在封面/背景/插圖，但不要讓生成式模型負責寫數字到圖上。
- 所有數字必須由資料管線提供（FMP/SEC/內部 API），LLM 不得臆測。

