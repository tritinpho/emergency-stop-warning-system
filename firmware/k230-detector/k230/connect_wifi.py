"""Standalone touch Wi-Fi setup for Yahboom K230 firmware 1.4.1.

Run this file directly from CanMV IDE.  Saved credentials are compatible with
the firmware Settings app (/sdcard/configs/sys_config.json, WLAN section).
"""

import json
import os
import time
import network
import lvgl as lv
import image
from machine import TOUCH
from media.display import Display
from media.media import MediaManager


DISPLAY_WIDTH = 640
DISPLAY_HEIGHT = 480
CONFIG_PATH = "/sdcard/configs/sys_config.json"
CONNECT_TIMEOUT_MS = 15000


class TouchScreen:
    def __init__(self):
        self.read_count = 0
        print("[TOUCH][INIT] calling lv.indev_create()")
        self.indev = lv.indev_create()
        print("[TOUCH][INIT] lv.indev_create returned")
        self.indev.set_type(lv.INDEV_TYPE.POINTER)
        print("[TOUCH][INIT] pointer type configured")
        self.indev.set_read_cb(self._read)
        print("[TOUCH][INIT] read callback configured")
        print("[TOUCH][INIT] calling TOUCH(0)")
        self.touch = TOUCH(0)
        print("[TOUCH][INIT] TOUCH(0) returned")

    def _read(self, driver, data):
        self.read_count += 1
        probe = self.read_count <= 2
        x, y, state = 0, 0, lv.INDEV_STATE.RELEASED
        if probe:
            print("[TOUCH] entering TOUCH.read(1), call #%d" % self.read_count)
        points = self.touch.read(1)
        if probe:
            print("[TOUCH] TOUCH.read(1) returned")
        if len(points):
            point = points[0]
            x, y = point.x, point.y
            if point.event == 2 or point.event == 3:
                state = lv.INDEV_STATE.PRESSED
        if probe:
            print("[TOUCH] point decoded: x=%s y=%s state=%s" % (x, y, state))
        data.point = lv.point_t({"x": x, "y": y})
        if probe:
            print("[TOUCH] data.point assigned")
        data.state = state
        if probe:
            print("[TOUCH] callback completed")


