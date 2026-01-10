# {{ title }}

> {{ date_display }} | 美股蓋倫哥 | {{ theme }}

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

## 代表股票

| 股票 | 市值 | 核心業務 | 產業鏈位置 | 觀點 |
|------|------|----------|------------|------|
{% for stock in representative_stocks %}
| {{ stock.ticker }} | {{ stock.market_cap }} | {{ stock.business }} | {{ stock.position }} | {{ stock.view }} |
{% endfor %}

---

## 情境展望

### 🐂 Bull Case（樂觀情境）
{{ bull_case }}

### ⚖️ Base Case（基準情境）
{{ base_case }}

### 🐻 Bear Case（悲觀情境）
{{ bear_case }}

---

## 投資策略建議

{{ investment_strategy }}

---

## 關注時點

{% for event in upcoming_events %}
- **{{ event.date }}**：{{ event.description }}
{% endfor %}

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。

---

*Rocket Screener — 獻給散戶的機構級分析*
