# 開發任務清單 (TASK.md)

> 由 prd-sdd-studio 依 SDD「實作路徑」規劃。commit 時對應前綴 `[TASK-NNN]`。
> 狀態圖例：⬜ 待辦 ｜ 🔵 進行中 ｜ ✅ 完成 ｜ ⏸ 阻塞

## 進度總覽
- 總任務數：6
- 已完成：6 / 6
- 目前進行：無（全部完成）

## 任務清單

### TASK-001 — 環境建置與專案初始化
- **狀態**：✅ 完成
- **對應 SDD**：§8 階段 1（環境建置與依賴安裝）
- **內容**：
  - 建立 `requirements.txt`（`flask`、`SQLAlchemy`）
  - 建立 `.gitignore`（`venv/`、`__pycache__/`、`*.pyc`、`*.db`）
  - 建立專案目錄結構（`templates/` 等）
- **驗收**：`pip install -r requirements.txt` 可成功安裝，專案骨架建立完成
- **產出檔案**：`requirements.txt`, `.gitignore`

### TASK-002 — 資料庫模組開發
- **狀態**：✅ 完成
- **對應 SDD**：§3 核心模組設計（database.py、models.py）、§4 資料庫設計
- **內容**：
  - `models.py`：定義 `Member`、`CarpoolRecord`、`PurchaseRecord`、`PurchaseItem`、`PurchaseShare` 五個 SQLAlchemy 模型
  - `database.py`：建立 engine（`sqlite:///carpool_purchase.db`）、`init_db()`、`get_session()`；`init_db()` 內若 `members` 為空，預先插入 1 位車主 + 4 位一般成員
- **驗收**：執行 `python -c "from database import init_db; init_db()"` 可成功建表並寫入初始 5 位成員，無 import/型別錯誤
- **產出檔案**：`models.py`, `database.py`

### TASK-003 — 核心業務邏輯開發
- **狀態**：✅ 完成
- **對應 SDD**：§3 核心模組設計（services.py）、§6 API 設計對應函數
- **內容**：於 `services.py` 實作：
  - `create_carpool_record()`（含同天同時段重複登記檢查、固定 30 元）
  - `delete_carpool_record()` / `toggle_payment_status()`（含僅本人可操作的權限檢查）
  - `create_purchase_record()`（寫入品項明細 + 依分攤人數平均計算 `purchase_shares.share_amount`）
  - `get_monthly_unpaid_count()`（供首頁「本月尚未結算」提示）
  - `add_member()` / `remove_member()`（車主專用，刪除成員不影響其歷史紀錄）
- **驗收**：對照 PRD 驗收標準（FR-002、FR-004、FR-005、FR-007、FR-008），以已知輸入手動呼叫每個函數一次，確認回傳/寫入結果正確
- **產出檔案**：`services.py`

### TASK-004 — 使用者介面開發
- **狀態**：✅ 完成
- **對應 SDD**：§5 使用者介面與互動規劃、§6 API 設計、§8 階段 4
- **內容**：
  - `app.py`：實作 §6 所列所有路由，使用 Flask `session` 儲存登入身份
  - `templates/base.html`：共用版面（含手機/電腦皆可讀的簡單響應式 CSS）
  - `templates/login.html`, `carpool.html`, `carpool_new.html`, `purchase.html`, `purchase_new.html`, `members.html`
- **驗收**：`python app.py` 可啟動，`http://localhost:5000` 可開啟身份選擇頁，無 import/執行錯誤
- **產出檔案**：`app.py`, `templates/base.html`, `templates/login.html`, `templates/carpool.html`, `templates/carpool_new.html`, `templates/purchase.html`, `templates/purchase_new.html`, `templates/members.html`

### TASK-005 — 整合測試與錯誤處理驗證
- **狀態**：✅ 完成
- **對應 SDD**：§7 錯誤處理策略、§8 階段 5
- **內容**：依 PRD 驗收標準（第 11.2 節）與 SDD §7 錯誤情境，實際操作驗證：
  1. 5 位成員皆可選擇身份登入，權限對應正確（一般成員只看自己共乘紀錄；車主看全部；代買清單所有人可見）
  2. 共乘：新增、重複登記阻擋、刪除、標記已付款皆正確
  3. 代買：多品項輸入、多人分攤金額計算正確、分攤人各自標記已付款正確
  4. 車主可新增/刪除成員，一般成員無法存取 `/members`
  5. 當月有未付款紀錄時首頁顯示提示，全部結清後提示消失
- **驗收**：以上 5 項情境皆實際操作驗證通過
- **產出檔案**：無新增檔案（驗證既有功能）

### TASK-006 — 文件與部署
- **狀態**：✅ 完成
- **對應 SDD**：§8 階段 6
- **內容**：建立 `README.md`，說明系統用途、啟動方式（`python app.py`）、預設成員名單如何調整
- **驗收**：依 README 步驟可從零啟動系統並成功存取
- **產出檔案**：`README.md`