class WiFiSetup:
    def __init__(self, wlan):
        self.wlan = wlan
        self.config = self._load_config()
        self.networks = []
        self.enabled = False
        self.busy = False
        self.pending_ssid = None
        self.pending_password = None
        self.connect_started = 0
        self.dialog = None
        self.keyboard = None
        self.startup_credentials = None
        self._timers = []

        self.screen = lv.scr_act()
        self.screen.set_style_bg_color(lv.color_hex(0xF4F7F5), 0)
        self._build_ui()
        self.set_wifi_enabled(True, startup=True)

    def log(self, message, level="INFO"):
        line = "[WIFI][%s] %s" % (level, message)
        print(line)
        self.status_label.set_text(message)

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r") as stream:
                data = json.load(stream)
            if not isinstance(data, dict):
                raise ValueError("configuration root is not an object")
            if "WLAN" not in data or not isinstance(data["WLAN"], dict):
                data["WLAN"] = {}
            print("[WIFI][INFO] Loaded " + CONFIG_PATH)
            return data
        except Exception as exc:
            print("[WIFI][WARN] Cannot load config: %s" % exc)
            return {"WLAN": {"SSID": "", "PASSWORD": "", "status": 0}}

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w") as stream:
                stream.write(json.dumps(self.config))
            return True
        except Exception as exc:
            self.log("Config save failed: %s" % exc, "ERROR")
            return False

    def _save_credentials(self, ssid, password):
        section = self.config.setdefault("WLAN", {})
        section["SSID"] = ssid
        section["PASSWORD"] = password
        section["status"] = 1
        if self._save_config():
            self.log("Saved Wi-Fi: " + ssid)

    def _build_ui(self):
        title = lv.label(self.screen)
        title.set_text("Wi-Fi setup")
        title.set_style_text_color(lv.color_hex(0x18392B), 0)
        title.align(lv.ALIGN.TOP_LEFT, 18, 14)

        self.toggle_btn = lv.btn(self.screen)
        self.toggle_btn.set_size(110, 42)
        self.toggle_btn.align(lv.ALIGN.TOP_RIGHT, -18, 8)
        self.toggle_btn.add_event(self._toggle_clicked, lv.EVENT.CLICKED, None)
        self.toggle_label = lv.label(self.toggle_btn)
        self.toggle_label.center()

        self.status_label = lv.label(self.screen)
        self.status_label.set_width(430)
        self.status_label.set_long_mode(lv.label.LONG.SCROLL_CIRCULAR)
        self.status_label.align(lv.ALIGN.TOP_LEFT, 18, 58)
        self.status_label.set_text("Starting...")

        self.rescan_btn = lv.btn(self.screen)
        self.rescan_btn.set_size(110, 38)
        self.rescan_btn.align(lv.ALIGN.TOP_RIGHT, -18, 52)
        self.rescan_btn.add_event(lambda e: self.start_scan(), lv.EVENT.CLICKED, None)
        label = lv.label(self.rescan_btn)
        label.set_text("Rescan")
        label.center()

        self.list = lv.obj(self.screen)
        self.list.set_size(604, 365)
        self.list.align(lv.ALIGN.BOTTOM_MID, 0, -10)
        self.list.set_style_pad_all(6, 0)
        self.list.set_flex_flow(lv.FLEX_FLOW.COLUMN)
        self.list.set_scrollbar_mode(lv.SCROLLBAR_MODE.AUTO)
        self._update_toggle()

    def _update_toggle(self):
        self.toggle_label.set_text("Wi-Fi ON" if self.enabled else "Wi-Fi OFF")
        color = 0x21A366 if self.enabled else 0x777777
        self.toggle_btn.set_style_bg_color(lv.color_hex(color), 0)

    def _toggle_clicked(self, event):
        if self.busy:
            self.log("Please wait for the current operation")
            return
        self.set_wifi_enabled(not self.enabled)

    def set_wifi_enabled(self, enabled, startup=False):
        self.enabled = enabled
        self._update_toggle()
        if enabled:
            try:
                # Some K230 builds expose active(), while Yahboom examples do
                # not need it.  Keep both variants compatible.
                if hasattr(self.wlan, "active"):
                    self.wlan.active(True)
            except Exception as exc:
                self.log("Could not explicitly enable radio: %s" % exc, "WARN")
            self.log("Wi-Fi enabled")
            if startup:
                self._schedule(self._startup_connect, 300)
            else:
                self.start_scan()
        else:
            try:
                self.wlan.disconnect()
                if hasattr(self.wlan, "active"):
                    self.wlan.active(False)
                self.config.setdefault("WLAN", {})["status"] = 0
                self._save_config()
                self.log("Wi-Fi disabled")
            except Exception as exc:
                self.log("Could not disable Wi-Fi: %s" % exc, "ERROR")
            self.busy = False
            self.list.clean()

    def _schedule(self, callback, delay_ms):
        holder = [None]

        def run(timer):
            try:
                callback()
            finally:
                try:
                    timer._del()
                except Exception:
                    pass
                if holder[0] in self._timers:
                    self._timers.remove(holder[0])

        holder[0] = lv.timer_create(run, delay_ms, None)
        self._timers.append(holder[0])

    def _startup_connect(self):
        print("[WIFI][STARTUP] callback entered; checking current connection")
        if self.wlan.isconnected():
            print("[WIFI][STARTUP] wlan.isconnected() returned True")
            self._show_connected()
            return
        print("[WIFI][STARTUP] wlan.isconnected() returned False")
        saved = self.config.get("WLAN", {})
        ssid = saved.get("SSID", "")
        password = saved.get("PASSWORD", "")
        placeholders = ("", "SSID", "your_wifi_ssid")
        if ssid in placeholders:
            self.log("No saved Wi-Fi. Select a network below.")
            self.start_scan()
            return
        # Match wifi_settings.py: scan, verify the saved SSID exists, then
        # reconnect with the saved password.
        self.startup_credentials = (ssid, password)
        self.log("Looking for saved Wi-Fi: " + ssid)
        self.start_scan()

    def start_scan(self):
        if not self.enabled:
            self.log("Turn Wi-Fi on before scanning", "WARN")
            return
        if self.busy:
            self.log("Wi-Fi is busy; please wait")
            return
        self.busy = True
        self.list.clean()
        label = lv.label(self.list)
        label.set_text("Scanning for networks...")
        self.log("Scanning for Wi-Fi networks...")
        self._schedule(self._perform_scan, 150)

    def _decode_ssid(self, value):
        if isinstance(value, bytes):
            try:
                return value.decode("utf-8")
            except Exception:
                return value.decode("utf-8", "ignore")
        return str(value)

    def _perform_scan(self):
        reconnect = None
        try:
            raw = self.wlan.scan()
            found = {}
            for item in raw:
                try:
                    if hasattr(item, "ssid"):
                        ssid = self._decode_ssid(item.ssid)
                        rssi = getattr(item, "rssi", -100)
                        security = getattr(item, "security", True)
                    else:
                        ssid = self._decode_ssid(item[0])
                        rssi = item[3] if len(item) > 3 else -100
                        security = item[4] if len(item) > 4 else True
                    if ssid and (ssid not in found or rssi > found[ssid]["rssi"]):
                        found[ssid] = {"ssid": ssid, "rssi": rssi, "security": bool(security)}
                except Exception as exc:
                    print("[WIFI][WARN] Skipped scan item: %s" % exc)
            self.networks = list(found.values())
            self.networks.sort(key=lambda net: net["rssi"], reverse=True)
            self._render_networks()
            self.log("Found %d Wi-Fi network(s)" % len(self.networks))
            if self.startup_credentials:
                ssid, password = self.startup_credentials
                self.startup_credentials = None
                if any(net["ssid"] == ssid for net in self.networks):
                    reconnect = (ssid, password)
                else:
                    self.log("Saved Wi-Fi not found. Select another network.", "WARN")
        except Exception as exc:
            self.networks = []
            self.list.clean()
            label = lv.label(self.list)
            label.set_text("Scan failed. Tap Rescan or toggle Wi-Fi.")
            self.log("Wi-Fi scan failed: %s" % exc, "ERROR")
        finally:
            self.busy = False
        if reconnect:
            self.start_connect(reconnect[0], reconnect[1], save=False)

    def _render_networks(self):
        self.list.clean()
        if not self.networks:
            label = lv.label(self.list)
            label.set_text("No network found. Tap Rescan.")
            return
        current = self._current_ssid()
        for net in self.networks:
            ssid = net["ssid"]
            btn = lv.btn(self.list)
            btn.set_size(lv.pct(100), 48)
            btn.set_style_bg_color(lv.color_hex(0x21A366 if ssid == current else 0xFFFFFF), 0)
            btn.set_style_text_color(lv.color_hex(0xFFFFFF if ssid == current else 0x222222), 0)
            btn.add_event(lambda e, name=ssid, secure=net["security"]: self._network_clicked(name, secure), lv.EVENT.CLICKED, None)
            label = lv.label(btn)
            suffix = "  %d dBm" % net["rssi"]
            if net["security"]:
                suffix += "  [locked]"
            if ssid == current:
                suffix += "  connected"
            label.set_text(ssid + suffix)
            label.align(lv.ALIGN.LEFT_MID, 6, 0)

    def _current_ssid(self):
        if not self.wlan.isconnected():
            return ""
        try:
            value = self.wlan.config("ssid")
            # On Yahboom image 1.4.1 this getter may return True instead of
            # the SSID.  Accept only an actual non-empty string/bytes value.
            if isinstance(value, (str, bytes)):
                decoded = self._decode_ssid(value)
                if decoded:
                    return decoded
        except Exception:
            pass
        return self.pending_ssid or self.config.get("WLAN", {}).get("SSID", "")

    def _network_clicked(self, ssid, secured):
        if self.busy:
            self.log("Please wait for the current operation")
            return
        if ssid == self._current_ssid():
            self._show_connected()
            return
        if secured:
            self._show_password_dialog(ssid)
        else:
            self.start_connect(ssid, "", save=True)

    def _show_password_dialog(self, ssid):
        self._close_dialog()
        self.dialog = lv.obj(self.screen)
        self.dialog.set_size(lv.pct(100), lv.pct(100))
        self.dialog.set_style_bg_color(lv.color_hex(0xE9EFEA), 0)
        self.dialog.set_style_pad_all(10, 0)

        title = lv.label(self.dialog)
        title.set_text("Password for: " + ssid)
        title.align(lv.ALIGN.TOP_LEFT, 8, 4)

        password = lv.textarea(self.dialog)
        password.set_size(430, 44)
        password.align(lv.ALIGN.TOP_LEFT, 8, 34)
        password.set_one_line(True)
        password.set_password_mode(True)
        password.set_placeholder_text("Wi-Fi password")

        show = lv.checkbox(self.dialog)
        show.set_text("Show")
        show.align(lv.ALIGN.TOP_RIGHT, -8, 43)
        show.add_event(lambda e: password.set_password_mode(not bool(show.get_state() & lv.STATE.CHECKED)), lv.EVENT.VALUE_CHANGED, None)

        self.keyboard = lv.keyboard(self.dialog)
        self.keyboard.set_size(620, 300)
        self.keyboard.align(lv.ALIGN.BOTTOM_MID, 0, 0)
        self.keyboard.set_textarea(password)

        cancel = lv.btn(self.dialog)
        cancel.set_size(100, 38)
        cancel.align(lv.ALIGN.TOP_LEFT, 8, 86)
        cancel.add_event(lambda e: self._close_dialog(), lv.EVENT.CLICKED, None)
        label = lv.label(cancel)
        label.set_text("Cancel")
        label.center()

        connect = lv.btn(self.dialog)
        connect.set_size(120, 38)
        connect.align(lv.ALIGN.TOP_RIGHT, -8, 86)

        def submit(event):
            value = password.get_text()
            self._close_dialog()
            self.start_connect(ssid, value, save=True)

        connect.add_event(submit, lv.EVENT.CLICKED, None)
        label = lv.label(connect)
        label.set_text("Connect")
        label.center()
        self.log("Enter password for " + ssid)

    def _close_dialog(self):
        if self.dialog:
            try:
                self.dialog.delete()
            except Exception:
                try:
                    self.dialog.del_()
                except Exception:
                    pass
        self.dialog = None
        self.keyboard = None

    def start_connect(self, ssid, password, save):
        if not self.enabled or self.busy:
            return
        self.busy = True
        self.pending_ssid = ssid
        self.pending_password = password
        self.save_after_connect = save
        try:
            if self.wlan.isconnected():
                self.wlan.disconnect()
            self.log("Connecting to " + ssid + "...")
            self.wlan.connect(ssid, password)
            self.connect_started = time.ticks_ms()
            self._poll_connect()
        except Exception as exc:
            self._connect_failed("connect call failed: %s" % exc)

    def _poll_connect(self):
        if self.wlan.isconnected() and self.wlan.ifconfig()[0] != "0.0.0.0":
            self.busy = False
            if self.save_after_connect:
                self._save_credentials(self.pending_ssid, self.pending_password)
            self._show_connected()
            self._render_networks()
            return
        if time.ticks_diff(time.ticks_ms(), self.connect_started) >= CONNECT_TIMEOUT_MS:
            self._connect_failed("timeout or wrong password")
            return
        self._schedule(self._poll_connect, 500)

    def _connect_failed(self, reason):
        ssid = self.pending_ssid or "saved network"
        self.busy = False
        try:
            self.wlan.disconnect()
        except Exception:
            pass
        self.log("Could not connect to %s: %s" % (ssid, reason), "ERROR")
        self.pending_ssid = None
        self.pending_password = None
        # Baseline behavior only tries a saved SSID if it is present in a
        # scan.  On any startup failure, expose the chooser to the user.
        self.start_scan()

    def _show_connected(self):
        ip = self.wlan.ifconfig()[0]
        ssid = self._current_ssid() or self.pending_ssid or "Wi-Fi"
        self.log("Connected to %s | IP: %s" % (ssid, ip))


