# Phase 1 Tech Knowledge Manager

這是一個可直接轉移到 Git 的 Phase 1 starter repo，目標是先完成：

- 本地 Ollama 模型對話
- FastAPI 後端
- Telegram polling
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
- Telegram bot 長輪詢（long polling）收訊與回覆
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

### 1. 先安裝 Ollama

如果你執行 `ollama list` 看到：

```bash
bash: ollama: command not found
```

代表目前主機還沒有安裝 Ollama，必須先安裝。

Linux 常見安裝方式：

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

安裝完成後，先確認指令存在：

```bash
command -v ollama
ollama --version
```

若你的系統沒有自動啟動 Ollama，可另開一個終端機手動啟動：

```bash
ollama serve
```

### 2. 下載要給專案使用的模型

本專案在 repo 根目錄的 `.env.example` 預設為：

```env
OLLAMA_MODEL=gemma3:4b
```

請先下載這個模型：

```bash
ollama pull gemma3:4b
```

下載後確認模型真的存在：

```bash
ollama list
```

### 3. 建立虛擬環境

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. 準備 `.env`

```bash
cp .env.example .env
```

請至少填入：

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=gemma3:4b
APP_BASE_URL=http://your-internal-host:8000
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_POLLING_ENABLED=true
TELEGRAM_POLLING_TIMEOUT_SECONDS=30
TELEGRAM_POLLING_LIMIT=100
TELEGRAM_POLLING_RETRY_DELAY_SECONDS=5
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_PUBLIC_KEY=your_discord_public_key
```

> 若只先測 Telegram，可先不填 Discord 相關欄位；`APP_BASE_URL` 也可以直接填你的內網網址，例如 `http://your-internal-host:8000`。另外，`OLLAMA_MODEL` 必須和你已經 `ollama pull` 下來的模型名稱一致。

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

### 1. 先確認本機 Ollama 正常

```bash
curl http://127.0.0.1:11434/api/tags
```

有回傳 JSON 代表 Ollama server 有正常啟動。

### 2. 直接測本機模型

```bash
curl http://127.0.0.1:11434/api/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "gemma3:4b",
    "stream": false,
    "messages": [
      {"role": "user", "content": "你好，請簡短自我介紹"}
    ]
  }'
```

如果這一步失敗，優先檢查：

- `ollama serve` 是否正在執行
- `ollama list` 是否看得到 `.env` 內設定的模型
- `.env` 的 `OLLAMA_MODEL` 是否和你下載的模型名稱一致

### 3. 再測專案的 `/config/check`

```bash
curl http://127.0.0.1:8000/config/check
```

重點確認：

- `ollama_base_url` 是否為 `http://127.0.0.1:11434`
- `ollama_model` 是否為你實際安裝的模型名稱

### 4. 最後測專案 `/chat`

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "text": "請介紹這個系統的用途"
  }'
```

如果 `/config/check` 正常、Ollama 直接測也正常，但 `/chat` 失敗，才需要回頭檢查應用本身。

### 5. 最短檢查流程

照下面順序檢查最快：

```bash
command -v ollama
ollama --version
curl http://127.0.0.1:11434/api/tags
ollama list
curl http://127.0.0.1:8000/config/check
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"text":"請介紹這個系統的用途"}'
```

---

## Telegram polling 設定

1. 在 Telegram 用 `@BotFather` 建立 bot。
2. 取得 bot token，填入 `.env` 的 `TELEGRAM_BOT_TOKEN`。
3. 確認你的 KM 主機可以對外連到 `https://api.telegram.org`。
4. 直接啟動服務即可，**不需要設定 webhook**。

> Telegram polling 模式建議只跑 **單一應用實例**，避免多個程序同時抓取同一個 bot 的 updates。

若你曾經替同一個 bot 設定過 webhook，建議先清掉：

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook" \
  -d "drop_pending_updates=false"
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
- Telegram 採 outbound polling，不需要對 Telegram 開公開 webhook
- 若要接 Discord，再額外配置 Nginx reverse proxy + HTTPS

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

## 內網部署建議

如果你的 KM 只想活在內網，例如 `your-internal-host`：

- Telegram 只需要讓主機能連外到 `api.telegram.org`
- 不需要讓 Telegram 主動打進你的內網
- 可直接在內網用 `http://your-internal-host:8000` 提供 `/health`、`/chat`、`/config/check`
- 若之後還要接 Discord 或其他 webhook 型平台，再另外加公開 HTTPS reverse proxy

---

## 下一步

請看 `docs/PROJECT_PLAN.md`，裡面已把 Phase 1 → Phase 3 的演進路線整理好。
