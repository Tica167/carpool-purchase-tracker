# 共乘與代買明細管理系統 軟體設計文件 (SDD)

## 文件資訊
| 項目 | 內容 |
|------|------|
| 文件版本 | 1.5 |
| 建立日期 | 2026年9月23日 |
| 最後更新 | 2026年9月23日 |
| 對應 PRD 版本 | 1.2 |
| 文件狀態 | 設計中 |

---

## 1. 簡介

### 1.1 專案概述
本系統供公司內部固定 5 人團體使用，用來記錄每日共乘（早/晚各 30 元）與互相代買（任何人皆可代買並指定分攤對象）的明細，並讓每人自行標記付款狀態，取代過去靠記憶對帳的方式。

### 1.2 系統目標
- 讓每筆共乘、代買紀錄在發生當下就能被快速登記。
- 依固定規則自動計算共乘金額，代買金額則由發起人手動輸入品項明細。
- 一般成員僅能看自己的共乘紀錄，車主可看所有人；代買清單所有人皆可見。
- 付款狀態由欠款人（付錢的一方）自行標記，不由收款人代為標記。
- 登入後若當月有未付款紀錄，顯示「本月尚未結算」提示。
- 車主可維護 5 人成員名單（新增/刪除）。
- 共乘與代買紀錄都可加一段簡短備註（例如：改搭公車、同事請假）。
- 代買紀錄的分攤對象可以不選任何人，代表這筆只是自己的紀錄、不需要別人付款。
- 共乘與代買整合在同一個儀表板頁面操作，頁面上方顯示登入者本人當月的統計（共乘趟數、車資小計、代買小計、應付總計）。
- 共乘日曆依中華民國政府行政機關辦公日曆表標示國定假日/補假（粉色），若該年度尚無資料則顯示提示文字，不影響其他功能運作。

### 1.3 技術選型
- 程式語言：Python 3.x
- Web 框架：**Flask + Jinja2 HTML Templates**
- 資料處理：不需要 Pandas，直接以 SQLAlchemy 查詢彙總即可
- 資料庫：本機開發用 SQLite（單一檔案 `carpool_purchase.db`）；雲端部署時可透過環境變數 `DATABASE_URL` 切換為 PostgreSQL，程式碼不需要修改（見 §8 部署與運維）
- 資料庫 ORM：SQLAlchemy
- 正式環境 Web 伺服器：**gunicorn**（取代 Flask 內建的開發用伺服器，本機開發仍用 `python app.py` 即可）
- 環境變數管理：**python-dotenv**，本機用 `.env` 檔（不進 git）提供密碼等機密設定；雲端則由 Render 環境變數提供，不透過 `.env`

---

## 2. 系統架構與運作流程

### 2.1 整體架構
```
使用者瀏覽器(手機/電腦) <-> Flask + Jinja2 Templates <-> Python 核心邏輯 <-> SQLite 資料庫
```

系統為單一 Flask 應用程式，不使用前端框架（無 React/Vue），頁面由伺服器端渲染的 HTML Templates 產生，確保手機與電腦皆可正常瀏覽。

### 2.2 運作流程詳解
1. 使用者開啟系統首頁，從固定 5 人名單中點選自己的名字（無密碼），系統將該身份存入 Session，導向 `/dashboard`。
2. `/dashboard` 是共乘與代買共用的單一儀表板頁面：上方顯示登入者本人當月統計卡片；車主額外可透過下拉選單切換查看其他成員（唯讀，僅能查看不能編輯他人紀錄）。
3. 使用者點選日曆中的日期，開啟該日的編輯面板：勾選上班/下班是否共乘、填寫備註，送出後即時儲存；同一面板也會列出當天已登記時段的付款狀態，可點擊標記已付款。
4. 使用者於「代買記錄」區塊填寫日期、單一品項名稱與金額、備註、勾選分攤對象（可不勾，代表僅自己記錄）後送出。
5. 系統將紀錄寫入 SQLite，共乘依固定規則計算金額，代買依分攤人數平均計算每人應付金額。
6. 相關成員在代買清單中看到自己被分攤的「未付款」項目，付款後自行點擊標記為「已付款」。
7. 登入或切換月份時，系統檢查當月是否仍有未付款紀錄，若有則於頁面上方顯示提示訊息。

