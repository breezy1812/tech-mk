# Phase 1 Tech Knowledge Manager

這是一個可直接轉移到 Git 的 Phase 1 starter repo，目標是先完成：

- 本地 Ollama 模型對話
- FastAPI 後端
- Telegram webhook
- Discord webhook
- 統一訊息入口與回覆流程
- 基本健康檢查與設定管理

> Phase 1 重點不是做完整 agent，而是先把聊天中間層穩定建立起來。

---

## 架構

```text
Telegram / Discord
        ↓
      FastAPI
        ↓
   Message Router
        ↓
   Ollama Client
        ↓
 Local Model (gemma / qwen / other ollama model)
```

---

## 目錄結構

```text
.
├── app/
│   ├── connectors/
│   │   ├── discord_handler.py
│   │   └── telegram_handler.py
│   ├── config.py
│   ├── logging_setup.py
│   ├── main.py
│   ├── models.py
│   ├── ollama_client.py
│   ├── router.py
│   └── service.py
├── docs/
│   └── PROJECT_PLAN.md
├── tests/
│   └── test_health.py
├── .env.example
├── .gitignore
├── requirements.txt
└── run_local.sh
```

---

## 功能範圍

### 已包含
- `/health` 健康檢查
- `/config/check` 設定檢查
- `/chat` 直接測試 API
- `/webhook/telegram` 接 Telegram 訊息
- `/webhook/discord` 接 Discord 訊息
- 同步呼叫 Ollama `/api/chat`

### 暫不包含
- 向量資料庫
- 文件 ingestion
- tool calling
- 多代理
- 長期記憶
- streaming

---

## 安裝

### 1. 建立虛擬環境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. 準備 `.env`

```bash
cp .env.example .env
```

請至少填入：

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b
APP_BASE_URL=https://your-domain.example.com
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_PUBLIC_KEY=your_discord_public_key
```

> 若只先測 Telegram，可先不填 Discord 相關欄位。

---

## 啟動

```bash
bash run_local.sh
```

或

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 測試 Ollama API

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "請介紹這個系統的用途"
  }'
```

---

## Telegram webhook 設定

先確認你的服務可被 Telegram 存取，例如：

```text
https://your-domain.example.com/webhook/telegram
```

設定 webhook：

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -d "url=https://your-domain.example.com/webhook/telegram"
```

---

## Discord webhook / interaction 設定

在 Discord Developer Portal 建立 application，取得：

- Bot Token
- Public Key

互動端點設為：

```text
https://your-domain.example.com/webhook/discord
```

目前這個 starter 主要支援：
- `PING`
- 基本 message payload

如果你之後要做 slash command 與更完整互動，可在 Phase 2 擴充。

---

## 建議部署方式

Phase 1 先建議用最簡單方式：

- Ubuntu server
- Python venv
- systemd
- Nginx reverse proxy
- HTTPS

後續再考慮：

- Docker
- Redis queue
- Chroma / PostgreSQL
- observability

---

## systemd 範例

```ini
[Unit]
Description=Phase1 Tech Knowledge Manager
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/phase1-tech-km-repo
EnvironmentFile=/opt/phase1-tech-km-repo/.env
ExecStart=/opt/phase1-tech-km-repo/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## Git 初始化

```bash
git init
git add .
git commit -m "init phase1 starter repo"
```

若要推到你的 Git 遠端：

```bash
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

---

## 下一步

請看 `docs/PROJECT_PLAN.md`，裡面已把 Phase 1 → Phase 3 的演進路線整理好。
