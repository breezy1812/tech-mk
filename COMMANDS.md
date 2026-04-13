# 指令與技能表

這份文件整理目前專案在 Telegram 與 API 層可直接使用的指令與能力。

---

## Telegram 指令表

目前在 Telegram 上可直接使用的指令如下：

| 指令 | 用途 | 範例 | 備註 |
| --- | --- | --- | --- |
| `/askdoc <問題>` | 查詢知識庫內容 | `/askdoc 這份文件提到了什麼？` | 會走 RAG 查詢，回覆答案與來源檔名 |
| `/ragstatus` | 查看目前索引狀態 | `/ragstatus` | 會顯示 collection、文件數、chunk 數、最後索引時間 |
| `/reindex` | 全量重建索引 | `/reindex` | 只有管理員可用，且需開啟 `RAG_ALLOW_REINDEX=true` |
| `/sync` | 增量同步索引 | `/sync` | 只有管理員可用，且需開啟 `RAG_ALLOW_REINDEX=true` |

---

## Telegram 使用方式

### 1. 一般聊天

如果你在 Telegram 直接輸入一般文字，而不是 slash 指令，系統會走一般聊天模式。

例如：

```text
你好，請介紹這個系統的用途
```

這不會查知識庫，而是走一般 `/chat` 對話邏輯。

### 2. 查知識庫

如果你要查文件內容，要用：

```text
/askdoc 這份文件提到了什麼？
```

這一條會：

1. 把你的問題送進 RAG query
2. 從向量庫找相關 chunks
3. 用 Ollama 生成答案
4. 回覆答案與來源檔名

### 3. 查看索引狀態

```text
/ragstatus
```

這會回你目前索引資料，例如：

* collection 名稱
* 已索引文件數
* 已索引 chunk 數
* 最後索引時間

### 4. 重建索引

```text
/reindex
```

這條不是所有人都能用。要成功執行，必須同時符合：

* `.env` 內 `RAG_ALLOW_REINDEX=true`
* 你的 Telegram user id 已放進 `TELEGRAM_ADMIN_USER_IDS`

如果不符合條件，bot 會直接拒絕。

### 5. 增量同步索引

```text
/sync
```

這條也是管理員指令。要成功執行，必須同時符合：

* `.env` 內 `RAG_ALLOW_REINDEX=true`
* 你的 Telegram user id 已放進 `TELEGRAM_ADMIN_USER_IDS`

它和 `/reindex` 的差別是：

* `/reindex`：整批重建全部索引
* `/sync`：只同步新增、修改、刪除的文件變更

成功時 bot 會回覆：

* 更新檔案數
* 未變更檔案數
* 刪除檔案數
* 失敗檔案數

### 6. 大量文件同步時的建議

如果你這次放了很多測試文件，請先注意這件事：

* `/sync` 雖然已支援 Telegram，但目前仍是同步執行
* 如果變更檔案很多、單檔很大，或 PDF / docx 很多，bot 可能會很久才回覆
* 這不一定代表真的壞掉，但使用體驗上會像卡住

因此建議這樣用：

* 小量新增、修改、刪除：可直接用 Telegram `/sync`
* 大量文件同步：優先用 API `POST /rag/sync`
* 如果你改了 embedding、chunking 規則，或懷疑索引狀態不一致：改用 `/reindex`

最穩定的 API 方式如下：

```bash
curl -X POST http://127.0.0.1:8000/rag/sync
```

如果你在大量同步時看到：

```text
curl: (52) Empty reply from server
```

先優先檢查兩件事：

1. 你是不是用開發模式 `--reload` 啟動，而且同步時同時寫入了向量庫資料目錄
2. docs root 裡是否有非 UTF-8 的 `.txt` 或 `.md` 文件

目前程式已補上常見編碼容錯，也已把本地啟動腳本排除 `data/vector_store`、`data/docs`、`test_docs` 的 reload 監看。

如果你剛剛已經開著舊版 server，請先重啟一次再測。

---

## Telegram 目前沒有的指令

目前 Telegram 還沒有這些指令：

| 指令 | 目前狀態 | 說明 |
| --- | --- | --- |
| `/query` | 未提供 | Telegram 查文件統一使用 `/askdoc` |
| `/debug` | 未提供 | debug retrieval 細節目前只保留在 API `debug=true` |

也就是說，目前 Telegram 已支援一般查詢、狀態查看、全量重建與增量同步；但 debug 查詢仍需走 API。

另外，若同步檔案量非常大，仍建議優先走 API `POST /rag/sync`，不要把 Telegram 當成大批量同步入口。

---

## API 指令表

| API | 用途 | 備註 |
| --- | --- | --- |
| `GET /health` | 健康檢查 | 檢查服務是否在線 |
| `GET /config/check` | 設定檢查 | 查看目前主要設定 |
| `POST /chat` | 一般聊天 | 不查知識庫 |
| `GET /rag/status` | 查看索引狀態 | 回傳 collection 與最近 report |
| `POST /rag/reindex` | 全量重建索引 | 受 `RAG_ALLOW_REINDEX` 保護 |
| `POST /rag/sync` | 增量同步索引 | 只同步新增、修改、刪除檔案 |
| `POST /rag/query` | 查詢知識庫 | 可加 `debug=true` 看 `retrieved_chunks` |

---

## 最常用的實際範例

### Telegram 查文件

```text
/askdoc 停車位租賃契約書主要在說什麼？
```

### Telegram 看索引狀態

```text
/ragstatus
```

### Telegram 重建索引

```text
/reindex
```

### Telegram 增量同步

```text
/sync
```

### API 做增量同步

```bash
curl -X POST http://127.0.0.1:8000/rag/sync
```

### API 查文件並看 debug 資訊

```bash
curl -X POST http://127.0.0.1:8000/rag/query \
  -H 'Content-Type: application/json' \
  -d '{
    "question": "這些文件提到了什麼？",
    "top_k": 3,
    "debug": true
  }'
```

---

## 權限與設定提醒

### `TELEGRAM_ADMIN_USER_IDS` 是什麼

這不是電話號碼，而是 Telegram 的 numeric user id。

只有被列在：

```env
TELEGRAM_ADMIN_USER_IDS=123456789
```

的人，才可以在 Telegram 執行 `/reindex` 與 `/sync`。

### `RAG_ALLOW_REINDEX` 影響哪些操作

```env
RAG_ALLOW_REINDEX=true
```

打開後才允許：

* `POST /rag/reindex`
* `POST /rag/sync`
* Telegram `/reindex`
* Telegram `/sync`

---

## 簡單結論

如果你只記三件事就好：

1. Telegram 查知識庫用 `/askdoc <問題>`
2. Telegram 看狀態用 `/ragstatus`
3. 小量同步可用 Telegram `/sync`，大量同步優先用 API `POST /rag/sync`