---

## 3. 核心模組設計

### `database.py`
- **職責**：建立 SQLAlchemy engine、Session，提供 `init_db()` 初始化資料表。engine 依環境變數 `DATABASE_URL` 決定連線目標：有設定就連該網址（雲端部署時指向 PostgreSQL，並自動把 `postgres://` 轉成 SQLAlchemy 需要的 `postgresql://`）；沒設定則沿用本機 SQLite，檔案路徑以本檔案自身所在目錄組出絕對路徑（`os.path.dirname(os.path.abspath(__file__))`），不依賴程式啟動時的工作目錄，避免透過捷徑/不同路徑啟動時，資料庫被建立在錯誤的位置。
- **核心功能**：`init_db()`、`get_session()`、`get_storage_warning()`（僅雲端 PostgreSQL 適用，見 §8.2）。

### `models.py`
- **職責**：定義所有 SQLAlchemy ORM 模型（成員、共乘紀錄、代買紀錄、代買品項、代買分攤、請假/居家狀態）。
- **核心功能**：`Member`、`CarpoolRecord`（含 `note` 備註欄位）、`MemberDayStatus`（成員請假/居家狀態，`member_id`+`record_date` 唯一）、`PurchaseRecord`（含 `note` 備註欄位）、`PurchaseItem`、`PurchaseShare` 六個模型類別。

### `services.py`
- **職責**：封裝所有業務邏輯（開關單一時段的共乘紀錄、設定請假/居家狀態、新增代買與分攤、計算月結金額與統計、切換付款狀態、判斷本月是否已結算）。
- **核心功能**：
  - `set_carpool_slot(member_id, record_date, period, active, note)` — 依點選日曆的操作開/關某一天某時段的共乘紀錄，並同步備註（`active=True` 且尚未登記則新增，已登記則更新備註；`active=False` 則刪除）
  - `set_day_status(member_id, record_date, status)` — 設定/清除成員某天的請假(`leave`)/居家(`wfh`)狀態，`status=None` 代表清除；跟 `set_carpool_slot` 互不影響，可同時設定
  - `get_month_day_status(member_id, year, month)` — 回傳該成員當月的請假/居家狀態字典，供日曆標色（此函數不限本人查詢，因為該狀態全員互相可見）
  - `create_purchase_record(initiator_id, date, items, share_member_ids, note)` — `share_member_ids` 可為空清單，代表僅自己記錄、不建立任何 `PurchaseShare`
  - `toggle_payment_status(record_type, record_id, member_id)`
  - `get_month_carpool_records(member_id, year, month)` / `get_month_purchase_records(year, month)`
  - `get_member_monthly_summary(member_id, year, month)` — 回傳該成員當月的共乘趟數、車資小計、代買小計（作為分攤人應付的金額）與應付總計，供儀表板統計卡片使用
  - `get_monthly_unpaid_count(member_id)`
  - `add_member(name)` / `remove_member(member_id)`

### `holidays.py`
- **職責**：讀取中華民國政府行政機關辦公日曆表資料（依年度存成 `data/holidays/<年份>.json`，格式為 `{ISO日期: 假日名稱}`），供儀表板日曆標示國定假日使用。資料來源為行政院人事行政總處公告的官方 CSV，每年需人工下載、轉換一次（政府公告連結每年帶隨機雜湊值，無法程式化自動推算網址）。
- **核心功能**：
  - `get_holidays(year)` — 回傳該年度 `{date: 假日名稱}` 字典；若該年度無資料檔，回傳空字典（不報錯）
  - `has_holiday_data(year)` — 該年度是否已有資料檔，供畫面判斷是否顯示「尚未有資料更新」提示

