{# Article 2 v2: 個股深度研究（Initiation of Coverage 等級）#}
{# 必填欄位標記：[REQUIRED] 代表 QA Gate 會檢查 #}

> {{ date_display }} | 美股蓋倫哥 | {{ ticker }}

---

## Investment Summary
{# [REQUIRED] 2-3 句話講清楚投資論點 #}

{{ investment_summary }}

---

## Tear Sheet
{# [REQUIRED] 至少 12 個欄位，一頁式全貌 #}

### 價格與動能

| 指標 | 數值 |
|------|------|
| 現價 | ${{ current_price }} |
| 盤後/盤前 | {{ after_hours_price }} |
| 52W 高 | ${{ price_52w_high }} |
| 52W 低 | ${{ price_52w_low }} |
| YTD | {{ ytd_return }} |
| 1M | {{ return_1m }} |
| 3M | {{ return_3m }} |
| Beta | {{ beta }} |
| 20D 均量 | {{ avg_volume_20d }} |

### 估值與規模

| 指標 | 數值 |
|------|------|
| 市值 | {{ market_cap }} |
| 企業價值 (EV) | {{ enterprise_value }} |
| 淨負債/淨現金 | {{ net_debt_or_cash }} |
| NTM P/E | {{ ntm_pe }} |
| EV/Sales | {{ ev_sales }} |
| EV/EBITDA | {{ ev_ebitda }} |

### 關鍵日期

| 事件 | 日期 |
|------|------|
| 下次財報 | {{ next_earnings_date }} |
| 除息日 | {{ ex_div_date }} |

*資料截至：{{ data_timestamp }}*

---

## 公司概覽

{{ company_description }}

**關鍵數據**
- 市值：{{ market_cap }}
- 產業：{{ sector }} / {{ industry }}
- 上市交易所：{{ exchange }}

---

## 基本面分析

### 關鍵 KPI

| 指標 | 數值 | 趨勢 |
|------|------|------|
{% for kpi in key_kpis %}
| {{ kpi.name }} | {{ kpi.value }} | {{ kpi.trend }} |
{% endfor %}

---

## 財務分析（8 季趨勢）
{# [REQUIRED] 至少 6 季數據 #}

### 損益表

| 指標 | {{ q1_label }} | {{ q2_label }} | {{ q3_label }} | {{ q4_label }} | {{ q5_label }} | {{ q6_label }} | {{ q7_label }} | {{ q8_label }} |
|------|-------|-------|-------|-------|-------|-------|-------|-------|
| 營收 | {{ q1_revenue }} | {{ q2_revenue }} | {{ q3_revenue }} | {{ q4_revenue }} | {{ q5_revenue }} | {{ q6_revenue }} | {{ q7_revenue }} | {{ q8_revenue }} |
| YoY% | {{ q1_rev_yoy }} | {{ q2_rev_yoy }} | {{ q3_rev_yoy }} | {{ q4_rev_yoy }} | {{ q5_rev_yoy }} | {{ q6_rev_yoy }} | {{ q7_rev_yoy }} | {{ q8_rev_yoy }} |
| 毛利率 | {{ q1_gm }} | {{ q2_gm }} | {{ q3_gm }} | {{ q4_gm }} | {{ q5_gm }} | {{ q6_gm }} | {{ q7_gm }} | {{ q8_gm }} |
| 營業利益率 | {{ q1_opm }} | {{ q2_opm }} | {{ q3_opm }} | {{ q4_opm }} | {{ q5_opm }} | {{ q6_opm }} | {{ q7_opm }} | {{ q8_opm }} |
| EPS | {{ q1_eps }} | {{ q2_eps }} | {{ q3_eps }} | {{ q4_eps }} | {{ q5_eps }} | {{ q6_eps }} | {{ q7_eps }} | {{ q8_eps }} |

### 現金流與資本支出

| 指標 | TTM | 去年 TTM | YoY |
|------|-----|---------|-----|
| 營業現金流 | {{ ocf_ttm }} | {{ ocf_ttm_prev }} | {{ ocf_yoy }} |
| 資本支出 | {{ capex_ttm }} | {{ capex_ttm_prev }} | {{ capex_yoy }} |
| 自由現金流 | {{ fcf_ttm }} | {{ fcf_ttm_prev }} | {{ fcf_yoy }} |
| FCF Yield | {{ fcf_yield }} | -- | -- |

### 驅動因子拆解（本季 vs 去年同期）
{# 解釋營收/毛利變動原因 #}

{{ driver_analysis }}

---

## 動能分析

*資料截至：{{ price_data_timestamp }}*

- 現價：${{ current_price }}
- 1日變化：{{ price_change_1d }}
- 5日變化：{{ price_change_5d }}
- 1月報酬：{{ price_change_1m }}
- 3月報酬：{{ price_change_3m }}
- 52週高點：${{ price_52w_high }}（距高點 {{ pct_from_high }}）
- 52週低點：${{ price_52w_low }}（距低點 {{ pct_from_low }}）
- Beta：{{ beta }}

---

## 競爭分析
{# [REQUIRED] 至少 3 個競品 #}

### 競品矩陣

| 公司 | 市值 | 營收成長 | 毛利率 | 營益率 | P/E | EV/S | 護城河 |
|------|------|----------|--------|--------|-----|------|--------|
{% for comp in competitors %}
| {{ comp.name }} ({{ comp.ticker }}) | {{ comp.market_cap }} | {{ comp.rev_growth }} | {{ comp.gross_margin }} | {{ comp.op_margin }} | {{ comp.pe }} | {{ comp.ev_sales }} | {{ comp.moat }} |
{% endfor %}

---

## 估值分析
{# [REQUIRED] 必須有 Bull/Base/Bear + 數字假設 #}

### 當前估值

| 指標 | 當前值 | 5Y 平均 | 同業平均 |
|------|--------|---------|----------|
| P/E (TTM) | {{ pe_ttm }} | {{ pe_5y_avg }} | {{ pe_peer_avg }} |
| Forward P/E | {{ forward_pe }} | -- | {{ fwd_pe_peer_avg }} |
| P/S | {{ ps_ratio }} | {{ ps_5y_avg }} | {{ ps_peer_avg }} |
| EV/EBITDA | {{ ev_ebitda }} | {{ ev_ebitda_5y_avg }} | {{ ev_ebitda_peer_avg }} |

### 合理價推估（Bull / Base / Bear）
{# [REQUIRED] 每個情境必須有數字假設 #}

| 情境 | 假設 | NTM 營收成長 | 目標毛利率 | 目標倍數 | 目標價 | 潛在空間 |
|------|------|--------------|------------|----------|--------|----------|
| 🐻 Bear | {{ bear_assumption }} | {{ bear_rev_growth }} | {{ bear_margin }} | {{ bear_multiple }} | ${{ bear_price }} | {{ bear_upside }} |
| ⚖️ Base | {{ base_assumption }} | {{ base_rev_growth }} | {{ base_margin }} | {{ base_multiple }} | ${{ base_price }} | {{ base_upside }} |
| 🐂 Bull | {{ bull_assumption }} | {{ bull_rev_growth }} | {{ bull_margin }} | {{ bull_multiple }} | ${{ bull_price }} | {{ bull_upside }} |

### 估值敏感度表
{# [REQUIRED] EPS × 倍數的 2D 矩陣 #}

**目標價 = NTM EPS × P/E 倍數**

| NTM EPS ↓ / P/E → | {{ pe_col1 }}x | {{ pe_col2 }}x | {{ pe_col3 }}x | {{ pe_col4 }}x | {{ pe_col5 }}x |
|-------------------|-------|-------|-------|-------|-------|
| ${{ eps_row1 }} | ${{ sens_1_1 }} | ${{ sens_1_2 }} | ${{ sens_1_3 }} | ${{ sens_1_4 }} | ${{ sens_1_5 }} |
| ${{ eps_row2 }} | ${{ sens_2_1 }} | ${{ sens_2_2 }} | ${{ sens_2_3 }} | ${{ sens_2_4 }} | ${{ sens_2_5 }} |
| ${{ eps_row3 }} | ${{ sens_3_1 }} | ${{ sens_3_2 }} | ${{ sens_3_3 }} | ${{ sens_3_4 }} | ${{ sens_3_5 }} |
| ${{ eps_row4 }} | ${{ sens_4_1 }} | ${{ sens_4_2 }} | ${{ sens_4_3 }} | ${{ sens_4_4 }} | ${{ sens_4_5 }} |
| ${{ eps_row5 }} | ${{ sens_5_1 }} | ${{ sens_5_2 }} | ${{ sens_5_3 }} | ${{ sens_5_4 }} | ${{ sens_5_5 }} |

*當前位置：EPS ${{ current_eps }}、P/E {{ current_pe }}x*

### 短/中/長期合理價
{# [REQUIRED] 三個時間尺度用不同方法 #}

| 時間框架 | 方法 | 合理價 | 說明 |
|----------|------|--------|------|
| 短期（1-4週） | 技術面 | ${{ short_term_price }} | {{ short_term_rationale }} |
| 中期（3-6月） | NTM EPS × 倍數 | ${{ medium_term_price }} | {{ medium_term_rationale }} |
| 長期（12-24月） | DCF / 長期倍數 | ${{ long_term_price }} | {{ long_term_rationale }} |

---

## 管理層訊號
{# 從 earnings call 提取 #}

**最近財報電話會議**：{{ latest_earnings_call }}

- 管理層語氣：{{ mgmt_tone }}
- 關鍵議題：{{ mgmt_key_topics }}
- 指引變化：{{ guidance_change }}
- 提及風險：{{ mgmt_risks }}

---

## 催化劑與風險

### 潛在催化劑
{% for catalyst in catalysts %}
- {{ catalyst }}
{% endfor %}

### 主要風險
{% for risk in risks %}
- {{ risk }}
{% endfor %}

### What Would Change My Mind
{# 什麼情況下會改變結論 #}
{% for trigger in change_triggers %}
- {{ trigger }}
{% endfor %}

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。作者可能持有或交易本文提及之股票。

---

*Rocket Screener — 獻給散戶的機構級分析*
