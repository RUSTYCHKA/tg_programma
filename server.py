import gettext
import requests
import json
import os
import platform
import sys
import aiohttp
import re
from random import randint as rd
import phonenumbers
import socks
import pycountry
import time
import asyncio
import random
from colorama import init, Fore, Back, Style
from functools import lru_cache
from emojiflags.lookup import lookup
from telethon import types, functions
from config import Config

account_text_indices = {}


def restore_console():
    """Восстанавливает свернутое окно консоли"""
    try:
        if platform.system() == "Windows":
            import ctypes

            hwnd = ctypes.windll.kernel32.GetConsoleWindow()

            ctypes.windll.user32.ShowWindow(hwnd, 9)

            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.SetWindowPos(
                hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0020)
        elif platform.system() == "Darwin":
            os.system(
                """osascript -e 'tell application "Terminal" to activate'""")
        else:
            os.system("wmctrl -a $(ps -p $$ -o comm=)")
    except Exception as e:
        print_error(f"Не удалось восстановить окно: {str(e)}")
        
def print_success(message):
    print(Fore.GREEN + message)
    

def print_success_with_start(message):
    restore_console()
    print(Fore.GREEN + message)

def print_warning(message):
    print(Fore.YELLOW + message)

def print_error(message):
    print(Fore.RED + message)


def print_info(message):
    print(Fore.CYAN + message)

def print_info_with_start(message):
    restore_console()
    print(Fore.CYAN + message)


def print_with_time(message):
    restore_console()
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

def print_error_with_start(message):
    restore_console()
    print(Fore.RED + message)



async def prepare_answer(event, texts, url_answer_machine, wait):
    texts = [texts]
    user = event.message.from_id.user_id
    # или другой уникальный идентификатор аккаунта
    account_id = event.client.session.filename

    # Инициализируем словарь для аккаунта, если его нет
    if account_id not in account_text_indices:
        account_text_indices[account_id] = {}

    # Инициализируем счетчик для пользователя, если его нет
    if user not in account_text_indices[account_id]:
        account_text_indices[account_id][user] = 0
    if account_text_indices[account_id][user] == 2:
        return
    sender = await event.get_sender()
    await event.client.forward_messages(url_answer_machine, event.message)
    
    # Проверяем, не превысили ли лимит сообщений для этого пользователя
    if account_text_indices[account_id][user] + 1 > len(texts):
        # account_text_indices[account_id][user] = 0
        await event.client.send_message(url_answer_machine, "Закончил писать сообщения")
        account_text_indices[account_id][user] += 1
        # for callback, event_ in event.client.list_event_handlers():
        #     event.client.remove_event_handler(event_)
        #     event.client.remove_event_handler(callback)
        return

    try:
        await asyncio.sleep(rd(*wait))
        if 'repost' in texts[account_text_indices[account_id][user]]:
            txt = texts[account_text_indices[account_id]
                        [user]].replace("repost", "").strip()
            message_id = txt.split("/")[-1]
            from_peer = txt.replace(message_id, "")
            await event.client.forward_messages(entity=user, from_peer=from_peer, messages=[int(message_id)])
        else:
            await event.client.send_message(user, texts[account_text_indices[account_id][user]], parse_mode='html')

        account_text_indices[account_id][user] += 1

    except Exception as e:
        print(
            f"Ошибка при отправке сообщения пользователю {user} с аккаунта {account_id}: {e}")


def ProxyFromUrl(url):
    pattern = re.compile(
        r'(?P<scheme>\w+)://(?:([^:/]+):([^@]+)@)?([^:/]+):(\d+)')
    match = pattern.match(url)
    if match:
        proxy = {
            "proxy_type": match.group('scheme'),
            "addr": match.group(4),
            "port": int(match.group(5)),
            "username": match.group(2),
            "password": match.group(3)
        }
        if match.group('scheme') == "http":
            proxy_f = (socks.HTTP, match.group(4), int(match.group(5)),
                       True, match.group(2), match.group(3))
        elif match.group('scheme') == "socks4":
            proxy_f = (socks.SOCKS4, match.group(4), int(match.group(5)),
                       True, match.group(2), match.group(3))
        elif match.group('scheme') == "socks5":
            proxy_f = {"http": url}
        
        if len(proxy['addr'].split(".")) > 1 and proxy['proxy_type'] in ('http', 'socks4', 'socks5'):

            return proxy_f

    else:
        return