### `app.py`
- **職責**：Flask 主程式，定義所有路由，串接 `services.py`，渲染對應的 HTML Template。
- **權限判斷**：
  - 車主登入需比對密碼（環境變數 `OWNER_PASSWORD`，程式碼內**沒有寫死的預設值**，避免密碼進 git；本機開發用 `.env` 檔提供，雲端部署則在 Render 環境變數設定；未設定時一律拒絕車主登入並提示尚未設定），一般成員不需要。
  - `can_edit`：目前查看的成員是否為登入者本人（只有本人能編輯自己的共乘/請假居家紀錄）。
  - `can_view_rides`：`can_edit` 或登入者是車主——只有這種情況才會撈出/顯示共乘打卡明細與金額；請假/居家狀態則不受此限制，一律撈出顯示。

---

## 4. 資料庫設計

### 4.1 資料庫選型
本機開發用 SQLite，單一檔案資料庫，無需安裝伺服器，適合 5 人內部小工具的規模。雲端部署（見 §8）改用 PostgreSQL（Neon 免費方案），因為部署平台的容器硬碟通常不持久（重啟/重新部署會清空），SQLite 檔案放上去會遺失資料；改用外部管理的 PostgreSQL 才能長期保留歷史紀錄。兩者的資料表結構完全相同，切換只靠 `DATABASE_URL` 環境變數，不需要改程式碼。

### 4.2 資料表設計

**Table: `members`**
| 欄位名稱 | 資料型態 | 說明 | 備註 |
|----------|----------|------|------|
| id | INTEGER | 唯一識別碼 | 主鍵，自動遞增 |
| name | TEXT | 成員姓名 | 不可重複 |
| is_owner | BOOLEAN | 是否為車主 | 預設 False |

**Table: `carpool_records`**
| 欄位名稱 | 資料型態 | 說明 | 備註 |
|----------|----------|------|------|
| id | INTEGER | 唯一識別碼 | 主鍵，自動遞增 |
| member_id | INTEGER | 登記人（外鍵） | 參照 `members.id` |
| record_date | DATE | 搭乘日期 | |
| period | TEXT | 時段：`morning` / `evening` | 同一天同一時段僅能登記一次 |
| amount | INTEGER | 金額 | 固定 30 |
| is_paid | BOOLEAN | 是否已付款 | 預設 False |
| note | TEXT | 備註 | 可為 NULL |
| created_at | DATETIME | 建立時間 | |

**Table: `member_day_status`**
| 欄位名稱 | 資料型態 | 說明 | 備註 |
|----------|----------|------|------|
| id | INTEGER | 唯一識別碼 | 主鍵，自動遞增 |
| member_id | INTEGER | 成員（外鍵） | 參照 `members.id` |
| record_date | DATE | 日期 | |
| status | TEXT | 狀態：`leave`（請假）/ `wfh`（居家） | |

> `(member_id, record_date)` 唯一約束，同一人同一天只能有一種狀態。此表**不受共乘紀錄的隱私規則限制**——所有成員查詢任何人的這張表都不需要權限檢查，因為請假/居家狀態設計為團隊互相可見。

**Table: `purchase_records`**
| 欄位名稱 | 資料型態 | 說明 | 備註 |
|----------|----------|------|------|
| id | INTEGER | 唯一識別碼 | 主鍵，自動遞增 |
| initiator_id | INTEGER | 代買發起人（外鍵） | 參照 `members.id` |
| record_date | DATE | 代買日期 | |
| note | TEXT | 備註 | 可為 NULL |
| created_at | DATETIME | 建立時間 | |

**Table: `purchase_items`**
| 欄位名稱 | 資料型態 | 說明 | 備註 |
|----------|----------|------|------|
| id | INTEGER | 唯一識別碼 | 主鍵，自動遞增 |
| purchase_record_id | INTEGER | 所屬代買紀錄（外鍵） | 參照 `purchase_records.id` |
| item_name | TEXT | 品項名稱 | 例：飲料 |
| amount | INTEGER | 品項金額 | |

