# 共乘與代買明細管理系統

供公司內部固定 5 人團體使用，記錄每日共乘（早/晚各 30 元）與互相代買的明細，並讓每人自行標記付款狀態。

## 啟動方式

```bash
# 建立虛擬環境（若尚未建立）
python -m venv venv

# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# 安裝依賴
pip install -r requirements.txt

# 啟動系統
python app.py
```

啟動後開啟瀏覽器訪問：`http://localhost:5050`

首次啟動會自動建立 SQLite 資料庫 `carpool_purchase.db`，並預先建立 5 位成員：車主 Hugo，以及 Tina、Blue、Mango、Rennie。

## 修改成員名單

登入車主（Hugo）帳號後，進入「成員管理」頁面可以新增/刪除成員：
- 若要更換其中一位成員的姓名，直接刪除舊成員、新增新姓名即可；但這樣會讓舊成員過去的歷史紀錄留在資料庫中（不會被刪除，只是不再顯示於登入名單）。若想「改名但保留歷史紀錄的關聯」，需要直接修改資料庫 `members` 表對應那一列的 `name` 欄位（尚無介面功能）。
- 若團體中車主人選需要變動，目前需直接修改資料庫中 `members` 表的 `is_owner` 欄位（尚無介面功能）。

## 專案文件

- [PRD.md](./PRD.md)：產品需求文件
- [SDD.md](./SDD.md)：軟體設計文件
- [TASK.md](./TASK.md)：開發任務清單
- [CHANGELOG.md](./CHANGELOG.md)：變更紀錄
