
# Phase 2 計畫書

## 專案名稱

**Local LLM Technical Knowledge Manager – Phase 2**

## 文件目的

在既有 Phase 1 已完成的基礎上，進一步導入**技術知識庫查詢能力**，讓系統從單純的聊天轉為可查詢文件內容的技術助理。
本階段**不導入完整 orchestration framework**，但會建立 Phase 3 可擴充的結構。

---

# 0. 目前進度摘要

## 0.1 Phase 2A 已完成什麼

簡白地說，Phase 2A 目前已經把「文件進系統並建立索引」這一段打通了。

也就是說，現在系統已經可以：

* 讀取本地文件
* 把文件切成較小片段
* 為這些片段產生 embedding
* 把結果寫進 Chroma 向量資料庫
* 透過 API 查看目前索引狀態
* 透過 API 重新建立整份文件索引

目前已完成並驗證的重點如下：

* 已建立 Phase 2 的基本模組結構：`api/routes`、`services`、`adapters`、`domain/schemas`、`ingestion`
* 已實作文件 loader，支援 `.md`、`.txt`、`.pdf`、`.docx`
* 已實作簡單可預測的 chunking 規則
* 已接上 Ollama embedding model
* 已接上 Chroma，並固定使用單一 collection：`tech_docs`
* 已實作 `/rag/status`
* 已實作 `/rag/reindex`
* 已實作 indexing report，方便 debug 每次重建索引的結果
* 已提供 `scripts/reindex.py` 供手動重建索引

目前手動驗證的結果是：至少三種文件格式已成功完成載入、切塊、embedding 與寫入向量庫。

## 0.2 Phase 2B 已完成什麼

簡白地說，Phase 2B 目前已經把「把已經建立好的知識索引查出來並回答」這一段打通了。

也就是說，現在系統已經可以：

* 針對使用者問題做 query embedding
* 從 Chroma 取回 top-k 相關 chunks
* 使用 RAG 專用 prompt 組裝上下文
* 在 retrieval 有結果時呼叫 Ollama 產生答案
* 在 retrieval 無結果時直接保守回答，不呼叫 LLM
* 回傳整理過的 `sources` 給 API 或產品層使用
* 在 debug 模式下額外輸出 `retrieved_chunks`
* 透過 Telegram `/askdoc` 查詢知識庫
* 透過 Telegram `/ragstatus` 查看索引狀態
* 透過 Telegram `/reindex` 重建索引

目前已完成並驗證的重點如下：

* 已實作 retrieval service 與 `vector_store.query()` 查詢契約
* 已實作 RAG 專用 prompt builder，並與一般 `/chat` prompt 分離
* 已實作 rag service orchestration
* 已實作 `/rag/query`
* 已完成業務上查無資料與真正 backend failure 的分流
* 已完成 Telegram `/askdoc`、`/ragstatus`、`/reindex` 的薄層整合
* 已新增 retrieval、rag service、rag API、telegram routing 測試

## 0.3 目前仍未納入範圍

雖然 Phase 2 的主鏈路已完成，但以下內容仍不在本階段範圍內：

* reranker
* hybrid retrieval
* metadata filter 查詢
* background reindex job
* 完整 orchestration framework
* 多 agent

> **Phase 2A 已經完成「把知識放進去」。**
> **Phase 2B 已經完成「把知識查出來並回答」。**

---

# 1. Phase 2 目標

## 1.1 核心目標

建置一套最小可用的 RAG 能力，使系統可以：

1. 匯入本地技術文件
2. 進行切塊與向量化
3. 儲存於向量資料庫
4. 接收使用者問題
5. 從知識庫檢索相關內容
6. 將檢索結果與問題一併送入 LLM 回答
7. 回傳答案與引用片段

## 1.2 本階段完成後，使用者應能做到

* 透過 API 查詢文件內容
* 透過 Telegram 查詢文件內容
* 看到回答所依據的片段或來源
* 對指定資料夾重新做索引
* 在不更改 Telegram 接入方式的前提下完成 RAG 查詢

---

# 2. 本階段不做的事情

為避免 scope 膨脹，Phase 2 **不包含**：

* 完整 LangGraph / workflow orchestration
* 多 agent 架構
* 自動工具呼叫
* 長期記憶系統
* 權限分級 / 多租戶
* 文件版本管理
* 自動增量同步檔案監控
* OCR-heavy 文件流程
* 複雜 reranker / hybrid retrieval 優化

本階段定位是：

> **在現有聊天骨架上，先導入穩定、可解釋、可維護的單路徑 RAG。**