**Table: `purchase_shares`**
| 欄位名稱 | 資料型態 | 說明 | 備註 |
|----------|----------|------|------|
| id | INTEGER | 唯一識別碼 | 主鍵，自動遞增 |
| purchase_record_id | INTEGER | 所屬代買紀錄（外鍵） | 參照 `purchase_records.id` |
| member_id | INTEGER | 分攤成員（外鍵） | 參照 `members.id` |
| share_amount | INTEGER | 該成員應付金額 | 品項總金額 ÷ 分攤人數（四捨五入） |
| is_paid | BOOLEAN | 是否已付款 | 預設 False，由該成員本人標記 |

> **設計假設**：代買總金額由分攤人數平均分攤，發起人（先墊錢者）本身不列入 `purchase_shares`（因為他已經付出去了，不欠自己錢）。此假設未在 PRD 中明確定義平均分攤規則，若實際使用後發現需要「不均分」的情境，可在下一輪迭代調整 `share_amount` 的計算方式。
>
> **v1.1 更新**：`share_member_ids` 允許為空清單——此時不建立任何 `PurchaseShare`，代表這筆代買純粹是發起人自己的紀錄（例如個人消費），不需要任何人分攤付款。

### 4.3 資料關聯
```
members 1 ──── * carpool_records
members 1 ──── * member_day_status
members 1 ──── * purchase_records (as initiator)
members 1 ──── * purchase_shares (as sharer)
purchase_records 1 ──── * purchase_items
purchase_records 1 ──── * purchase_shares
```

### 4.4 假日資料（非資料庫，檔案儲存）
國定假日資料**不存放在 SQLite**，而是以年度為單位存成 JSON 檔案 `data/holidays/<年份>.json`（格式：`{"YYYY-MM-DD": "假日名稱"}`），由 `holidays.py` 讀取。這樣設計是因為：
- 假日資料是每年由政府公告一次的靜態參考資料，不隨使用者操作變動，不需要放進交易型資料庫。
- 方便每年直接下載新的 CSV 轉換覆蓋，不需要寫資料庫遷移或管理介面。

---

## 5. 使用者介面與互動規劃

### 5.1 頁面結構
| 頁面 | 路徑 | 說明 |
|------|------|------|
| 選擇身份 | `/` | 列出 5 位成員供點選登入；車主額外顯示密碼輸入框 |
| 共乘與代買儀表板 | `/dashboard` | 單一整合頁面：本人本月統計卡片、共乘日曆（點日期開編輯面板）、代買記錄（快速新增＋清單）；**所有人**皆可透過下拉選單切換查看任何成員（查看他人時，共乘明細受 `can_view_rides` 權限限制，請假/居家狀態不受限） |
| 成員管理 | `/members`（僅車主可見） | 新增/刪除成員 |

### 5.2 視覺風格
全站採用深色「簡潔文青」風格：深色背景（`--bg: #17181a`）、卡片式版面（圓角、細邊框），強調色使用 teal（上班共乘）、blue（下班共乘）、orange（備註/總計金額）、pink（國定假日）、**purple（請假）、yellow（居家）** 區分不同語意，統一定義在 `base.html` 的 CSS 變數中，方便日後調整配色而不用逐頁修改。

