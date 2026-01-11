# V2 Template Field Mapping

本文件說明 v2 模板每個欄位的資料來源，方便 builder 實作。

## 資料來源代碼

- `FMP`: Financial Modeling Prep API
- `FMP_QUOTE`: FMP /quote endpoint
- `FMP_PROFILE`: FMP /profile endpoint
- `FMP_FINANCIALS`: FMP /income-statement, /balance-sheet, /cash-flow
- `FMP_RATIOS`: FMP /ratios, /key-metrics
- `FMP_NEWS`: FMP /stock_news
- `SEC`: SEC EDGAR filings
- `TRANSCRIPT`: earningscall.biz API
- `CALC`: 程式計算
- `LLM`: LLM 生成（基於 Evidence Pack）
- `STATIC`: 靜態配置

---

## Article 1 v2 (晨報)

### 必填欄位 (QA Gate 檢查)

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `market_thesis` | LLM | 基於 market_snapshot + top_events 生成 1-2 句主線 |
| `quick_reads` | LLM | 基於 top_events 前 3 則生成可讀句 |
| `top_events[].price_reaction` | FMP_QUOTE | 取 ticker 的 changesPercentage |
| `quick_hits` | FMP_NEWS | 取 top 15-20 則新聞，LLM 生成摘要 |
| `catalyst_econ` | STATIC | 預設經濟事件日曆 |
| `catalyst_earnings` | FMP | /earning_calendar endpoint |

### 選填欄位

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `market_snapshot[].change_display` | CALC | 指數用 %, 利率用 bps |
| `top_events[].beneficiaries` | LLM | 分析受益股 |
| `top_events[].losers` | LLM | 分析受害股 |
| `top_events[].pricing_path` | LLM | 定價傳導路徑 |
| `top_events[].key_kpis` | LLM | 關鍵 KPI |
| `watchlist` | CALC + LLM | 基於 event + 技術面選股 |

---

## Article 2 v2 (個股深度)

### Tear Sheet 欄位

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `current_price` | FMP_QUOTE | price |
| `after_hours_price` | FMP_QUOTE | 若有 preMarketPrice/postMarketPrice |
| `price_52w_high` | FMP_QUOTE | yearHigh |
| `price_52w_low` | FMP_QUOTE | yearLow |
| `ytd_return` | CALC | (price - yearStartPrice) / yearStartPrice |
| `return_1m`, `return_3m` | CALC | 從歷史價格計算 |
| `beta` | FMP_PROFILE | beta |
| `avg_volume_20d` | CALC | 20 日均量 |
| `market_cap` | FMP_QUOTE | marketCap |
| `enterprise_value` | FMP_RATIOS | enterpriseValue |
| `net_debt_or_cash` | FMP_RATIOS | netDebt (負值=淨現金) |
| `ntm_pe` | FMP_RATIOS | 或 CALC: price / analyst_eps_estimate |
| `ev_sales` | FMP_RATIOS | enterpriseValueMultiple |
| `ev_ebitda` | FMP_RATIOS | evToEbitda |
| `next_earnings_date` | FMP | /earning_calendar |
| `ex_div_date` | FMP_PROFILE | exDividendDate |

### 8 季財務欄位

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `q1_revenue` ~ `q8_revenue` | FMP_FINANCIALS | 最近 8 季營收 |
| `q1_gm` ~ `q8_gm` | CALC | grossProfit / revenue |
| `q1_opm` ~ `q8_opm` | CALC | operatingIncome / revenue |
| `q1_eps` ~ `q8_eps` | FMP_FINANCIALS | eps |
| `ocf_ttm`, `capex_ttm`, `fcf_ttm` | CALC | TTM 加總 |
| `fcf_yield` | CALC | fcf_ttm / market_cap |
| `driver_analysis` | LLM + TRANSCRIPT | 基於財報電話會議解釋變動原因 |

### 估值敏感度欄位

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `eps_row1` ~ `eps_row5` | CALC | NTM EPS ±20% 範圍 |
| `pe_col1` ~ `pe_col5` | CALC | P/E 倍數範圍（歷史 + 同業） |
| `sens_X_Y` | CALC | eps_rowX * pe_colY |
| `current_eps`, `current_pe` | FMP_RATIOS + CALC | 標註當前位置 |

