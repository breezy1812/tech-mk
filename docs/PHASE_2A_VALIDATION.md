# Phase 2A 手動驗證指南

這份文件的目標不是再跑一次單元測試，而是用最少步驟確認整條 Phase 2A pipeline 真的可用：

- 文件可被載入
- 文件可被切塊
- embedding 可正常產生
- Chroma 可寫入資料
- `/rag/status` 與 `/rag/reindex` 可正常工作

若這份流程全部通過，再進入 Phase 2B 會比較穩。

---

## 0. 先決條件

請先確認你在專案根目錄，並且已經建立好虛擬環境。

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

---

## 1. 先跑現有測試

這一步是先確認 repo 目前的基礎狀態正常，避免把環境問題誤判成 RAG 問題。

```bash
python -m pytest -q
```

預期結果：

- 全部通過
- 沒有 import error
- 沒有 config error

目前預期應該會看到類似：

```bash
11 passed
```

---

## 2. 建立最小測試文件集

先不要直接動正式的 `data/docs`，使用獨立資料夾做驗證最乾淨。

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

不要先改 `.env`，直接用 shell 覆蓋這次測試所需設定就夠了。

重點是：

- `RAG_DOCS_ROOT=./test_docs`
- `RAG_ALLOW_REINDEX=true`

在一個 terminal 執行：

```bash
RAG_DOCS_ROOT=./test_docs \
RAG_ALLOW_REINDEX=true \
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

如果你習慣用腳本，也可以先用 export 再跑：

```bash
export RAG_DOCS_ROOT=./test_docs
export RAG_ALLOW_REINDEX=true
bash run_local.sh
```

兩種方式擇一即可，不要同時跑兩個 server。

---

## 4. 先檢查 status

開第二個 terminal：

```bash
curl http://127.0.0.1:8000/rag/status
```

預期結果：

- HTTP 200
- 不是 500
- JSON 內可看到：
  - `docs_root`
  - `collection_name`
  - `chunk_size`
  - `chunk_overlap`

第一次啟動、尚未 reindex 前，以下值可能是 0 或 `null`，這是正常的：

- `indexed_files`
- `indexed_chunks`
- `last_indexed_at`
- `last_report`

---

## 5. 執行 reindex

這是 Phase 2A 最重要的一步。

```bash
curl -X POST http://127.0.0.1:8000/rag/reindex
```

預期結果：

- HTTP 200
- 不是 403
- 不是 500

請重點檢查回傳 JSON 內這些欄位：

- `collection_name`
- `embedding_model`
- `files_processed`
- `chunks_indexed`
- `failed_files`
- `files`

### 通過條件

至少要符合：

- `files_processed` 等於 `2`
- `chunks_indexed` 大於 `0`
- `failed_files` 是空陣列
- `files` 中每一筆都為 `status: "indexed"`

---

## 6. 再查一次 status

```bash
curl http://127.0.0.1:8000/rag/status
```

預期結果：

- `indexed_files` 大於 `0`
- `indexed_chunks` 大於 `0`
- `last_indexed_at` 有值
- `last_report` 不為空

這一步是在確認 index 不只是 reindex 當下算出來，而是真的被系統保存下來。

---

## 7. 可選加測：PDF

如果你想多驗一個最容易出問題的格式，可以再加一個簡單 PDF。

假設你手上已有一個可讀 PDF：

```bash
cp /path/to/sample.pdf test_docs/c.pdf
curl -X POST http://127.0.0.1:8000/rag/reindex
```

預期：

- `files_processed` 變成 `3`
- `failed_files` 仍為空，或至少不包含 `c.pdf`

若 PDF 失敗，但 txt/md 正常，代表 Phase 2A 核心資料流大致可用，問題集中在 parser 而不是整體架構。

---

## 最小通過標準

只要下面四件事成立，就可以視為 Phase 2A 基本可用：

1. `GET /rag/status` 可正常回應
2. `POST /rag/reindex` 成功
3. `chunks_indexed > 0`
4. 第二次 `GET /rag/status` 可看到已存在的 index 與 `last_report`

---

## 看到以下情況就先不要進 Phase 2B

- `POST /rag/reindex` 回 403
- `POST /rag/reindex` 回 500
- `chunks_indexed == 0`
- `failed_files` 有你預期應成功的 txt 或 md
- Ollama embedding timeout
- `/rag/status` 看不到任何 indexed 資訊

---

## 補充說明

目前專案的 Phase 2A 設計是：

- 單一 docs root
- 單一 collection：`tech_docs`
- 全量重建
- 不做 incremental sync

所以這份驗證文件也刻意只測這一條最小路徑，不去引入多 collection 或複雜權限情境。