### 5.3 核心互動流程
1. 首頁點選姓名 → 一般成員直接登入；車主需輸入密碼，錯誤則停在登入頁顯示「密碼錯誤」。登入成功導向 `/dashboard`，若當月有未付款紀錄，頁面上方顯示提示區塊「本月尚未結算」。
2. 儀表板頂部：若 `can_view_rides`（查看自己，或車主查看任何人）為真，顯示當月統計卡片（共乘趟數、車資小計、代買小計、應付總計）；否則顯示提示文字，說明共乘明細屬隱私僅本人與車主可查看。
3. 「查看成員」下拉選單開放給所有人（不限車主），可切換查看任何成員的日曆。
4. 共乘日曆以 ISO 8601 週別呈現整月：
   - 若 `can_view_rides`：每天格子以圓點標示是否有上班/下班共乘、是否有備註。
   - 每天格子一律顯示（不受 `can_view_rides` 限制）：若當天是政府公告的國定假日/補假，以粉色標示並顯示假日名稱；若該成員當天標記請假，以紫色標示「請假」；若標記居家，以黃色標示「居家」（假日、請假、居家三者互斥顯示，優先順序：假日 > 請假/居家）。
   - 點擊日期在下方開啟面板：
     - 若查看對象是本人：顯示請假/居家狀態下拉選單（正常／請假／居家）+ 儲存按鈕；顯示可勾選的上班/下班切換框、備註輸入框、「儲存共乘」按鈕（兩者互不影響，可同時設定）；已登記的時段另外顯示付款狀態按鈕（僅本人可點擊標記已付款）。
     - 若查看對象是他人：面板標示「唯讀」。一律顯示該成員的請假/居家狀態文字；若 `can_view_rides`（車主查看）則額外顯示共乘明細與付款狀態文字，否則顯示「共乘打卡明細僅本人與車主可見」。
   - 若該年度尚無假日資料檔（`holidays.has_holiday_data(year)` 為 False）：在日曆卡片與點選日期的面板都顯示提示文字「尚未有 {{年度}} 年度政府行政機關辦公日曆表資料更新」，其餘功能不受影響。
5. 代買記錄區塊提供快速新增表單（日期、品項、金額、備註、分攤對象——分攤對象可不選，代表僅自己記錄），送出後即時出現在下方清單；清單所有人皆可見，分攤人若是目前登入者可點擊標記已付款。

---

## 6. API 設計 / 功能函數

| 路由 | 方法 | 功能 | 對應 service 函數 |
|------|------|------|--------------------|
| `/` | GET | 顯示身份選擇頁 | - |
| `/login/<member_id>` | POST | 設定 Session 身份；若為車主須比對 `password` 表單欄位與 `OWNER_PASSWORD` | - |
| `/dashboard` | GET | 依 `year`/`month`/`view_member_id`/`date` 查詢參數顯示儀表板（統計卡片、日曆、代買清單） | `get_member_monthly_summary()`、`get_month_carpool_records()`、`get_month_day_status()`、`get_month_purchase_records()`、`get_holidays()`、`has_holiday_data()` |
| `/dashboard/carpool/save` | POST | 儲存選定日期的上班/下班開關與備註 | `set_carpool_slot()` |
| `/dashboard/status/save` | POST | 儲存選定日期的請假/居家狀態（限本人） | `set_day_status()` |
| `/dashboard/carpool/<id>/pay` | POST | 標記共乘紀錄已付款（限本人） | `toggle_payment_status()` |
| `/dashboard/purchase/add` | POST | 新增一筆代買紀錄（單一品項）與分攤（分攤對象可為空） | `create_purchase_record()` |
| `/dashboard/purchase/share/<id>/pay` | POST | 標記分攤款已付款（限本人） | `toggle_payment_status()` |
| `/members` | GET/POST | 車主查看/新增成員（僅車主） | `add_member()` |
| `/members/<id>/delete` | POST | 車主刪除成員（僅車主） | `remove_member()` |

---

## 7. 錯誤處理策略

| 錯誤情境 | 處理策略 | UI 呈現 |
|----------|----------|----------|
| 同一天同時段重複登記共乘 | 後端檢查後拒絕寫入 | 顯示「該時段已登記過」提示 |
| 非本人嘗試修改/刪除他人紀錄 | 後端比對 Session 身份與紀錄擁有者，拒絕操作 | 回傳 403，顯示「無權限」提示 |
| 非車主嘗試存取成員管理頁 | 後端檢查 Session 身份是否為車主 | 導回首頁並顯示提示 |
| 車主查看他人紀錄時嘗試送出編輯表單 | 頁面上不渲染編輯表單，僅顯示唯讀文字 | 面板標示「唯讀」 |
| 查看的年度沒有假日資料檔 | `has_holiday_data()` 回傳 False，日曆仍正常顯示，只是不標示假日 | 顯示「尚未有資料更新」提示，不阻斷其他功能 |
| 車主登入密碼錯誤 | 後端比對失敗，不建立 Session | 停留在登入頁，顯示「密碼錯誤」 |
| 非本人且非車主查看他人的共乘明細 | 後端直接不撈取該成員的共乘紀錄與統計（`can_view_rides=False` 時回傳空資料），非僅前端隱藏 | 顯示「共乘打卡明細僅本人與車主可見」，但仍顯示該成員的請假/居家狀態 |

