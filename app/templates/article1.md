# {{ title }}

> {{ date_display }} | 美股蓋倫哥

---

## 三行快讀

{{ quick_summary }}

---

## 市場快照

| 指標 | 收盤 | 漲跌 | 漲跌幅 |
|------|------|------|--------|
{% for item in market_snapshot %}
| {{ item.name }} | {{ item.close }} | {{ item.change }} | {{ item.change_pct }} |
{% endfor %}

---

## 今日焦點 Top {{ top_events|length }}

{% for event in top_events %}
### {{ loop.index }}. {{ event.headline }}

**發生什麼事？**
{{ event.what_happened }}

**為何重要？**
{{ event.why_important }}

**可能影響**
{{ event.impact }}

**下一步觀察**
{{ event.next_watch }}

📎 來源：{% for url in event.source_urls %}[{{ loop.index }}]({{ url }}){% if not loop.last %} | {% endif %}{% endfor %}

---

{% endfor %}

## 今晚必看

{% for item in watch_tonight %}
- {{ item }}
{% endfor %}

---

## 風險提示

本文內容僅供參考，不構成任何投資建議。投資有風險，入市需謹慎。過去績效不代表未來表現。

---

*Rocket Screener — 獻給散戶的機構級分析*
