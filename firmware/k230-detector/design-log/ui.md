# UI baseline cho Yahboom K230

Tài liệu này mô tả cách viết UI theo firmware đang chạy trong `k230-firmware/`. Đây là baseline của dự án: khi cần tạo app hoặc page mới, ưu tiên sao chép cấu trúc của app gần nhất trong firmware và giữ nguyên contract với `ybMain`, LVGL và `PipeLine`.

## Nền tảng

- GUI: LVGL 8.3 trên MicroPython.
- Màn hình: `640 × 480`.
- System shell chiếm vùng phía trên; content của app dùng vùng `640 × 420`, căn xuống đáy màn hình.
- Entry point `/sdcard/main.py` gọi `ybMain.main.start()`.
- System shell và `AppManager` thuộc module `ybMain` của firmware.
- App người dùng nằm trong `/sdcard/apps/<app_name>/`.

## Kiến trúc UI

```text
ybMain.main.start()
└── AppManager
    ├── config / text_config
    ├── PipeLine dùng chung
    ├── UART, Wi-Fi, buzzer, RGB, recorder
    └── apps/<app_name>/app.py
        └── App(BaseApp)
            ├── initialize()
            ├── deinitialize()
            └── các Page
```

`AppManager` sở hữu các dịch vụ cấp hệ thống. App nhận và giữ reference thay vì tự tạo lại camera pipeline hoặc driver phần cứng:

```python
self.app_manager = app_manager
self.config = app_manager.config
self.text_config = app_manager.text_config
self.pl = app_manager.pl
self.uart = app_manager.uart
```

Chỉ lấy những dependency app thực sự sử dụng.

## Contract của một app

Mỗi app export class `App` kế thừa `ybMain.base_app.BaseApp`:

```python
import lvgl as lv
from ybMain.base_app import BaseApp


class App(BaseApp):
    def __init__(self, app_manager):
        self.app_manager = app_manager
        self.config = app_manager.config
        self.text_config = app_manager.text_config
        self.pl = app_manager.pl
        self.content = None

        name = self.text_config.get_section("System")["MyApp"]
        super().__init__(app_manager, name=name, icon=self._load_icon())

    def _load_icon(self):
        try:
            with open("/sdcard/apps/my_app/icon.png", "rb") as file:
                data = file.read()
            return lv.img_dsc_t({"data_size": len(data), "data": data})
        except Exception:
            return None

    def initialize(self):
        self.content = lv.obj(self.screen)
        self.content.set_size(lv.pct(100), 420)
        self.content.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.content.set_style_border_width(0, 0)
        self.content.set_style_radius(0, 0)
        self.build_ui()

    def build_ui(self):
        label = lv.label(self.content)
        label.set_text("My App")
        label.center()

    def deinitialize(self):
        if self.content:
            self.content.delete()
            self.content = None
```

Các thành phần bắt buộc cần giữ:

- Tên class là `App`.
- Constructor nhận `app_manager`.
- Gọi `BaseApp.__init__()` với name và icon.
- Dựng UI trong `initialize()`.
- Thu hồi UI, timer và tài nguyên riêng trong `deinitialize()`.
- Tạo widget dưới `self.screen` hoặc container con của nó.

## Layout chuẩn của app nhóm chức năng

Các app AI, nhận dạng màu, mã và đồ họa dùng master–detail layout:

- Container gốc: `640 × 420`.
- Danh mục bên trái: 30% chiều rộng.
- Detail panel bên phải: 70% chiều rộng.
- Container dùng `lv.FLEX_FLOW.ROW`.
- Danh mục dùng `lv.FLEX_FLOW.COLUMN` và scroll dọc.
- Nút đang chọn dùng `lv.STATE.CHECKED`.
- Khi đổi page, gọi `detail_panel.clean()` rồi page hiện tại dựng lại widget.

```python
flex = lv.obj(self.content)
flex.set_size(lv.pct(100), lv.pct(100))
flex.set_flex_flow(lv.FLEX_FLOW.ROW)

self.category_list = lv.list(flex)
self.category_list.set_size(lv.pct(30), lv.pct(100))
self.category_list.set_flex_flow(lv.FLEX_FLOW.COLUMN)
self.category_list.set_scroll_dir(lv.DIR.VER)

self.detail_panel = lv.obj(flex)
self.detail_panel.set_size(lv.pct(70), lv.pct(100))
self.detail_panel.set_flex_flow(lv.FLEX_FLOW.COLUMN)
```

Menu nên khai báo theo thứ tự hiển thị và map sang page key:

```python
self.menu_order = [
    ("Detection", "detection"),
    ("Recognition", "recognition"),
]
self.category_mapping = dict(self.menu_order)
self.pages = {
    "detection": DetectionPage(self, self.detail_panel),
    "recognition": RecognitionPage(self, self.detail_panel),
}
```

## Base page cho AI demo

Firmware dùng một base page để thống nhất banner, nút Start, title và description. Page con chỉ cung cấp nội dung và callback:

```python
class BaseDemoPage:
    def __init__(self, app, detail_panel, config, text_config):
        self.app = app
        self.detail_panel = detail_panel
        self.config = config
        self.text_config = text_config

    def display(self):
        self.detail_panel.clean()
        # Tạo banner, nút Start, title và description tại đây.

    def get_image_source(self):
        return None

    def get_title(self):
        return "Demo"

    def get_description(self):
        return ""

    def get_button_text(self):
        return "Start"

    def on_button_click(self, event):
        pass
```

