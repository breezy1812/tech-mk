# Phase 2B 手動驗證指南

這份文件的目標不是重跑單元測試，而是用最少步驟確認 Phase 2B 的查詢主鏈路真的可用：

- 已建立的索引可被查詢
- `/rag/query` 可回傳答案與來源
- `debug=true` 時可額外看到 `retrieved_chunks`
- 查無資料時會保守回答，不會硬湊內容
- Telegram `/askdoc`、`/ragstatus`、`/reindex` 可正常工作

若這份流程全部通過，就代表目前的 Phase 2 已經不是只有「能建索引」，而是已經具備「可查詢、可回答、可透過 bot 使用」的基本能力。

---

## 0. 先決條件

請先確認你在專案根目錄，並且使用的是 repo 內的虛擬環境。

### 確認目前工作路徑

```bash
pwd
```

預期應為：

```bash
/home/mads/tech-mk
```

### 確認虛擬環境可用

```bash
.venv/bin/python --version
```

### 確認 Ollama 可用

```bash
ollama list
curl http://127.0.0.1:11434/api/tags
```

若 Ollama 尚未啟動，先在另一個 terminal 執行：

```bash
ollama serve
```

### 確認 embedding model 已存在

```bash
ollama pull nomic-embed-text
```

### 若你要驗證 Telegram，先確認 `.env` 至少有這些值

```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_POLLING_ENABLED=true
```

若你要驗證 Telegram `/reindex`，還需要：

```env
RAG_ALLOW_REINDEX=true
TELEGRAM_ADMIN_USER_IDS=你的 Telegram user id
```

---

## 1. 先跑現有測試

這一步是先確認 repo 目前狀態正常，避免把環境問題誤判成 RAG query 問題。

```bash
.venv/bin/python -m pytest -q
```

預期結果：

- 全部通過
- 沒有 import error
- 沒有 config error

目前預期應該會看到類似：

```bash
25 passed
```

---

## 2. 準備最小測試文件集

若你已經有一份想測的文件資料夾，也可以直接跳到下一步。

若你想用最小可控資料集驗證，建議沿用獨立資料夾，不要先動正式的 `data/docs`。

```bash
mkdir -p test_docs
```

### 建立第一個文字檔

```bash
cat > test_docs/a.txt <<'EOF'
This is a test document about AI models.
EOF
```

### 建立第二個 Markdown 檔

```bash
cat > test_docs/b.md <<'EOF'
# RAG Test

Retrieval Augmented Generation is useful.
EOF
```

### 確認檔案存在

```bash
find test_docs -maxdepth 1 -type f | sort
```

預期至少看到：

```bash
test_docs/a.txt
test_docs/b.md
```

---

## 3. 用臨時環境變數啟動 API

建議先用臨時環境變數覆蓋，不要一開始就改正式 `.env`。

重點是：

- `RAG_DOCS_ROOT=./test_docs`
- `RAG_ALLOW_REINDEX=true`

若你還要測 Telegram `/reindex`，請把你的 Telegram user id 一起帶進來：

- `TELEGRAM_ADMIN_USER_IDS=<your_user_id>`

在一個 terminal 執行：

```bash
RAG_DOCS_ROOT=./test_docs \
RAG_ALLOW_REINDEX=true \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

如果這輪只驗 API，不測 Telegram `/reindex`，可以省略 `TELEGRAM_ADMIN_USER_IDS`。

---

## 4. 先確認 status 與 reindex 正常

開第二個 terminal。

### 先查 status

```bash
curl http://127.0.0.1:8000/rag/status
```

預期結果：

- HTTP 200
- JSON 內可看到 `docs_root`、`collection_name`、`chunk_size`、`chunk_overlap`

第一次啟動、尚未 reindex 前，以下值可能是 `0` 或 `null`，這是正常的：

- `indexed_files`
- `indexed_chunks`
- `last_indexed_at`
- `last_report`

### 執行 reindex

```bash
curl -X POST http://127.0.0.1:8000/rag/reindex
```

預期結果：

- HTTP 200
- `files_processed` 等於 `2`
- `chunks_indexed` 大於 `0`
- `failed_files` 為空

### 再查一次 status

```bash
curl http://127.0.0.1:8000/rag/status
```

這一步重點確認：

- `indexed_files` 大於 `0`
- `indexed_chunks` 大於 `0`
- `last_indexed_at` 有值
- `last_report` 不為空

---

## 5. 驗證 `/rag/query` 基本查詢

這一步是確認 Phase 2B 最核心的 API 鏈路：

- 問題可轉成 embedding
- top-k chunks 可被取回
- LLM 會根據檢索結果回答
- API 會回傳產品層可用的 `sources`

執行：

```bash
curl -X POST http://127.0.0.1:8000/rag/query \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "這些文件提到了什麼？",
    "top_k": 3
  }'
