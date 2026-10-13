# DeskOS Native

DeskOS Native 是為 **Raspberry Pi 直接連接觸控螢幕**設計的本機資訊與監控介面。它以 Python、GTK 4 與 PyGObject 實作，不需要瀏覽器、不啟動 HTTP Server，也不會開放網路監聽埠。

目前介面針對 **1024 × 600** 顯示器設計，採用精簡文字導覽、清楚的資料列與單一暖色點綴。從 v0.4 起，核心只保留首頁、應用程式管理與設定；時鐘、天氣、快訊、專注及裝置監測都以可加入／移除的小 App 運作。

## 特色

- **小 App 平台**：內建 App 與第三方外掛使用相同的登錄、生命週期與事件介面。
- **應用程式管理**：直接從觸控介面加入或移除已探索的小 App，不需重新啟動。
- **原生設定**：在螢幕上調整天氣地點、RSS、專注／休息時間、時制與低功耗 3D。
- **每日首頁**：時間、日期、即時天氣、專注進度、系統狀態與最新科技快訊；來源 App 移除後摘要會自動隱藏。
- **本機時鐘**：大字時間、日期、年度週次與當日／年度進度。
- **天氣資訊**：透過 Open-Meteo 取得溫度、體感溫度、降雨機率與天氣狀態；網路中斷時保留最後一次成功資料。
- **科技快訊**：讀取 RSS／Atom feed，以適合觸控閱讀的清單呈現。
- **專注計時**：以實際時間戳記計算，不因畫面更新或程式短暫卡頓而失準；進度會寫入 SQLite。
- **裝置監測**：顯示 CPU、記憶體、磁碟、溫度、網路與運行時間。
- **Raspberry Pi 4 模型**：使用原生 `Gtk.GLArea` 顯示 3D 模型；不支援 OpenGL 時自動切換靜態預覽。
- **觸控優先**：主要操作區保留至少 48 px 的觸控高度。
- **本機優先**：無 WebView、無內建網站、無遠端管理介面；使用者資料保存在 Pi 本機。

## 小 App 與外掛

DeskOS 內建的時鐘、天氣、科技快訊、專注與裝置監測，都可以在「應用程式」頁加入或移除。移除只會停用並從導覽列卸載，不會刪除該 App 的 SQLite 設定；重新加入即可恢復。

第三方外掛是已安裝到同一 Python 環境、並宣告 `deskos.plugins` entry point 的 Python 套件。例如外掛套件完成可信來源審查後，可安裝至 DeskOS virtual environment：

```bash
cd /opt/deskos-native
.venv/bin/pip install /path/to/trusted-plugin
```

重新啟動 DeskOS 後，外掛會出現在「應用程式」頁，再由使用者決定是否加入。DeskOS 不會自行下載套件、執行 `pip` 或執行 shell 指令。完整 API、生命週期與安全界線請參考 [`docs/PLUGIN_SYSTEM.md`](docs/PLUGIN_SYSTEM.md)。

## 系統需求

- Raspberry Pi OS 64-bit（建議 Bookworm 或更新版本）
- Raspberry Pi 4／5
- 1024 × 600 顯示器（其他解析度尚未完整驗證）
- Python 3.11+
- GTK 4、PyGObject 與可用的 X11 或 Wayland 圖形桌面
- 網路連線（僅天氣與 RSS 更新需要）

## 快速安裝

DeskOS 必須在一般桌面使用者的圖形工作階段執行，**不要用 root 啟動程式**。

### 1. 安裝系統套件

```bash
sudo apt update
sudo apt install -y \
  git python3 python3-venv python3-pip python3-gi \
  gir1.2-gtk-4.0 libgtk-4-1 libgl1
```

### 2. 下載程式

```bash
sudo mkdir -p /opt/deskos-native
sudo chown "$USER:$USER" /opt/deskos-native
git clone https://github.com/Alexchen93/deskos-native.git /opt/deskos-native
cd /opt/deskos-native
```

### 3. 建立 Python 環境