disp_img = None
touch = None
disp_driver = None
display_started = False
media_started = False
lvgl_started = False
flush_count = 0


def _flush(display_driver, area, color):
    global flush_count
    flush_count += 1
    probe = flush_count <= 2
    try:
        if probe:
            print("[LVGL][FLUSH] enter #%d" % flush_count)
            print("[LVGL][FLUSH] calling Display.show_image(single-buffer)")
        Display.show_image(disp_img)
        if probe:
            print("[LVGL][FLUSH] Display.show_image returned")
        time.sleep(0.01)
    except Exception as exc:
        print("[LVGL][FLUSH][ERROR] %s" % exc)
    finally:
        display_driver.flush_ready()
        if probe:
            print("[LVGL][FLUSH] flush_ready returned")


def init_display():
    global disp_img, touch, disp_driver
    global display_started, media_started, lvgl_started
    print("[BOOT][3/7] Initializing ST7701 display...")
    Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=True)
    display_started = True
    print("[BOOT][3/7] Display ready")
    print("[BOOT][4/7] Initializing MediaManager...")
    MediaManager.init()
    media_started = True
    print("[BOOT][4/7] MediaManager ready")
    print("[BOOT][5/7] Initializing LVGL...")
    lv.init()
    lvgl_started = True
    print("[BOOT][5/7] lv.init returned")
    # Use the executable src/13.Lvgl baseline: one BGRA8888 buffer in DIRECT
    # mode.  This avoids the extra contiguous allocation required by FULL
    # double buffering.
    print("[BOOT][5/7] Allocating single display buffer...")
    disp_img = image.Image(DISPLAY_WIDTH, DISPLAY_HEIGHT, image.BGRA8888)
    print("[BOOT][5/7] Display buffer allocated")
    disp_driver = lv.disp_create(DISPLAY_WIDTH, DISPLAY_HEIGHT)
    disp_driver.set_draw_buffers(
        disp_img.bytearray(),
        None,
        disp_img.size(),
        lv.DISP_RENDER_MODE.DIRECT,
    )
    disp_driver.set_flush_cb(_flush)
    print("[BOOT][5/7] Display driver configured")
    touch = TouchScreen()
    print("[BOOT][5/7] LVGL and touch ready")