### Bull/Base/Bear 欄位

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `bull_rev_growth`, `base_rev_growth`, `bear_rev_growth` | CALC | 基於歷史 + 同業 |
| `bull_margin`, `base_margin`, `bear_margin` | CALC | 毛利率或營益率假設 |
| `bull_multiple`, `base_multiple`, `bear_multiple` | CALC | 目標倍數 |
| `bull_price`, `base_price`, `bear_price` | CALC | NTM EPS × 倍數 或 DCF |

### 競品矩陣欄位

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `competitors` | STATIC + FMP | 預設同業清單 + 即時數據 |
| `comp.moat` | LLM | 護城河標籤 |

### 管理層訊號欄位

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `latest_earnings_call` | TRANSCRIPT | 最近一季 Q |
| `mgmt_tone` | TRANSCRIPT + LLM | 語氣分析 |
| `mgmt_key_topics` | TRANSCRIPT | top_topics |
| `guidance_change` | TRANSCRIPT + LLM | 指引變化分析 |
| `mgmt_risks` | TRANSCRIPT | risks_mentioned |

---

## Article 3 v2 (產業趨勢)

### 代表股矩陣欄位 (8-12 檔)

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `representative_stocks` | STATIC + FMP | 預設代表股清單 + 即時數據 |
| `stock.return_1d`, `return_1w`, `return_1m`, `return_ytd` | CALC | 從歷史價格計算 |
| `stock.vs_spy` | CALC | return_ytd - spy_ytd |
| `stock.pe`, `stock.ev_sales`, `stock.ev_ebitda` | FMP_RATIOS | 估值倍數 |
| `stock.rev_growth`, `stock.gross_margin` | FMP_FINANCIALS | 財務數據 |
| `stock.kpi1`, `stock.kpi2`, `stock.kpi3` | STATIC + FMP | 產業特定 KPI |
| `stock.position` | STATIC | 產業鏈位置 |
| `stock.view` | LLM | 投資觀點 |

### Profit Pool 欄位

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `profit_pools` | STATIC + FMP | 產業鏈各層毛利結構 |
| `pool.margin_range` | FMP_FINANCIALS | 從代表股推算 |
| `pool.pricing_power` | LLM | 定價權評估 (強/中/弱) |
| `pool.bottleneck` | LLM | 瓶頸程度 (高/中/低) |
| `profit_pool_insight` | LLM | 綜合洞察 |

### 受益順序欄位

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `benefit_pathway` | STATIC + LLM | 傳導路徑描述 |
| `benefit_sequence` | STATIC | 預設受益順序 |
| `step.trigger` | LLM | 觸發條件 |
| `step.timing` | LLM | 預期時間 |

### 情境觸發條件欄位

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `bull_triggers`, `bear_triggers` | LLM | 情境觸發條件 |
| `bull_beneficiaries`, `bear_losers` | LLM | 首要受益/受害股 |
| `base_assumptions` | LLM | 基準情境假設 |

### 關鍵監測指標

| 欄位 | 資料來源 | 說明 |
|------|----------|------|
| `industry_kpis` | STATIC | 產業特定 KPI 清單 |
| `kpi.current` | FMP + 外部來源 | 當前數值 |

---

## 產業特定 KPI 配置

### AI Infra / Semiconductor
- HBM 供給量
- CoWoS 產能利用率
- GPU ASP
- 雲端 Capex 指引

### EV
- 交車量
- 電池成本 $/kWh
- 充電樁利用率
- 鋰價

### Fintech
- TPV (Total Payment Volume)
- Take rate
- Charge-off rate
- ARPU

### Cloud / SaaS
- Cloud 營收成長
- AI 營收貢獻
- 淨留存率 (NRR)
- Gross margin

---

## 實作優先順序

1. **Phase 1**: Tear Sheet + 8Q 財務（FMP 數據）
2. **Phase 2**: 估值敏感度 + Bull/Base/Bear（計算邏輯）
3. **Phase 3**: 代表股矩陣 + Profit Pool（產業配置）
4. **Phase 4**: LLM 增強（Market Thesis、驅動分析）
5. **Phase 5**: 管理層訊號（Transcript 整合）
