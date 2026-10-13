# Raspberry Pi 圖形桌面部署

DeskOS 是原生 GTK 4 圖形程式，必須在 Raspberry Pi 一般使用者的桌面工作階段內啟動。請勿把它設成 root system service，也不需要啟動 Chromium。

## 安裝

```bash
sudo apt update
sudo apt install -y \
  git python3 python3-venv python3-pip python3-gi \
  gir1.2-gtk-4.0 libgtk-4-1 libgl1
sudo mkdir -p /opt/deskos-native
sudo chown "$USER:$USER" /opt/deskos-native
git clone https://github.com/Alexchen93/deskos-native.git /opt/deskos-native
cd /opt/deskos-native
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e .
```

先從 Pi 桌面終端機測試 1024 × 600 視窗：

```bash
DESKOS_WINDOWED=1 /opt/deskos-native/.venv/bin/deskos
```

確認顯示與觸控正常後，以全螢幕啟動：

```bash
/opt/deskos-native/.venv/bin/deskos
```

## 自動啟動

### Raspberry Pi OS（labwc）

在 `~/.config/labwc/autostart` 加入：

```sh
/opt/deskos-native/.venv/bin/deskos &
```

### 支援 XDG Autostart 的桌面

```bash
mkdir -p ~/.config/autostart
cp /opt/deskos-native/deploy/deskos.desktop ~/.config/autostart/deskos.desktop
```

只使用其中一種方法。登出再登入，並重新開機一次確認圖形工作階段可正常啟動。

## 復原

如果程式無法開啟，先移除所選的自動啟動項目，再從桌面終端機執行：

```bash
cd /opt/deskos-native
DESKOS_WINDOWED=1 .venv/bin/deskos
```

使用者資料預設位於 `~/.local/share/deskos`，與程式目錄分開保存。