async def check_proxy(proxy):
    print(f"Подключение к {proxy}")
    timeout = aiohttp.ClientTimeout(total=10)  # 10 секунд таймаут
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get("https://google.com/", proxy=proxy, timeout=timeout) as resp:
                    if resp.status // 100 != 2:
                        print_error(f"Прокси {proxy} нерабочий (статус: {resp.status})")
                        return (False, proxy)
                    else:
                        print_success_with_start(f"Прокси {proxy} рабочий")
                        return (True, proxy)
            except (aiohttp.client_exceptions.ClientHttpProxyError, 
                    aiohttp.client_exceptions.ClientProxyConnectionError,
                    aiohttp.client_exceptions.ClientConnectorError) as e:
                print_error(f"Прокси {proxy} нерабочий: {str(e)}")
                return (False, proxy)
            except asyncio.TimeoutError:
                print_error(f"Прокси {proxy} нерабочий (таймаут)")
                return (False, proxy)
            except Exception as e:
                print_error(f"Прокси {proxy} нерабочий: {str(e)}")
            return (False, proxy)
    except Exception as e:
        print_error(f"Прокси {proxy} нерабочий: {str(e)}")
    return (False, proxy)

async def CheckProxies(proxy_list):
    
    tasks = []
    for proxy in proxy_list:
        is_valid = ProxyFromUrl(proxy)
        if is_valid is None:
            tasks.append(asyncio.create_task(check_proxy(proxy)))
        else:
            tasks.append(asyncio.create_task(check_proxy(proxy)))
    results = await asyncio.gather(*tasks)
    return results

_ = gettext.gettext
@lru_cache(256)
def alpha2_to_country_name(code):
    if not isinstance(code, str):
        return None
    code = code.strip()
    if not code or len(code) != 2:
        return None
    r = pycountry.countries.get(alpha_2=code)
    if not r:
        return None
    return _(r.name)  # type: ignore


def get_flag_code(country_code):
    """
    Возвращает код флага в формате '1f1f7-1f1fa' для заданного кода страны
    :param country_code: Двухбуквенный код страны (ISO Alpha-2)
    :return: Строка с кодом флага
    """
    # Преобразуем буквы в верхний регистр
    country_code = country_code.upper()

    # Проверяем, что код страны состоит из 2 букв
    if len(country_code) != 2 or not country_code.isalpha():
        raise ValueError(
            "Неверный код страны. Должен быть 2-буквенный код (ISO Alpha-2)")

    # Конвертируем каждую букву в соответствующий региональный индикатор
    first_part = f"1f1{ord(country_code[0]) - 0x41 + 0xe6:x}"
    second_part = f"1f1{ord(country_code[1]) - 0x41 + 0xe6:x}"
    
    return f"static/img-apple-64/{first_part}-{second_part}"



def get_geo_from_phone(login):
    try:
        phn = phonenumbers.parse("+"+login)
        country = phonenumbers.region_code_for_number(phn)
        country_name = alpha2_to_country_name(country)
        emoji = get_flag_code(country)
        if emoji == None and country_name != None:
            return f"{country}"
        if emoji == None and country_name == None:
            return ""

        return emoji, f"{country}"
    except Exception as e:
        print(f"Ошибка при определении гео: {e}")
        return "❌", "Неизвестно"


def distribute_proxies(accounts: list, proxies: list) -> list[tuple]:
    """
    Распределяет прокси так:
    - Первые N аккаунтов получают первые N прокси (уникальные).
    - Остальные аккаунты получают прокси с начала списка.
    
    :param accounts: Список аккаунтов [{"phone": "123"}, ...]
    :param proxies: Список прокси ["ip:port", ...]
    :return: Список кортежей [(аккаунт, прокси), ...]
    """
    if not proxies:
        return [(account, None) for account in accounts]

    result = []

    for i, account in enumerate(accounts):
        # Если прокси закончились — берем с начала списка
        proxy = proxies[i % len(proxies)]
        result.append((account, proxy))

    return result


def delete_accounts_sessions(account_ids: list, folder: str = 'all'):
    """
    Удаляет сессии и связанные файлы выбранных аккаунтов
    :param account_ids: список номеров телефонов для удаления
    :param folder: папка для поиска ('working', 'archive' или 'all')
    :return: словарь с результатами удаления
    """
    # Определяем пути к папкам
    if folder == 'working':
        directories = [Config.WORKING_DIR]
    elif folder == 'archive':
        directories = [Config.ARCHIVE_DIR]
    else:  # all
        directories = [Config.WORKING_DIR, Config.ARCHIVE_DIR]

    result = {
        'deleted': [],
        'not_found': [],
        'errors': []
    }

    for phone in account_ids:
        deleted = False

        for directory in directories:
            session_file = os.path.join(directory, f"{phone}.session")
            json_file = os.path.join(directory, f"{phone}.json")

            try:
                # Удаляем файл сессии
                if os.path.exists(session_file):
                    os.remove(session_file)
                    deleted = True

                # Удаляем json файл
                if os.path.exists(json_file):
                    os.remove(json_file)
                    deleted = True

               

            except Exception as e:
                result['errors'].append({
                    'phone': phone,
                    'error': str(e),
                    'directory': directory
                })
                print_error(str(e))
                continue

            if deleted:
                result['deleted'].append({
                    'phone': phone,
                    'directory': directory
                })
                break  # Прерываем поиск в других директориях

        if not deleted:
            result['not_found'].append(phone)

    return result


