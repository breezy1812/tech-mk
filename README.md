# Phase 1-2B Tech Knowledge Manager

這是一個可直接轉移到 Git 的 Phase 1 starter repo，目標是先完成：

- 本地 Ollama 模型對話
- FastAPI 後端
- Telegram polling
- Discord webhook
- 統一訊息入口與回覆流程
- 基本健康檢查與設定管理

> 目前 repo 已完成 Phase 1 聊天骨架，以及 Phase 2 的 indexing 與 query 主鏈路，包含 `/rag/query` 與 Telegram `/askdoc` 整合。

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
- `/rag/query` 根據知識庫內容回答問題，並回傳來源清單
- `/rag/status` 檢查目前 collection 與最近一次 indexing 報表
- `/rag/reindex` 全量重建單一 `tech_docs` collection
- Telegram bot 長輪詢（long polling）收訊與回覆
- Telegram `/askdoc`、`/ragstatus`、`/reindex`
- `/webhook/discord` 接 Discord 訊息
- 同步呼叫 Ollama `/api/chat`
- 本地文件 loader：`.md`、`.txt`、`.pdf`、`.docx`
- 簡單可預測 chunking 與 indexing 報表輸出
- Chroma top-k retrieval
- RAG 專用 prompt builder 與保守回答策略

### 暫不包含
- tool calling
- 多代理
- 長期記憶
- streaming
- hybrid retrieval / reranker

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
TELEGRAM_ADMIN_USER_IDS=
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_PUBLIC_KEY=your_discord_public_key
RAG_DOCS_ROOT=data/docs
RAG_VECTOR_STORE_PATH=data/vector_store
RAG_COLLECTION_NAME=tech_docs
RAG_TOP_K=3
RAG_EMBEDDING_MODEL=nomic-embed-text
RAG_QUERY_DEBUG_DEFAULT=false
RAG_ALLOW_REINDEX=false
```

> 若只先測 Telegram，可先不填 Discord 相關欄位；`APP_BASE_URL` 也可以直接填你的內網網址，例如 `http://your-internal-host:8000`。另外，`OLLAMA_MODEL` 必須和你已經 `ollama pull` 下來的模型名稱一致。

若你想調整機器人的回覆風格，優先修改 `.env` 內的 `OLLAMA_SYSTEM_PROMPT`。目前預設值會偏向即時聊天風格，避免太像 Markdown 文件；如果你希望更口語，可以再明確加入像是「像真人對話，不要使用標題與條列，除非我要求」這類限制。

若你要使用 Phase 2A indexing，還需要先拉 embedding model：

```bash
ollama pull nomic-embed-text
```

---

## 啟動

```bash
bash run_local.sh
```

或

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Phase 2 Indexing And Query

目前採固定策略：

- 單一 docs root：`data/docs`
- 單一 collection：`tech_docs`
- 全量重建：每次 `/rag/reindex` 都重建整個 collection

可先把文件放進 `data/docs`，再用以下方式重建索引：

```bash
.venv/bin/python scripts/reindex.py
```

或透過 API：

```bash
curl -X POST http://127.0.0.1:8000/rag/reindex
curl http://127.0.0.1:8000/rag/status
```

`/rag/reindex` 預設受 `RAG_ALLOW_REINDEX` 保護；若你要讓 API 端可直接重建，需在 `.env` 內明確打開。

建立索引後，可直接測試 `/rag/query`：

```bash
curl -X POST http://127.0.0.1:8000/rag/query \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "這份文件在說什麼？",
    "top_k": 3
  }'
```

若你要看 debug 資訊：

```bash
curl -X POST http://127.0.0.1:8000/rag/query \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "這份文件在說什麼？",
    "top_k": 3,
    "debug": true
  }'
```

一般模式下回傳格式會固定為：

```json
{
  "answer": "...",
  "sources": [
    {"file": "guide.md", "chunk": 0, "relative_path": "guide.md"}
  ]
}
```

只有 `debug=true` 才會額外附上 `retrieved_chunks`。

## RAG 流程說明

目前這套 RAG 不是每次提問都把所有原始文件重新讀一遍，而是分成兩段：

- 建索引時：把支援的文件完整讀入、切塊、做 embedding、寫進 Chroma
- 查詢時：只把問題做 embedding，從 Chroma 撈出最相關的 top-k chunks，再交給 LLM 生成答案

也就是說：

- `/rag/reindex` 會重新處理整批文件
- `/rag/query` 不會重新全文掃描所有文件
- `/rag/query` 只會使用查回來的相關 chunks，而不是整份文件全文

### 流程圖

```mermaid
flowchart TD
  A[文件放入 data/docs] --> B[Loader 讀取 .md .txt .pdf .docx]
  B --> C[TextChunker 切成 chunks]
  C --> D[EmbeddingClient 產生每個 chunk 的 embedding]
  D --> E[Chroma 儲存 chunk 與向量]

  Q[使用者問題] --> R[EmbeddingClient 產生 query embedding]
  R --> S[Chroma 查 top-k 相關 chunks]
  S --> T[RAGPromptBuilder 組 prompt]
  T --> U[Ollama chat 生成答案]
  S --> V[整理 sources]
  U --> W[/rag/query 回傳 answer]
  V --> W
```

### 詳細解釋

#### 1. 建索引階段

這一段由 [app/services/indexing_service.py](/home/mads/tech-mk/app/services/indexing_service.py) 負責。

系統會掃描 `RAG_DOCS_ROOT` 底下所有支援格式的文件，逐份做以下事情：

1. 用 loader 讀出原始文字
2. 切成多個 chunks
3. 為每個 chunk 建立 embedding
4. 把 chunk 內容與對應 embedding 寫進 Chroma

所以在 reindex 時，確實是把每份文件都完整處理過一次。

#### 2. 查詢階段

這一段主要由 [app/services/rag_service.py](/home/mads/tech-mk/app/services/rag_service.py) 串起來。

當你呼叫 `/rag/query` 時，系統不會再把 docs root 裡所有原始文件整批重讀一次，而是：

1. 先把你的問題轉成 query embedding
2. 從 Chroma 撈出最相關的 top-k chunks
3. 把這些 chunks 組進 RAG prompt
4. 呼叫 Ollama 生成答案
5. 回傳 `answer` 與 `sources`

因此目前的成本主要是：

- reindex 時花一次較多時間
- query 時只查向量庫與少量相關 chunks

#### 3. 目前策略的特性

目前 repo 採的是簡化且穩定的做法：

- 單一 docs root
- 單一 collection：`tech_docs`
- 全量重建索引
- 不做 incremental sync
- 不做 hybrid retrieval 或 reranker

這樣的好處是行為單純、容易驗證；缺點是每次 reindex 都會整批重建。

### Telegram 指令

Phase 2B 完成後，Telegram 目前支援：

- `/askdoc <問題>`：查詢知識庫
- `/ragstatus`：查看索引狀態
- `/reindex`：重建索引，需 admin user 且 `RAG_ALLOW_REINDEX=true`

完整的中文逐步驗證流程請見 [docs/PHASE_2B_VALIDATION.md](/home/mads/tech-mk/docs/PHASE_2B_VALIDATION.md)。

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