PyGObject 由 Raspberry Pi OS 提供，因此 virtual environment 需要讀取系統套件：

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e .
```

### 4. 第一次啟動

先以視窗模式確認 GTK、字型與觸控操作：

```bash
cd /opt/deskos-native
DESKOS_WINDOWED=1 .venv/bin/deskos
```

確認正常後，使用全螢幕模式：

```bash
cd /opt/deskos-native
.venv/bin/deskos
```

## 開機自動啟動

只選擇一種方法，避免程式重複啟動。

### Raspberry Pi OS（labwc）

```bash
mkdir -p ~/.config/labwc
printf '/opt/deskos-native/.venv/bin/deskos &\n' >> ~/.config/labwc/autostart
```

登出再登入，或重新開機測試。

### 支援 XDG Autostart 的桌面

```bash
mkdir -p ~/.config/autostart
cp /opt/deskos-native/deploy/deskos.desktop ~/.config/autostart/deskos.desktop
```

## 設定

從側邊導覽進入「設定」，可直接調整：

- 天氣顯示名稱、緯度與經度
- 一個或多個 RSS／Atom URL
- 專注與休息分鐘數
- 12／24 小時制
- 低功耗 3D 模式（重新啟動後套用）

設定儲存在 `~/.local/share/deskos` 的 SQLite 資料庫。開發或診斷時仍可使用：

| 變數 | 預設值 | 說明 |
| --- | --- | --- |
| `DESKOS_WINDOWED` | `0` | 設為 `1` 時以 1024 × 600 視窗開啟 |
| `DESKOS_DATA_DIR` | `~/.local/share/deskos` | SQLite 與快取資料目錄 |

## 更新

```bash
cd /opt/deskos-native
git pull --ff-only
.venv/bin/pip install -e .
```

更新後重新登入桌面，或先關閉舊程序再重新啟動。

## 疑難排解

### 程式顯示需要圖形工作階段

若看到 `DeskOS requires an active graphical session`，請從 Pi 桌面內的終端機啟動，而不是從未轉送顯示環境的純 SSH shell 啟動。

### OpenGL 無法啟用

裝置頁會自動切換成靜態 Raspberry Pi 圖片，系統監測仍可正常運作。先確認顯示驅動與 `libgl1` 已安裝。

### 自動啟動後畫面異常

先移除或註解 autostart 指令，再從桌面終端機用視窗模式檢查：

```bash
cd /opt/deskos-native
DESKOS_WINDOWED=1 .venv/bin/deskos
```

### 清除本機狀態

DeskOS 的資料預設位於：

```text
~/.local/share/deskos
```

先關閉 DeskOS，再備份或移走該目錄即可重建乾淨狀態。

## 開發與測試

```bash
cd /opt/deskos-native
.venv/bin/pip install -e '.[dev]'
.venv/bin/ruff format --check src tests
.venv/bin/ruff check src tests
.venv/bin/pytest
```

目前 52 項測試涵蓋設定、SQLite、天氣與 RSS 快取、專注計時、系統監測格式、3D 模型解析、外掛登錄／探索／持久化及 1024 × 600 UI 合約。

## 架構

- `src/deskos/plugins/`：不可變外掛 API、登錄、entry point 探索與啟用狀態
- `src/deskos/ui/`：GTK 核心頁面、動態導覽、CSS 與 3D 模型檢視器
- `src/deskos/services/`：天氣、RSS、專注、SQLite 與系統監測
- `src/deskos/core/`：不可變資料模型與服務介面
- `assets/models/`：Raspberry Pi 4 GLB 與靜態備援圖片
- `deploy/`：圖形桌面安裝與自動啟動範例
- `tests/`：服務與 UI 合約測試

更完整的設計界線請參考 [`ARCHITECTURE.md`](ARCHITECTURE.md)；外掛開發請參考 [`docs/PLUGIN_SYSTEM.md`](docs/PLUGIN_SYSTEM.md)；後續 Weather Forecast、Calendar、Focus Insights、System History、Diagnostics 與硬體 App 規劃收錄於 [`docs/ROADMAP.md`](docs/ROADMAP.md)。

## 安全界線

DeskOS 僅讀取本機系統狀態，並主動連線至設定的 Open-Meteo／RSS 來源。它不提供 HTTP API、不開放監聽埠、不執行任意外部命令，也不包含遠端控制功能。