def deinit_display():
    global disp_img, touch, disp_driver
    global display_started, media_started, lvgl_started
    if lvgl_started:
        try:
            lv.deinit()
        except Exception as exc:
            print("[STOP] LVGL cleanup failed: %s" % exc)
        lvgl_started = False
    touch = None
    disp_driver = None
    disp_img = None
    if display_started:
        try:
            Display.deinit()
        except Exception as exc:
            print("[STOP] Display cleanup failed: %s" % exc)
        display_started = False
    if media_started:
        try:
            MediaManager.deinit()
        except Exception as exc:
            print("[STOP] MediaManager cleanup failed: %s" % exc)
        media_started = False


def verify_minimal_render():
    """Prove the LVGL/display backend before constructing the Wi-Fi UI."""
    print("[BOOT][5.5/7] Building minimal render gate")
    screen = lv.scr_act()
    screen.set_style_bg_color(lv.color_hex(0x20352B), 0)
    label = lv.label(screen)
    label.set_text("Starting Wi-Fi setup...")
    label.set_style_text_color(lv.color_hex(0xFFFFFF), 0)
    label.center()
    print("[BOOT][5.5/7] Entering minimal render gate")
    period = lv.timer_handler()
    print("[BOOT][5.5/7] Minimal render gate passed, period=%s" % period)
    screen.clean()