---

# 3. 建議架構

## 3.1 高層架構

```text
User
  ↓
Telegram Polling / API Client
  ↓
FastAPI
  ↓
Application Service
  ├─ Chat mode
  └─ RAG mode
         ↓
   Retriever
         ↓
   Vector DB
         ↓
   Prompt Builder
         ↓
      Ollama
         ↓
     Response
```

## 3.2 設計原則

* **入口層與知識庫邏輯分離**
* **LLM 呼叫與 retrieval 分離**
* **先 rule-based route，不急著導入 orchestration framework**
* **回應附來源，提升可驗證性**
* **所有 indexing 與 query 都要可單獨測試**

---

# 4. 功能範圍

## 4.1 文件 ingestion

支援從本地資料夾載入文件，初版建議只支援：

* `.md`
* `.txt`
* `.pdf`

可選擇性加上：

* `.docx`

暫不建議 Phase 2 一開始就做：

* `.pptx`
* 圖片 OCR
* 複雜表格抽取

## 4.2 文件切塊

需實作 chunking，建議：

* chunk size: 500–1000 tokens 對應字數近似
* overlap: 100–150 tokens

要求：

* 保留來源檔名
* 保留 chunk index
* 保留原始相對路徑
* 保留必要 metadata

## 4.3 向量資料庫

建議優先選用：

* **Chroma**

原因：

* 本地部署簡單
* 開發速度快
* 對 Phase 2 足夠

若專案端已有偏好，也可用：

* FAISS

但若需要 metadata filter 與未來擴充性，Chroma 會比較順。

## 4.4 Embedding

若維持本地優先，可考慮：

* Ollama embedding model
* 或 sentence-transformers 本地模型

建議初版以**穩定與可部署為先**，不要一開始追求最佳 embedding 品質。

## 4.5 查詢 API

至少提供：

### `POST /rag/query`

輸入：

* question
* top_k
* optional filters

輸出：

* answer
* retrieved_chunks
* source filenames
* metadata

### `POST /rag/reindex`

功能：

* 對指定資料夾重新建立索引

### `GET /rag/status`

功能：

* 回報目前 collection 狀態
* 文件數 / chunk 數 / 最後索引時間

## 4.6 Bot 指令

Telegram 層至少支援：

* `/askdoc <問題>`
* `/reindex`（可先限制本地管理用途）
* `/ragstatus`

若目前 polling handler 已穩定，可直接在 command routing 上擴充，不需重做入口層。

---

# 5. 建議模組拆分

以下為建議的 repo 結構方向：

```text
app/
  api/
    routes/
      chat.py
      rag.py

  services/
    chat_service.py
    rag_service.py
    retrieval_service.py
    indexing_service.py

  core/
    config.py
    logging.py

  adapters/
    ollama_client.py
    telegram_bot.py
    vector_store.py
    embedding_client.py

  domain/
    schemas/
      rag.py
      chat.py

  ingestion/
    loaders/
      pdf_loader.py
      text_loader.py
      markdown_loader.py
    chunkers/
      text_chunker.py

data/
  docs/
  vector_store/

scripts/
  reindex.py
```

原則：

* `api/routes`：只做 request/response
* `services`：放商業邏輯
* `adapters`：封裝外部系統
* `ingestion`：處理文件
* `domain/schemas`：資料模型

---

# 6. 查詢流程設計

## 6.1 RAG query flow

1. 接收使用者問題
2. 呼叫 embedding model 產生 query embedding
3. 至 vector DB 查 top-k chunks
4. 組合 prompt：

   * system instruction
   * retrieved context
   * user question
5. 呼叫 Ollama chat model
6. 回傳答案與來源

## 6.2 Prompt 規則

需明確要求模型：

* 優先根據提供的 context 回答
* context 不足時要明講不知道
* 不要假設文件中未出現的資訊
* 回傳時可附來源檔名或 chunk 編號

建議 system prompt 包含：

* 回答語氣
* 根據檢索內容作答
* context 不足時保守回答
* 引用來源格式

---

# 7. 路由策略

Phase 2 不導入完整 orchestration，但要先建立**最小路由控制**：

## 7.1 API 層路由

* `/chat`：一般聊天
* `/rag/query`：文件問答
* `/rag/reindex`：重建索引

## 7.2 Bot 層路由

* `/askdoc` → RAG
* 一般訊息 → 一般聊天
* `/ragstatus` → status
* `/reindex` → indexing

這樣做的好處是：