---

## 8. 部署與運維

### 8.1 本機開發
```bash
"venv\Scripts\python.exe" app.py
```
不設定 `DATABASE_URL` 時，直接用本機 SQLite 檔案 `carpool_purchase.db`，適合單人開發測試，或單機使用不需要多人跨網路連線的情境（雙擊 `啟動系統.bat`）。

### 8.2 雲端部署（多成員跨網路使用）
因為使用者不一定都在同一個內部網路，系統改為部署到雲端讓大家都能連到。採用的組合：

| 用途 | 服務 | 說明 |
|------|------|------|
| 程式碼託管 | GitHub（private repo） | Render 從這裡讀取程式碼自動部署 |
| 應用程式主機 | Render（免費 Web Service） | 執行 `gunicorn app:app --bind 0.0.0.0:$PORT`（見 `Procfile`） |
| 資料庫 | Neon（免費 PostgreSQL，永久不過期） | 透過 `DATABASE_URL` 環境變數連接 |

**環境變數設定（在 Render 後台設定，不寫進程式碼或 git）：**
| 變數名稱 | 說明 | 範例值 |
|----------|------|--------|
| `DATABASE_URL` | Neon 提供的連線字串 | `postgresql://user:password@xxx.neon.tech/dbname?sslmode=require` |
| `SECRET_KEY` | Flask session 加密金鑰，正式環境務必自訂 | 任意一串隨機亂碼 |
| `OWNER_PASSWORD` | 車主登入密碼；程式碼沒有寫死預設值，未設定時車主無法登入 | 自訂的密碼字串 |

**本機開發**：可在專案根目錄建立 `.env` 檔（已被 `.gitignore` 排除，不會進 git）放同樣的變數，`app.py` 啟動時會透過 `python-dotenv` 自動讀取，不需要每次手動 `set` 環境變數。

**為什麼不能直接把 SQLite 檔案放上 Render 免費方案：** Render 免費 Web Service 的容器硬碟不持久，服務閒置 15 分鐘會睡眠、下次連線喚醒或每次重新部署都會清空檔案系統，SQLite 資料庫檔案會跟著消失。Render 自己的免費 PostgreSQL 則是 30 天會過期（14 天寬限期後刪除）。因此改接外部、免費且不過期的 Neon PostgreSQL 來保存資料。

**已知限制：** Render 免費方案閒置 15 分鐘會睡眠，之後第一個連線的人要等約 1 分鐘喚醒，這是正常現象。

### 8.3 資料庫容量監控
Neon 免費方案空間上限約 0.5GB。`database.py` 的 `get_storage_warning()` 透過 PostgreSQL 內建的 `pg_database_size(current_database())` 查詢目前用量，剩餘容量低於 0.1GB 時回傳提醒文字；`app.py` 每次請求都會檢查（透過 `inject_common()` context processor），畫面上方顯示紅色警示 banner。這個機制**只提醒、不會自動刪除任何資料**，只在連 PostgreSQL 時生效，本機 SQLite 模式沒有這個限制、不會檢查。以目前 5 人團體的資料量估算，實際觸發這個警示大概需要數百年，屬於安全網性質，非急迫風險。

---

## 9. 實作路徑 (Implementation Roadmap)

**此章節為 AI Coding Agent 的執行指南，請依序完成每個階段。**