```

預期結果：

- HTTP 200
- JSON 內有 `answer`
- JSON 內有 `sources`
- `sources` 不是空陣列

重點不是答案字面上完全固定，而是至少要滿足：

- 回答內容和 `test_docs` 的文件主題一致
- `sources` 中可以看到像 `a.txt` 或 `b.md` 這種來源檔名

---

## 6. 驗證 `debug=true`

這一步是確認 debug 模式下，系統會額外回傳 retrieval 細節，但一般模式不會暴露這些內部資料。

執行：

```bash
curl -X POST http://127.0.0.1:8000/rag/query \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "這些文件提到了什麼？",
    "top_k": 3,
    "debug": true
  }'
```

預期結果：

- HTTP 200
- JSON 內除了 `answer`、`sources`，還會出現 `retrieved_chunks`
- `retrieved_chunks` 內每筆資料可看到檔名、chunk index、內容片段與 score

---

## 7. 驗證查無資料時的行為

這一步的目標不是要讓模型答對，而是要確認系統在沒有可靠檢索結果時，不會硬編內容。

執行：

```bash
curl -X POST http://127.0.0.1:8000/rag/query \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "這份知識庫裡有沒有提到火星殖民地租賃條款？",
    "top_k": 3
  }'
```

通過條件：

- HTTP 200
- 系統回覆偏保守，明確表示文件中找不到或沒有足夠資訊
- `sources` 可能為空，或至少不應該憑空出現不相關來源

若你看到模型硬編大量不存在的細節，代表這條保守回答策略需要回頭再查。

---

## 8. 驗證 Telegram `/askdoc`

這一步是確認 Telegram 端只是薄層入口，真正的查詢行為和 API 保持一致。

### 先傳空白問題

在 Telegram 對 bot 傳：

```text
/askdoc
```

預期結果：

- bot 不應該當機
- bot 應提示正確用法，要求補上問題

### 再傳實際問題

```text
/askdoc 這些文件提到了什麼？
```

預期結果：

- bot 有回覆答案
- 回覆中可看到來源檔名
- 回答方向與 `/rag/query` 結果一致

---

## 9. 驗證 Telegram `/ragstatus`

在 Telegram 對 bot 傳：

```text
/ragstatus
```

預期結果：

- bot 有回覆目前索引狀態
- 回覆內容至少應包含 collection、indexed files、indexed chunks 或最近一次 reindex 的資訊

---

## 10. 驗證 Telegram `/reindex`

這一步分成兩種情境驗證。

### 情境 A：非 admin 或未開啟 `RAG_ALLOW_REINDEX`

在 Telegram 對 bot 傳：

```text
/reindex
```

預期結果：

- bot 明確拒絕
- 不應直接成功重建索引

### 情境 B：admin 且 `RAG_ALLOW_REINDEX=true`

若你已經把自己的 user id 放進 `TELEGRAM_ADMIN_USER_IDS`，再次傳：

```text
/reindex
```

預期結果：

- bot 會回覆重建完成
- 回覆中應可看到 `files_processed`、`chunks_indexed` 等結果摘要

---

## 最小通過標準

只要下面幾件事成立，就可以視為 Phase 2B 基本可用：

1. `POST /rag/reindex` 成功
2. `POST /rag/query` 可回傳 `answer` 與 `sources`
3. `debug=true` 時可看到 `retrieved_chunks`
4. 查無資料時系統不會硬編內容
5. Telegram `/askdoc` 可正常回覆
6. Telegram `/ragstatus` 可正常顯示索引狀態

若你需要驗證管理權限，再補測：

7. Telegram `/reindex` 在非 admin 時會被拒絕
8. Telegram `/reindex` 在 admin 且開啟旗標時可成功執行

---

## 看到以下情況就先不要往下擴充

- `/rag/reindex` 回 403 或 500
- `/rag/query` 回 500 或 502
- `sources` 長期為空，即使文件明明已成功索引
- `debug=true` 仍看不到 `retrieved_chunks`
- Telegram `/askdoc` 沒有回應或只回 generic error
- Telegram `/ragstatus` 回不出目前索引資訊
- Telegram `/reindex` 權限判斷和設定不一致

---

## 補充說明

目前專案的 Phase 2 設計仍維持這些固定前提：

- 單一 docs root
- 單一 collection：`tech_docs`
- 全量重建
- 不做 incremental sync
- `/chat` 與 `/rag/query` 分離，不混成單一路由

所以這份驗證文件也刻意只測最小、最穩定的主鏈路，不去引入 reranker、hybrid retrieval、metadata filter 或 background job。