* 邏輯清楚
* 好測試
* 未來 Phase 3 可自然升級成 state/router graph

---

# 8. 與 Telegram polling 方式的相容性要求

由於目前 Telegram 已改為 polling，Phase 2 實作需遵守：

1. **不得假設 webhook-only 架構**
2. bot handler 與 service 層必須解耦
3. polling 僅作為訊息來源，不應承擔 RAG 邏輯
4. command parsing 與 business logic 分離
5. 若 polling 有重複 update 風險，需保證 command 處理冪等性

建議實作：

* bot adapter 只負責：

  * 收訊息
  * parse command
  * 呼叫 service
  * 回傳文字
* 不把 retrieval / indexing 寫進 bot handler

---

# 9. 非功能需求

## 9.1 可維護性

* 各模組需可單獨測試
* 避免把所有流程寫進單一 route handler
* 配置集中管理

## 9.2 可觀測性

至少加入：

* query log
* retrieval top-k log
* indexing result log
* response latency log

## 9.3 穩定性

* 文件載入失敗不可讓整體服務崩潰
* 單一文件 parse 失敗要記錄並跳過
* 向量庫不存在時要可自動初始化

## 9.4 安全性

* `/reindex` 最好不要對所有外部聊天入口完全開放
* 可先限制為：

  * local-only
  * admin command
  * env flag 開關

---

# 10. 交付項目

Phase 2 完成時應交付：

## 10.1 程式功能

* 可運行的 RAG API
* 可運行的 indexing script
* Telegram `/askdoc` 指令
* Chroma 或 FAISS 本地向量庫整合
* Embedding model 串接
* Ollama RAG answer flow

## 10.2 文件

* README 更新
* `.env.example` 更新
* 索引流程說明
* 支援文件格式說明
* API 規格說明

## 10.3 測試

至少包含：

* chunking test
* indexing test
* retrieval test
* rag service test
* API smoke test

---

# 11. 驗收標準

符合以下條件視為完成：

1. 指定資料夾內文件可成功建立索引
2. `/rag/query` 能回傳答案與來源
3. Telegram `/askdoc` 可正常查詢
4. 查無資料時能保守回答，不胡亂生成
5. 單一文件損壞不影響整體索引流程
6. README 足以讓新開發者完成啟動與驗證

---

# 12. 建議開發順序

## Step 1

建立 ingestion 與 chunking 模組
輸入文件，輸出 chunks + metadata

## Step 2

接入 embedding 與 vector store
完成 reindex script

## Step 3

建立 retrieval service
輸入 query，回傳 top-k chunks

## Step 4

建立 rag service
完成 prompt 組裝與 Ollama 問答

## Step 5

暴露 API route
完成 `/rag/query` `/rag/status` `/rag/reindex`

## Step 6

串到 Telegram command handler
支援 `/askdoc`

## Step 7

補齊 logging / tests / README

---

# 13. 風險與注意事項

## 13.1 Telegram polling

若 update offset 沒處理好，可能造成重複訊息。
需確認 bot adapter 對 command 執行沒有重複副作用。

## 13.2 PDF 品質

若 PDF 解析品質差，會直接影響 RAG 品質。
Phase 2 應先接受此限制，不建議急著上 OCR。

## 13.3 Embedding 模型選型

embedding 模型若過重，可能拖慢 indexing。
Phase 2 應優先求穩定，再做品質優化。

## 13.4 Prompt 注入與幻覺

context 拼接策略需保守，避免把不可靠內容混入。
回答需附來源，降低錯誤信任。

---

# 14. Phase 2 完成後的下一步

Phase 2 完成後，可進入 Phase 3：

* 加入最小 orchestration
* 導入 chat / rag / tool 三路由
* 建立 conversation state
* 加入管理命令
* 規劃未來 LangGraph 或自定 router

也就是說：

> **Phase 2 是把知識庫接上。
> Phase 3 才是把總控台接上。**

---

# 15. 可直接交付 agent 的任務摘要

請基於既有 Phase 1 repo，實作 Phase 2：
為系統加入本地文件知識庫查詢能力，包含文件 ingestion、chunking、embedding、vector database、retrieval、RAG answer flow、FastAPI 路由與 Telegram `/askdoc` 指令整合。
本階段不導入完整 orchestration framework，但需保留未來擴充結構，並確保 polling 式 Telegram 接入可以相容運作。

---

如果你要，我下一則可以直接幫你把這份再整理成**更像 PRD / implementation ticket 的版本**，讓對方 agent 更容易照單實作。
