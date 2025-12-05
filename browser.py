import json
from time import sleep
import zipfile

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium_authenticated_proxy import SeleniumAuthenticatedProxy

from server import print_error_with_start
from telethon.sessions import SQLiteSession

async def authorization(phone, session, proxy):
    telethon_session = SQLiteSession(session.session)
    key = telethon_session.auth_key.key.hex()
    proxy_str = proxy[1]

    # Разбираем прокси с помощью urllib
    from urllib.parse import urlparse
    parsed = urlparse(proxy_str)
    protocol = parsed.scheme
    login = parsed.username
    password = parsed.password
    ip = parsed.hostname
    port = parsed.port

    # Проверяем наличие данных аутентификации
    if not all([login, password, ip, port]):
        raise ValueError(
            "Invalid proxy format. Use: scheme://login:password@ip:port")

    id = session.me.id
    dc_id = telethon_session.dc_id
    WEB_SESSION_DATA = {
        f'dc{dc_id}_auth_key': key,
        'dc': f"{dc_id}",
        'user_auth': f'{{"dcID":{dc_id},"id":"{id}"}}',
    }

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    opts = Options()

    # Создаем расширение для работы с прокси
    PROXY_EXT = """
    var config = {
        mode: "fixed_servers",
        rules: {
            singleProxy: {
                scheme: "%s",
                host: "%s",
                port: %d
            },
            bypassList: ["localhost"]
        }
    };

    chrome.proxy.settings.set({value: config, scope: "regular"}, function() {});

    function callbackFn(details) {
        return {
            authCredentials: {
                username: "%s",
                password: "%s"
            }
        };
    }

    chrome.webRequest.onAuthRequired.addListener(
        callbackFn,
        {urls: ["<all_urls>"]},
        ['blocking']
    );
    """ % (protocol, ip, int(port), login, password)

    # Создаем временное расширение
    import tempfile
    import os
    import shutil
    import zipfile

    proxy_ext_dir = tempfile.mkdtemp()
    with open(os.path.join(proxy_ext_dir, "manifest.json"), "w") as f:
        f.write("""
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Proxy Auth",
            "background": {"scripts": ["background.js"]},
            "permissions": ["proxy", "webRequest", "webRequestBlocking", "<all_urls>"]
        }
        """)

    with open(os.path.join(proxy_ext_dir, "background.js"), "w") as f:
        f.write(PROXY_EXT)

    # Пакуем расширение
    proxy_ext_path = os.path.join(tempfile.gettempdir(), "proxy_auth.zip")
    with zipfile.ZipFile(proxy_ext_path, 'w') as zf:
        for file in ["manifest.json", "background.js"]:
            zf.write(os.path.join(proxy_ext_dir, file), file)

    shutil.rmtree(proxy_ext_dir)

    # Добавляем расширение в опции
    opts.add_extension(proxy_ext_path)
    opts.add_argument("--disable-popup-blocking")

    driver = webdriver.Chrome(options=opts)

    # Устанавливаем данные сессии
    driver.get("https://web.telegram.org/a")
    for key, value in WEB_SESSION_DATA.items():
        if "auth_key" in key:
            value = f'"{value}"'
        driver.execute_script(
            f"window.localStorage.setItem('{key}', {json.dumps(value)});")

    driver.get("https://web.telegram.org/a")

    # Очистка временных файлов
    os.unlink(proxy_ext_path)

    return driver




