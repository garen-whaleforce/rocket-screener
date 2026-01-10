# Rocket Screener 部署指南

## v10 部署配置

每日 08:00 台灣時間自動執行，生成並發佈 3 篇股市分析文章到 Ghost。

---

## 1. 環境變數配置

複製並編輯 `.env` 文件：

```bash
cp .env.example .env
```

必要變數：

| 變數 | 用途 | 範例 |
|------|------|------|
| `GHOST_ADMIN_URL` | Ghost 後台 URL | `https://yoursite.ghost.io` |
| `GHOST_ADMIN_API_KEY` | Ghost Admin API Key | `66...` |
| `FMP_API_KEY` | Financial Modeling Prep API | `abc123` |
| `LITELLM_API_URL` | LiteLLM Proxy URL | `https://litellm.whaleforce.dev` |
| `LITELLM_API_KEY` | LiteLLM API Key | `sk-xxx` |

可選變數：

| 變數 | 用途 | 預設 |
|------|------|------|
| `SLACK_WEBHOOK_URL` | 失敗告警 | - |
| `ALERT_EMAIL` | 告警郵件 | - |
| `ALERT_ON_SUCCESS` | 成功也發通知 | `false` |
| `TRANSCRIPT_API_URL` | 財報電話會議 API | `https://earningcall.gpu5090.whaleforce.dev` |

---

## 2. 部署方式

### 方式一：Docker Compose (推薦)

```bash
# 建置並啟動
docker-compose up -d

# 查看日誌
docker-compose logs -f rocket-screener

# 啟動含 cron 定時服務
docker-compose --profile cron up -d
```

### 方式二：系統 Cron

```bash
# 執行設定腳本
chmod +x scripts/setup_cron.sh
./scripts/setup_cron.sh

# 驗證 cron
crontab -l
```

### 方式三：手動執行

```bash
# 執行當日流程
python -m app.run

# 指定日期
python -m app.run 2025-01-15
```

---

## 3. 定時執行配置

| 平台 | 設定 |
|------|------|
| **Docker cron** | 內建於 docker-compose.yml cron service |
| **Linux cron** | `0 0 * * 1-5` (UTC) = 08:00 台灣 |
| **macOS cron** | 同上，使用 setup_cron.sh |
| **GitHub Actions** | 見下方配置 |

### GitHub Actions 範例

```yaml
name: Daily Newsletter
on:
  schedule:
    - cron: '0 0 * * 1-5'  # 08:00 Taiwan (UTC+8)
  workflow_dispatch:

jobs:
  run:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m app.run
        env:
          GHOST_ADMIN_URL: ${{ secrets.GHOST_ADMIN_URL }}
          GHOST_ADMIN_API_KEY: ${{ secrets.GHOST_ADMIN_API_KEY }}
          FMP_API_KEY: ${{ secrets.FMP_API_KEY }}
          LITELLM_API_URL: ${{ secrets.LITELLM_API_URL }}
          LITELLM_API_KEY: ${{ secrets.LITELLM_API_KEY }}
```

---

## 4. 監控與告警

### Slack 告警

設定 `SLACK_WEBHOOK_URL` 後，以下情況會收到通知：

- Pipeline 執行失敗
- QA Gate 未通過
- Ghost 發佈失敗

### 日誌位置

| 位置 | 內容 |
|------|------|
| `logs/cron.log` | Cron 執行記錄 |
| `output/{date}/` | 當日輸出（文章、圖表） |
| `output/{date}/qa_report.json` | QA 驗證結果 |

---

## 5. 故障排除

### 常見問題

| 問題 | 解決方案 |
|------|----------|
| Ghost 發佈失敗 | 確認 API Key 權限、檢查 `source=html` |
| LLM 超時 | 增加 timeout 或降級為預設內容 |
| 圖表生成失敗 | 確認 matplotlib + 中文字體已安裝 |
| QA Gate 失敗 | 查看 qa_report.json 檢查具體錯誤 |

### 手動重試

```bash
# 重新執行當日
python -m app.run

# 強制發佈（跳過 QA 檢查 - 謹慎使用）
SKIP_QA=1 python -m app.run
```

---

## 6. 版本更新

```bash
# 拉取最新代碼
git pull

# 重建 Docker 映像
docker-compose build --no-cache

# 重啟服務
docker-compose up -d
```

---

## 7. 健康檢查清單

- [ ] `.env` 已配置所有必要變數
- [ ] `python -m app.run` 手動執行成功
- [ ] Ghost 文章正確發佈
- [ ] Slack 告警可正常接收
- [ ] Cron 已設定且時區正確

---

*Rocket Screener v10 — 獻給散戶的機構級分析*