Page cụ thể kế thừa base page và override các method trên. Dùng pattern này thay vì lặp lại toàn bộ layout cho từng AI model.

## Chạy AI demo từ UI

UI shell và AI demo dùng chung `PipeLine` do `AppManager` cung cấp. Pattern baseline:

```python
def run_demo(self, module):
    demo = None
    try:
        demo = module.YAHBOOM_DEMO(self.app.pl, self.app.uart)
        demo.exce_demo(self.text_config.get_section("System")["Loading"])
    finally:
        if demo:
            del demo
        gc.collect()
```

Khi demo kết thúc:

1. Dừng và giải phóng tài nguyên riêng của demo.
2. Xóa nội dung OSD còn lại.
3. Thu hồi object lớn và chạy `gc.collect()`.
4. Trả quyền điều khiển về UI shell.

Không tạo `PipeLine` thứ hai trong app nếu app đang chạy bên trong GUI firmware.

## Settings page theo dữ liệu

Firmware biểu diễn từng setting bằng dictionary và để `BaseSettingPage` chọn widget tương ứng:

```python
items = [
    {"name": "Device", "type": "info", "value": "K230"},
    {
        "name": "Enabled",
        "type": "switch",
        "value": 1,
        "config_section": "feature",
        "config_key": "enabled",
    },
    {
        "name": "Volume",
        "type": "slider",
        "value": 59,
        "min": 0,
        "max": 100,
        "config_section": "sound",
        "config_key": "volume",
    },
]
```

Các type baseline:

| Type | LVGL widget |
| :--- | :--- |
| `info` | `lv.label` |
| `switch` | `lv.switch` |
| `slider` | `lv.slider` |
| `button` | `lv.btn` |
| `select` | `lv.dropdown` |

Khi value thay đổi, cập nhật `Configuration` và lưu `/sdcard/configs/sys_config.json` giống các setting page hiện có.

## Text, icon và asset

- Text hiển thị lấy từ `app_manager.text_config`; không hardcode nếu text cần dịch.
- Font dùng font do `app_manager` cung cấp, ví dụ `font_16`.
- Icon app đặt tại `/sdcard/apps/<app_name>/icon.png`.
- Một số app có thêm `dock_icon.png` hoặc `icon_dock.png` cho launcher/dock.
- Ảnh được đọc thành bytes và bọc bằng `lv.img_dsc_t`.
- Giữ bytes ảnh còn sống trong thời gian LVGL sử dụng descriptor nếu implementation page không giữ bản copy nội bộ.

## Style baseline

| Thành phần | Style thường dùng |
| :--- | :--- |
| Background | `#f5f5f5` hoặc `#ffffff` |
| Primary text | `#333333` |
| Secondary text | `#666666` hoặc `#888888` |
| Accent | `#1a73e8` hoặc `#2196f3` |
| Primary action | nền đen, chữ trắng |
| Card radius | khoảng 10 px |
| Selected menu | `lv.STATE.CHECKED` với nền sáng và border trái |

Khi mở rộng app hiện có, copy style từ chính app đó để giữ giao diện đồng nhất.

## Event và lifecycle

- Đăng ký callback bằng `obj.add_event(callback, lv.EVENT.<TYPE>, None)`.
- Dùng default argument trong lambda để giữ đúng item của vòng lặp:

```python
btn.add_event(
    lambda event, key=page_key, button=btn: self.select_page(key, button),
    lv.EVENT.CLICKED,
    None,
)
```

- Sau `container.clean()` hoặc `delete()`, không tiếp tục sử dụng widget con cũ.
- Timer, animation, dialog và worker riêng của app phải được dừng trong `deinitialize()`.
- Page có tài nguyên riêng nên cung cấp `cleanup()`; app gọi `cleanup()` cho từng page trước khi xóa container.
- Giữ các reference LVGL cần dùng lại dưới thuộc tính của app/page để tránh bị GC sớm.

## Baseline để sinh UI mới

1. Chọn app gần nhất trong `k230-firmware/apps/`.
2. Giữ contract `App(BaseApp)`, `initialize()` và `deinitialize()`.
3. Dùng content `640 × 420` và `self.screen` của `BaseApp`.
4. Lấy config, text, pipeline và hardware service từ `app_manager`.
5. Dùng base page nếu app có nhiều chức năng cùng layout.
6. Dùng data-driven setting cho form cấu hình.
7. Chạy AI trên `app_manager.pl`, cleanup rồi quay lại shell.
8. Giữ asset path tuyệt đối dưới `/sdcard/apps/<app_name>/`.
9. Kiểm thử trực tiếp trên image baseline `1.4.1`.

Các file tham chiếu chính:

- `k230-firmware/apps/ai_objects/app.py`
- `k230-firmware/apps/ai_objects/base_demo_page.py`
- `k230-firmware/apps/setting/app.py`
- `k230-firmware/apps/setting/base_setting_page.py`
- `k230-firmware/apps/camera/app.py`
- `k230-firmware/utils/Configuration.py`
- `k230-firmware/utils/modal_dialog.py`
