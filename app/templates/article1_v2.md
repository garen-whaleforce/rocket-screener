{# Article 1 v2: 美股盤後晨報（研究報告級）#}
{# 必填欄位標記：[REQUIRED] 代表 QA Gate 會檢查 #}

> {{ date_display }} | 美股蓋倫哥

---

## Market Thesis
{# [REQUIRED] 1-2 句話講今天市場主線 #}

{{ market_thesis }}

---

## 三行快讀
{# [REQUIRED] 格式：【動詞+結果】+（Ticker）+ 一個數字 #}

{% for item in quick_reads %}
- {{ item }}
{% endfor %}

---

## 市場快照

| 指標 | 收盤 | 變化 |
|------|------|------|
{% for item in market_snapshot %}
| {{ item.name }} | {{ item.close }} | {{ item.change_display }} |
{% endfor %}

*資料截至：{{ market_data_timestamp }}*

---

## 今日焦點 Top {{ top_events|length }}

{% for event in top_events %}
### {{ loop.index }}. {{ event.headline }}

**發生什麼事？**
{{ event.what_happened }}

{% if event.price_reaction %}
**市場反應**
{{ event.price_reaction }}
{% endif %}

**為何重要？**
{{ event.why_important }}

{% if event.impact_card %}
**Impact Card**
- 受益：{{ event.impact_card.beneficiaries or "待分析" }}
- 受害：{{ event.impact_card.losers or "暫無明顯受害者" }}
- 定價路徑：{{ event.impact_card.pricing_path or "待分析" }}
- 關鍵 KPI：{{ event.impact_card.key_kpis or "待分析" }}
{% endif %}

**下一步觀察**
{{ event.next_watch }}

📎 來源：{% for url in event.source_urls %}[{{ loop.index }}]({{ url }}){% if not loop.last %} | {% endif %}{% endfor %}

---

{% endfor %}

## Quick Hits
{# [REQUIRED] 至少 10 則，每則 1 行 #}

{% for hit in quick_hits %}
- {{ hit.summary }}（{{ hit.ticker }}{% if hit.change %} | {{ hit.change }}{% endif %}）
{% endfor %}

---

## Catalyst Calendar（今晚/明天事件）
{# [REQUIRED] 至少列出 3 個事件 #}

### 經濟數據
{% for item in catalyst_econ %}
- **{{ item.time }}**：{{ item.event }}
{% endfor %}

### 財報發布
{% for item in catalyst_earnings %}
- **{{ item.timing }}**：{{ item.event }}{% if item.ticker %}（{{ item.ticker }}）{% endif %}
{% endfor %}

### 其他事件
{% for item in catalyst_other %}
- **{{ item.time }}**：{{ item.event }}
{% endfor %}

---

## Rocket Watchlist
{# 3-7 檔值得今天盯的股票 #}

{% for stock in watchlist %}
### {{ stock.ticker }}
- 為什麼盯：{{ stock.reason }}
- 關鍵價位：{{ stock.key_levels }}
{% if stock.event_time %}- 事件時間：{{ stock.event_time }}{% endif %}

{% endfor %}

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。

---

*Rocket Screener — 獻給散戶的機構級分析*
