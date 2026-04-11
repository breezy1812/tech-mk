# Phase 1 專案計劃書

## 1. 專案名稱
Phase 1 Tech Knowledge Manager Starter

## 2. 專案目的
建立一個可部署在 server 上、可串接 Telegram 或 Discord、並可透過本地 Ollama 模型回覆訊息的最小可用系統。

此階段重點是：
- 穩定
- 可控
- 容易 debug
- 可逐步擴充

而不是一開始就追求完整 agent 自主能力。

---

## 3. 背景與動機
先前使用 OpenClaw 的主要問題在於：
- 中間層不夠透明
- tool routing 不易控制
- streaming / timeout 問題增加除錯成本
- 難以作為穩定的 server-side 技術管理員基礎

因此本專案改採較傳統且可控的架構：
- FastAPI 作為服務入口
- Python 明確定義 routing 與 service flow
- Ollama 作為本地模型執行層
- 聊天平台僅作為外部訊息入口

---

## 4. Phase 1 目標

### 核心目標
1. 可接收外部聊天訊息
2. 可將訊息送入本地 Ollama 模型
3. 可將回覆返回聊天平台
4. 可在 server 上穩定部署
5. 可輕鬆轉移到 Git 與持續開發

### 成功判定
- Telegram 訊息可以正常收到與回覆
- Discord 基本訊息入口可以打通
- `/chat` API 可直接測試模型回應
- `/health` 與 `/config/check` 可用於部署檢查

---

## 5. 系統範圍

### 納入範圍
- FastAPI 應用主體
- Ollama client
- 訊息標準化模型
- Telegram polling handler
- Discord webhook handler
- 統一 message router
- 基礎 logging
- 可上 Git 的 repo 結構

### 不納入範圍
- 向量資料庫
- 文件切塊與 embedding
- RAG retrieval
- tool calling framework
- 多 agent 協作
- 背景任務佇列
- 多租戶權限控管

---

## 6. 系統架構

```text
Telegram / Discord
        ↓
      FastAPI
        ↓
 Unified Connector Layer
        ↓
  Message Router / Service
        ↓
    Ollama Client
        ↓
    Local LLM Model
```

---

## 7. 設計原則

### 7.1 先同步、後複雜
Phase 1 使用同步請求，不先導入 streaming、queue、async tool calls。

### 7.2 中間層明確可讀
每個步驟由 Python 顯式控制，不依賴黑盒 agent orchestrator。

### 7.3 先平台穩定，後知識庫
先把聊天穩定打通，再加入技術資料檢索。

### 7.4 可遷移到 Git 與 CI
repo 結構保持乾淨，便於之後加上 lint、test、Docker 與 CI/CD。

---

## 8. Phase 規劃

## Phase 1：聊天中間層打通
### 目標
- FastAPI + Ollama + Telegram/Discord 打通
- 統一訊息格式
- 能在 server 上穩定運作

### 產出
- starter repo
- README
- 計劃書
- 基本測試

---

## Phase 2：技術知識庫接入
### 目標
- 導入文件 ingestion pipeline
- 支援 Markdown / PDF / PPTX / TXT
- 建立 chunking 與 embedding 流程
- 導入 Chroma 或 FAISS

### 預期新增模組
- `ingest/`
- `vector_store/`
- `retrieval/`
- `prompts/`

### 功能
- 問技術文件
- 回答文件來源
- 基本 RAG 查詢

---

## Phase 3：工具與權限控管
### 目標
- 增加 tool calling
- 增加 command routing
- 加入身分與群組限制
- 強化 observability

### 可能項目
- shell tool
- internal API tool
- admin-only commands
- usage logging
- metrics

---

## 9. 風險與對策

### 風險 1：Ollama 回應太慢
對策：
- 先選小模型
- 關閉 streaming
- 設定 timeout

### 風險 2：聊天平台串接除錯困難
對策：
- 保留 `/chat` 本地測試入口
- Telegram 優先採 polling，減少公開 webhook 依賴
- 先本地 curl 驗證，再接外部平台

### 風險 3：Discord 流程較繁瑣
對策：
- Telegram 優先驗證
- Discord 先保留最小 handler

### 風險 4：後續需求膨脹
對策：
- 以 phase 演進
- 每階段只新增單一主題能力

---

## 10. 建議部署策略

### 初期
- venv + systemd + nginx
- 便於快速部署與除錯

### 中期
- Docker 化
- 加入 log rotation
- 加入 reverse proxy hardening

### 後期
- queue / worker
- vector db
- multi-service 架構

---

## 11. Git 遷移建議

1. 先在本地測試 `.env` 與 `run_local.sh`
2. 初始化 Git repo
3. 推到自己的 private repo
4. 新增 branch 策略：
   - `main`: 穩定版
   - `develop`: 開發版
   - `feature/*`: 新功能
5. 導入最基本 CI：
   - import test
   - health route test

---

## 12. 結論
這個 starter repo 的定位不是最終產品，而是可靠的起點。

它的價值在於：
- 可控
- 易懂
- 易部署
- 易演進

等 Phase 1 穩定後，再往知識庫與 agent 能力擴充，整體風險會小很多。