async def wiretapping_forward_to_storage(event, settings, trigerwords, url):
    text = event.message.text
    admin = settings["chat_link"]
    for keyword in trigerwords:
        if keyword.lower() in text.lower():
            await event.client.send_message(admin, f"Сообщение лида обнаружено: https://t.me/{event.message.chat.username}/{event.message.id}")


async def wiretapping_reply_in_chat(event, settings, trigerwords):
    for keyword in trigerwords:
        if keyword.lower() in event.message.text.lower():
            wait = list(map(int, settings["delay"].split('-')))
            message = settings["message"]
            await asyncio.sleep(rd(*wait))
            await event.reply(message)
    

async def wiretapping_like_triggers(event, settings, trigerwords):
    for keyword in trigerwords:
        if keyword.lower() in event.message.text.lower():
            wait = list(map(int, settings["delay"].split('-')))
            await asyncio.sleep(rd(*wait))
            peer_id = event.message.peer_id
            msg_id = event.message.id
            result = await event.client(functions.messages.SendReactionRequest(
                peer=peer_id,
                msg_id=msg_id,
                reaction=[types.ReactionEmoji(
                    emoticon="👍"
                )]
            ))


async def wiretapping_add_to_group(event, settings, trigerwords):
    for keyword in trigerwords:
        if keyword.lower() in event.message.text.lower():
            group_link = settings["group_link"]
            result = await event.client(functions.contacts.AddContactRequest(
                id=event.message.sender,
                first_name=event.message.sender.first_name if event.message.sender.first_name else "Неизвестный",
                last_name=event.message.sender.last_name if event.message.sender.last_name else "Неизвестный",
                phone=event.message.sender.phone if event.message.sender.phone else "899999999"
            ))
            try:
                invite = await event.client(
                  functions.channels.InviteToChannelRequest(
                    group_link,
                    [event.message.sender],
                )
               )
            except Exception as e:
                print(f"Error: {e}")

            if invite.missing_invitees:
                if invite.missing_invitees[0].premium_required_for_pm:
                    print_error_with_start(
                        f"Пользователь {event.message.sender.username} не может быть приглашен в {group_link} (На аккаунте необходим ТГ премиум)")
                elif invite.missing_invitees[0].premium_would_allow_invite:
                    print_error_with_start(
                        f"Пользователь {event.message.sender.username} не может быть приглашен в {group_link} (На аккаунте необходим ТГ премиум и нельзя пригласить из за настроек приватности.)")
                else:
                    print_error_with_start(
                        f"Пользователь {event.message.sender.username} не может быть приглашен в {group_link} (Нельзя пригласить из за настроек приватности)")

            else:
                print_success_with_start(f"Пользователь {event.message.sender.username} был добавлен в {group_link}")
                
            

async def wiretapping_initiate_pm(event, settings, trigerwords):
    message = settings['message']
    original = settings['include_original']
    wait = list(map(int, settings["delay"].split('-')))
    for keyword in trigerwords:
        if keyword.lower() in event.message.text.lower():
            await asyncio.sleep(rd(*wait))
            if original:
                await event.message.forward_to(event.message.sender_id)
                await event.client.send_message(event.message.sender_id, message)
            else:
                await event.client.send_message(event.message.sender_id, message)


async def wiretapping_ai_conversation(event, ai_agent, trigerwords):
    promt = ai_agent[3]
    for keyword in trigerwords:
        if keyword.lower() in event.message.text.lower():
            text = await promt_generation(promt)
            await event.client.send_message(event.message.chat_id, text)
            
async def call_gemini_api(gemini_api_key, promt):
    api_key = gemini_api_key
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {
                "parts": [
                    {"text": promt}
                ]
            }
        ] 
    }

    proxy = "http://user252117:1qimjh@102.165.47.151:3097"

    response = requests.post(url, headers=headers, data=json.dumps(data), params={
                             "key": api_key}, proxies={"http": proxy, "https": proxy})
    f = response.json()
    return f['candidates'][0]['content']['parts'][0]['text']


async def promt_generation(promt):
    try:
        chat = await call_gemini_api(Config.API_KEY, promt)
    except Exception as e:
        return "❌ Произошла ошибка при генерации текста"
    # if isinstance(chat, dict):
    #     text = chat['choices'][0]['message']['content']
    # else:
    #     text = ""
    #     for token in chat:
    #         content = token["choices"][0]["delta"].get("content")
    #         if content is not None:
    #             text += content
    return chat

if __name__ == '__main__':
    asyncio.run(promt_generation("hello"))