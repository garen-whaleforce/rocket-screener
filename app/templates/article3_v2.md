{# Article 3 v2: 產業趨勢深度研究（Sector Research 等級）#}
{# 必填欄位標記：[REQUIRED] 代表 QA Gate 會檢查 #}

> {{ date_display }} | 美股蓋倫哥 | {{ theme_display }}

---

## Investment Thesis
{# [REQUIRED] 2-3 句話講清楚產業投資主線 #}

{{ investment_thesis }}

---

## 為何現在關注？

{{ why_now }}

---

## 驅動因子

{% for driver in drivers %}
### {{ loop.index }}. {{ driver.title }}

{{ driver.description }}

{% endfor %}

---

## 產業鏈 / 供應鏈框架

{{ supply_chain_overview }}

{% if supply_chain_chart_url %}
![產業鏈圖]({{ supply_chain_chart_url }})
{% else %}
### 產業鏈結構

| 位置 | 環節 | 代表公司 | 說明 |
|------|------|----------|------|
{% for layer in supply_chain %}
| {{ layer.position }} | {{ layer.segment }} | {{ layer.companies }} | {{ layer.notes }} |
{% endfor %}
{% endif %}

---

## Profit Pool 分析
{# [REQUIRED] 哪一層毛利最高、誰有定價權 #}

### 毛利分布

| 產業鏈位置 | 毛利率區間 | 定價權 | 瓶頸程度 | 代表公司 |
|------------|------------|--------|----------|----------|
{% for pool in profit_pools %}
| {{ pool.position }} | {{ pool.margin_range }} | {{ pool.pricing_power }} | {{ pool.bottleneck }} | {{ pool.companies }} |
{% endfor %}

### 關鍵洞察

{{ profit_pool_insight }}

---

## 受益順序（Who Benefits First）
{# [REQUIRED] 資金/需求的傳導路徑 #}

### 傳導路徑

{{ benefit_pathway }}

### 受益時序

| 順序 | 環節 | 受益股 | 觸發條件 | 預期時間 |
|------|------|--------|----------|----------|
{% for step in benefit_sequence %}
| {{ loop.index }} | {{ step.segment }} | {{ step.tickers }} | {{ step.trigger }} | {{ step.timing }} |
{% endfor %}

---

## Industry Dashboard（代表股矩陣）
{# [REQUIRED] 至少 8 檔代表股 #}

*資料截至：{{ market_cap_timestamp }}*

### 代表股表現

| 股票 | 市值 | 1D | 1W | 1M | YTD | vs SPY |
|------|------|----|----|----|----|--------|
{% for stock in representative_stocks %}
| {{ stock.ticker }} | {{ stock.market_cap }} | {{ stock.return_1d }} | {{ stock.return_1w }} | {{ stock.return_1m }} | {{ stock.return_ytd }} | {{ stock.vs_spy }} |
{% endfor %}

### 估值比較

| 股票 | P/E | EV/S | EV/EBITDA | 營收成長 | 毛利率 |
|------|-----|------|-----------|----------|--------|
{% for stock in representative_stocks %}
| {{ stock.ticker }} | {{ stock.pe }} | {{ stock.ev_sales }} | {{ stock.ev_ebitda }} | {{ stock.rev_growth }} | {{ stock.gross_margin }} |
{% endfor %}

### 產業特定 KPI

| 股票 | {{ kpi1_name }} | {{ kpi2_name }} | {{ kpi3_name }} | 產業鏈位置 | 投資觀點 |
|------|-----------------|-----------------|-----------------|------------|----------|
{% for stock in representative_stocks %}
| {{ stock.ticker }} | {{ stock.kpi1 }} | {{ stock.kpi2 }} | {{ stock.kpi3 }} | {{ stock.position }} | {{ stock.view }} |
{% endfor %}

---

## 情境展望
{# [REQUIRED] 每個情境必須有觸發條件 #}

### 🐂 Bull Case（樂觀情境）

**情境描述**
{{ bull_case }}

**觸發條件**
{% for trigger in bull_triggers %}
- {{ trigger }}
{% endfor %}

**首要受益股**
{{ bull_beneficiaries }}

---

### ⚖️ Base Case（基準情境）

**情境描述**
{{ base_case }}

**假設條件**
{% for assumption in base_assumptions %}
- {{ assumption }}
{% endfor %}

---

### 🐻 Bear Case（悲觀情境）

**情境描述**
{{ bear_case }}

**觸發條件**
{% for trigger in bear_triggers %}
- {{ trigger }}
{% endfor %}

**首要受害股**
{{ bear_losers }}

---

## 投資策略建議

{{ investment_strategy }}

### 建議配置

| 風格 | 建議標的 | 理由 |
|------|----------|------|
| 穩健型 | {{ conservative_picks }} | {{ conservative_rationale }} |
| 成長型 | {{ growth_picks }} | {{ growth_rationale }} |
| 積極型 | {{ aggressive_picks }} | {{ aggressive_rationale }} |

---

## 關鍵監測指標
{# 投資人應該追蹤的 KPI #}

### 產業 KPI

{% for kpi in industry_kpis %}
- **{{ kpi.name }}**：{{ kpi.description }}（目前：{{ kpi.current }}）
{% endfor %}

### 關注時點

{% for event in upcoming_events %}
- **{{ event.date }}**：{{ event.description }}
{% endfor %}

---

## What Would Change My Mind
{# 什麼情況下會改變產業觀點 #}

### 上調觀點條件
{% for condition in upgrade_conditions %}
- {{ condition }}
{% endfor %}

### 下調觀點條件
{% for condition in downgrade_conditions %}
- {{ condition }}
{% endfor %}

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。

---

*Rocket Screener — 獻給散戶的機構級分析*