### 階段 1：環境建置與依賴安裝
```bash
mkdir carpool-purchase-tracker
cd carpool-purchase-tracker
python -m venv venv
# Windows: .\venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
```

`requirements.txt`：
```
flask
SQLAlchemy
gunicorn
psycopg2-binary
python-dotenv
```
（`gunicorn`、`psycopg2-binary` 是雲端部署才會用到；本機開發用 SQLite 不會實際載入 psycopg2；`python-dotenv` 用於本機讀取 `.env`）

```bash
pip install -r requirements.txt
```

`.gitignore`：
```
venv/
__pycache__/
*.pyc
*.db
.env
```

`Procfile`（供 Render 等平台辨識啟動指令）：
```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

### 階段 2：資料庫模組開發
- 建立 `models.py`：定義 `Member`、`CarpoolRecord`、`PurchaseRecord`、`PurchaseItem`、`PurchaseShare` 五個 SQLAlchemy 模型（依第 4 章 Schema）。
- 建立 `database.py`：建立 engine（`sqlite:///carpool_purchase.db`）、`init_db()` 建表、`get_session()`。
- 於 `init_db()` 中，若 `members` 表為空，可預先插入 1 位車主 + 4 位一般成員的初始名單（實際姓名由使用者於開發時提供或於成員管理頁補齊）。

### 階段 3：核心業務邏輯開發
依序實作 `services.py`：
1. `set_carpool_slot()` / `toggle_payment_status()` — 含權限檢查（僅本人）。
2. `create_purchase_record()` — 寫入 `purchase_records` + `purchase_items` + 依分攤人數計算 `purchase_shares.share_amount`（`share_member_ids` 可為空）。
3. `get_member_monthly_summary()` / `get_month_carpool_records()` / `get_month_purchase_records()` / `get_monthly_unpaid_count()` — 供儀表板統計卡片與「本月尚未結算」提示使用。
4. `add_member()` / `remove_member()` — 車主專用，刪除成員不刪除其歷史紀錄。

### 階段 4：使用者介面開發
- 建立 `app.py`：定義第 6 章所有路由，使用 Flask `session` 儲存目前登入的 `member_id`。
- 建立 `templates/` 目錄，依第 5 章頁面結構建立對應的 `.html` 檔（`login.html`、`dashboard.html`、`members.html`），共用一個 `base.html` 版面（深色簡潔文青風、手機/電腦皆可讀的響應式 CSS）。
- 所有表單提交後導回儀表板頁（保留 `year`/`month`/`date` 查詢參數），並在畫面上以文字/圓點提示操作結果。

### 階段 5：測試與驗證
功能測試項目：
- 各成員可選擇身份登入並看到對應權限的畫面。
- 共乘紀錄：日曆點選開關上班/下班、重複開啟不報錯、備註儲存、標記已付款皆正確運作。
- 代買紀錄：品項輸入、多人分攤金額計算正確、分攤對象留空時僅自己記錄不建立分攤、清單所有人可見、分攤人可各自標記已付款。
- 車主切換查看其他成員時為唯讀，無法送出編輯表單。
- 車主可新增/刪除成員，一般成員無法存取成員管理頁。
- 當月有未付款紀錄時，登入首頁會顯示提示；全部結清後提示消失。

錯誤處理測試：依第 7 章逐項驗證。

### 階段 6：文件與部署
- 建立 `README.md`，說明如何啟動系統。
- 本機最終確認：
```bash
# 啟動應用
python app.py

# 開啟瀏覽器訪問
# http://localhost:5050
```
- 若需要跨網路多人使用，依 §8 部署與運維：推上 GitHub → 在 Render 建立 Web Service（連 GitHub repo，環境變數設定 `DATABASE_URL`／`SECRET_KEY`）→ 用 Neon 建立永久 PostgreSQL 資料庫並取得連線字串。

**預期產出：** 5 位成員皆可透過手機或電腦瀏覽器（無論是否在同一網路），完成共乘與代買明細的登記、查看與付款狀態標記，系統可交付日常使用。
