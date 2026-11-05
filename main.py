import asyncio
import re
import base64
import urllib.request
import logging
import threading
import os

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.core.clipboard import Clipboard
from kivy.clock import Clock

from telethon import TelegramClient, connection

# ================== НАСТРОЙКИ ==================
API_ID = 123456                      # <-- ОБЯЗАТЕЛЬНО ЗАМЕНИТЬ
API_HASH = "your_api_hash_here"      # <-- ОБЯЗАТЕЛЬНО ЗАМЕНИТЬ

URL = "https://raw.githubusercontent.com/SoliSpirit/mtproto/master/all_proxies.txt"
TIMEOUT = 10.0        
CONCURRENCY = 5       
# ===============================================

logging.getLogger('telethon').setLevel(logging.CRITICAL)

def normalize_secret(secret: str):
    secret = secret.strip()
    if re.fullmatch(r"[0-9a-fA-F]+", secret):
        return secret.lower()
    try:
        padded = secret + "=" * (-len(secret) % 4)
        raw = base64.urlsafe_b64decode(padded)
        if not raw: return None
        return raw.hex()
    except Exception:
        return None

async def check_proxy(server, port, secret_hex, sem, session_path):
    async with sem:
        client = TelegramClient(
            session=session_path,
            api_id=API_ID,
            api_hash=API_HASH,
            connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,
            proxy=(server, port, secret_hex),
            timeout=TIMEOUT,
            connection_retries=0,
            request_retries=0,
            auto_reconnect=False,
        )
        try:
            await asyncio.wait_for(client.connect(), timeout=TIMEOUT)
            if not client.is_connected(): return False
            await asyncio.wait_for(client.get_me(), timeout=TIMEOUT)
            return True
        except Exception:
            return False
        finally:
            try: await client.disconnect()
            except Exception: pass

async def run_checks(proxy_list, session_path, status_callback):
    sem = asyncio.Semaphore(CONCURRENCY)
    working = []
    
    async def worker(server, port, secret_hex, line, index, total):
        ok = await check_proxy(server, port, secret_hex, sem, session_path)
        status_callback(f"Проверено {index+1} из {total}...")
        if ok: return line
        return None

    tasks = [worker(s, p, sec, ln, i, len(proxy_list)) for i, (s, p, sec, ln) in enumerate(proxy_list)]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r]

class MTProtoApp(App):
    def build(self):
        self.session_path = os.path.join(self.user_data_dir, "proxy_session")
        
        root = BoxLayout(orientation="vertical", padding=15, spacing=10)
        
        self.status_label = Label(text="Готов к работе", size_hint_y=None, height=40, font_size="16sp")
        root.add_widget(self.status_label)
        
        self.btn_check = Button(text="Проверить прокси", size_hint_y=None, height=60, background_color=(0.2, 0.6, 0.8, 1))
        self.btn_check.bind(on_press=self.start_check)
        root.add_widget(self.btn_check)
        
        self.btn_copy = Button(text="Скопировать рабочие", size_hint_y=None, height=50, background_color=(0.3, 0.7, 0.3, 1))
        self.btn_copy.bind(on_press=self.copy_links)
        root.add_widget(self.btn_copy)
        
        self.out = TextInput(readonly=True, font_size="12sp", background_color=(0.1, 0.1, 0.1, 1), foreground_color=(1, 1, 1, 1))
        root.add_widget(self.out)
        return root

    def start_check(self, instance):
        self.btn_check.disabled = True
        self.out.text = "Скачиваю список..."
        threading.Thread(target=self._bg_worker, daemon=True).start()

    def _bg_worker(self):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
            text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
            
            pattern = re.compile(r"server=([^&]+).*?port=(\d+)&secret=([^&\s]+)")
            proxies = []
            for line in text.splitlines():
                m = pattern.search(line.strip())
                if m:
                    sec = normalize_secret(m.group(3))
                    if sec: proxies.append((m.group(1).rstrip("."), int(m.group(2)), sec, line.strip()))
            
            if not proxies:
                Clock.schedule_once(lambda dt: self._update_ui("Прокси не найдены", False))
                return

            def status_update(msg):
                Clock.schedule_once(lambda dt: setattr(self.status_label, 'text', msg))

            status_update(f"Проверяю {len(proxies)} шт...")
            working = asyncio.run(run_checks(proxies, self.session_path, status_update))
            
            if working:
                res_text = "\n\n".join(working)
                Clock.schedule_once(lambda dt: self._update_ui(f"Найдено {len(working)} рабочих!", False, res_text))
            else:
                Clock.schedule_once(lambda dt: self._update_ui("Рабочих не найдено.", False, ""))

        except Exception as e:
            Clock.schedule_once(lambda dt: self._update_ui(f"Ошибка: {e}", False))

    def _update_ui(self, status, disable_btn, text=None):
        self.status_label.text = status
        if text is not None:
            self.out.text = text
        if not disable_btn:
            self.btn_check.disabled = False

    def copy_links(self, instance):
        if self.out.text:
            Clipboard.copy(self.out.text)
            self.status_label.text = "Скопировано в буфер!"

if __name__ == "__main__":
    MTProtoApp().run()