def main():
    wlan = None
    try:
        print("[BOOT] connect_wifi.py started")
        print("[BOOT][1/7] Fresh soft-reboot runtime; no pre-init deinit calls")
        # Preserve the Yahboom GUI lifecycle: display and touch are brought up
        # before the Wi-Fi page creates its network helper.  Constructing WLAN
        # first can leave the native TOUCH(0) constructor blocked on this image.
        init_display()
        verify_minimal_render()
        print("[BOOT][2/7] Creating WLAN station after display/touch...")
        wlan = network.WLAN(network.STA_IF)
        print("[BOOT][2/7] WLAN station ready")
        print("[BOOT][6/7] Building touch interface...")
        app = WiFiSetup(wlan)
        print("[BOOT][6/7] Touch interface ready")
        print("[BOOT][7/7] Wi-Fi setup is running")
        first_handler = True
        while True:
            if first_handler:
                print("[LVGL][HANDLER] entering first timer handler")
            # Use the core handler one iteration at a time.  In the observed
            # run the convenience helper never returned; this form exposes
            # whether the block is in LVGL itself, touch, or a Wi-Fi callback.
            period = lv.timer_handler()
            if first_handler:
                print("[LVGL][HANDLER] first handler returned, period=%s" % period)
                first_handler = False
            delay = period if isinstance(period, int) else 5
            if delay < 1:
                delay = 1
            elif delay > 10:
                delay = 10
            time.sleep_ms(delay)
    except KeyboardInterrupt:
        print("[WIFI][INFO] Stopped from IDE")
    except Exception as exc:
        print("[WIFI][FATAL] %s" % exc)
    finally:
        print("[STOP] Cleaning up...")
        time.sleep_ms(50)
        deinit_display()


if __name__ == "__main__":
    main()
