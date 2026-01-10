# {{ title }}

> {{ date_display }} | 美股蓋倫哥 | {{ ticker }}

---

## 公司概覽

{{ company_overview }}

**關鍵數據**
- 市值：{{ market_cap }}
- 產業：{{ sector }} / {{ industry }}
- 上市交易所：{{ exchange }}

---

## 基本面分析

{{ fundamental_analysis }}

### 關鍵 KPI

| 指標 | 數值 | YoY 變化 |
|------|------|----------|
{% for kpi in key_kpis %}
| {{ kpi.name }} | {{ kpi.value }} | {{ kpi.yoy_change }} |
{% endfor %}

---

## 財務面分析

{{ financial_analysis }}

### 財務摘要

| 指標 | 最新季 | 前一季 | YoY |
|------|--------|--------|-----|
{% for item in financials %}
| {{ item.name }} | {{ item.current }} | {{ item.previous }} | {{ item.yoy }} |
{% endfor %}

---

## 動能分析

{{ momentum_analysis }}

| 期間 | 報酬率 | 波動度 |
|------|--------|--------|
{% for item in momentum %}
| {{ item.period }} | {{ item.return }} | {{ item.volatility }} |
{% endfor %}

---

## 競爭分析

{{ competition_analysis }}

### 同業比較

| 公司 | 市值 | P/E | 營收成長 |
|------|------|-----|----------|
{% for comp in competitors %}
| {{ comp.name }} | {{ comp.market_cap }} | {{ comp.pe }} | {{ comp.revenue_growth }} |
{% endfor %}

---

## 估值分析

{{ valuation_analysis }}

### 當前估值

| 指標 | 當前值 | 5年平均 | 產業平均 |
|------|--------|---------|----------|
{% for item in valuation_metrics %}
| {{ item.name }} | {{ item.current }} | {{ item.avg_5y }} | {{ item.industry_avg }} |
{% endfor %}

### 合理價推估

{% if valuation_chart_url %}
![估值模型]({{ valuation_chart_url }})
{% else %}
| 情境 | 假設 | 目標價 | 潛在空間 |
|------|------|--------|----------|
| 🐻 Bear | {{ bear_case.assumption }} | {{ bear_case.target }} | {{ bear_case.upside }} |
| ⚖️ Base | {{ base_case.assumption }} | {{ base_case.target }} | {{ base_case.upside }} |
| 🐂 Bull | {{ bull_case.assumption }} | {{ bull_case.target }} | {{ bull_case.upside }} |
{% endif %}

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

---

## 投資結論

{{ investment_conclusion }}

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。作者可能持有或交易本文提及之股票。

---

*Rocket Screener — 獻給散戶的機構級分析*
