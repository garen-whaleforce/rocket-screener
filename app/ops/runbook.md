# Rocket Screener 營運手冊

## 快速開始

### 環境設定

1. 建立虛擬環境：
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
```

2. 安裝相依套件：
```bash
pip install -r requirements.txt
```

3. 設定環境變數（複製 `.env.example` 並填入實際值）：
```bash
cp .env.example .env
# 編輯 .env 填入 API keys
```

### 每日執行

#### Dry Run（測試模式）
```bash
python -m app.run --date 2025-01-10 --dry-run
```
- 輸出到 `out/` 目錄
- 不發佈、不寄信
- 用於檢查文章內容

#### 正式發佈
```bash
python -m app.run --date 2025-01-10 --publish
```
- 發佈到 Ghost
- 文章 1 會寄 newsletter
- 同日重跑不會重複寄信

---

## 環境變數

| 變數 | 必填 | 說明 |
|------|------|------|
| `GHOST_ADMIN_API_URL` | ✅ | Ghost Admin API URL |
| `GHOST_ADMIN_API_KEY` | ✅ | Ghost Admin API Key (格式: id:secret) |
| `NEWSLETTER_SLUG` | ❌ | Newsletter slug (預設: default-newsletter) |
| `EMAIL_SEGMENT` | ❌ | Email segment (預設: status:free) |
| `FMP_API_KEY` | ❌ (v2+) | FMP Premium API Key |
| `TRANSCRIPT_API_URL` | ❌ (v5+) | Transcript API URL |
| `TRANSCRIPT_API_KEY` | ❌ (v5+) | Transcript API Key |
| `OUTPUT_DIR` | ❌ | 輸出目錄 (預設: out) |
| `LOG_LEVEL` | ❌ | 日誌等級 (預設: INFO) |

---

## 排程設定（Cron）

每日台灣時間 08:00 執行：

```cron
# Rocket Screener 每日發佈 (UTC+8 08:00 = UTC 00:00)
0 0 * * * cd /path/to/rocket-screener && /path/to/.venv/bin/python -m app.run --publish >> /var/log/rocket-screener.log 2>&1
```

---

## 故障排除

### 文章重複發佈
- **不會發生**：系統使用 slug 做 idempotent 檢查
- 同 slug 會 update 而非 create

### Newsletter 重複寄出
- **不會發生**：Ghost 會記錄已寄出的 email
- 重跑時會跳過已寄出的 newsletter

### Ghost API 錯誤
1. 檢查 API key 是否正確
2. 檢查 URL 是否正確（含 `/ghost`）
3. 檢查 token 是否過期（自動更新）

### FMP API 錯誤 (v2+)
1. 檢查 API key 是否有效
2. 檢查是否超過 rate limit
3. 降級策略：使用快取資料

---

## 重跑策略

### 部分失敗重跑
```bash
# 只重跑，不會重複已完成的步驟
python -m app.run --date 2025-01-10 --publish
```

### 強制重新生成（不重跑發佈）
```bash
python -m app.run --date 2025-01-10 --dry-run
# 檢查 out/ 內容後再決定是否發佈
```

---

## 日誌位置

- 控制台輸出：即時顯示
- 檔案日誌：`/var/log/rocket-screener.log`（需在 cron 設定）

---

## 版本資訊

- v1: 骨架 + Ghost 發佈
- v2+: 見 `roadmap/` 目錄
