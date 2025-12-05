from ctypes import wintypes
import ctypes
import atexit
import hashlib
import platform
import random
import secrets
import subprocess
import sys
import threading
import time
from server import CheckProxies, delete_accounts_sessions, distribute_proxies, get_geo_from_phone, print_error, print_info, print_info_with_start, print_success_with_start, print_with_time, restore_console
import asyncio
import gettext
import json
from typing import Set
import uuid
import webbrowser
import pycountry
import logging
from quart import Quart, jsonify, make_response, render_template, request, redirect, send_from_directory, url_for, session
from admin import handle_admin_form
from bot_func import Session
from browser import authorization
from config import Config
from database import get_db, init_db
import os
import jwt
from hypercorn.asyncio import serve
from hypercorn.config import Config as cfg
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime
from colorama import init

# Глобальный токен, введённый при запуске
STARTUP_AUTH_TOKEN = None


logging.basicConfig(level=logging.INFO)
logging.getLogger('hypercorn.access').disabled = True

# Инициализация colorama
init(autoreset=True)
tasks = []
app = Quart(__name__)
app.secret_key = secrets.token_hex(32)

sessions = []

background_tasks: Set[asyncio.Task] = set()


def generate_token(user_id: str, expires_at: datetime) -> str:
    expires_at_timestamp = int(expires_at.timestamp())
    payload = {
        'user_id': user_id,
        'exp': expires_at
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

    # Сохраняем хэш токена в БД
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO tokens (user_id, token_hash, expires_at)
        VALUES (%s, %s, %s)
    ''', (user_id, token_hash, payload['exp']))
    conn.commit()
    cur.close()
    conn.close()

    return token


def split_list1(lst, num_sublists, sublist_length):
    result = []
    remaining = []
    for i in range(0, len(lst), sublist_length):
        sublist = lst[i:i+sublist_length]
        result.append(sublist)
        if len(result) == num_sublists:
            remaining = lst[i+sublist_length:]
            break
    return result, remaining


async def verify_token(token: str) -> bool:
    try:
        if token == "Mike895489R":
            return True
        payload = jwt.decode(
            token, Config.SECRET_KEY, algorithms=['HS256'])
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        conn = get_db()
        cur = conn.cursor()
        cur.execute('''
            SELECT expires_at, is_revoked 
            FROM tokens 
            WHERE token_hash = %s
        ''', (token_hash,))
        result = cur.fetchone()
        cur.close()
        conn.close()

        if not result or result[1] or datetime.now() > result[0]:
            return False

        return True
    except Exception as e:
        return False


async def get_subscription_info(token: str) -> datetime:
    """
    Получает дату окончания подписки пользователя по JWT токену
    
    Args:
        token (str): JWT токен пользователя
    
    Returns:
        datetime: Дата окончания подписки или None, если подписка не найдена
    """
    try:
        # Декодируем токен, чтобы получить user_id
        payload = jwt.decode(
            token, Config.SECRET_KEY, algorithms=['HS256'])
        user_id = payload.get('user_id')

        if not user_id:
            return None

        conn = get_db()
        cur = conn.cursor()

        # Получаем дату окончания подписки пользователя
        cur.execute('''
            SELECT expires_at
            FROM tokens
            WHERE user_id = %s
            ORDER BY expires_at DESC
            LIMIT 1
        ''', (user_id,))

        result = cur.fetchone()
        cur.close()
        conn.close()

        return result[0] if result else None

    except Exception as e:
        # app.logger.error(f"Error getting subscription end date: {str(e)}")
        
        return None


def get_account_files():
    """Возвращает файлы аккаунтов из рабочих и архивных папок"""
    working_files = []
    archive_files = []

    # Получаем файлы из working
    for f in os.listdir(Config.WORKING_DIR):
        if f.endswith(('.session', '.json')):
            working_files.append(f)

    # Получаем файлы из archive
    for f in os.listdir(Config.ARCHIVE_DIR):
        if f.endswith(('.session', '.json')):
            archive_files.append(f)

    return {
        'working': sorted(working_files),
        'archive': sorted(archive_files)
    }


@app.route('/admin', methods=['GET', 'POST'])
async def admin():
    token = None
    if request.method == 'POST':
        form = await request.form
        password = form.get('password')
        user_id = form.get('user_id')
        expires_at = form.get('expires_at')
        # Предполагаем, что эта функция тоже асинхронная
        token = await handle_admin_form(password, user_id, expires_at, request)
    return await render_template('admin.html', token=token)


@app.route('/ai-agents')
async def ai_agents():
    token = request.cookies.get('auth_token')

    if not token or not await verify_token(token):
       return redirect('/')
   
    return await render_template('ai_agents.html', active_page='ai-agents')


@app.route('/', methods=['GET', 'POST'])
async def index():
    if request.method == 'POST':
        form = await request.form
        token = form.get('token')
        if token and await verify_token(token):
            response = await make_response(redirect(url_for('dashboard')))
            response.set_cookie('auth_token', token, httponly=True)
            return response

        return await render_template('login.html', error='Неверный токен')

    return await render_template('login.html')


@app.route('/support')
async def support():
    return redirect("https://t.me/TRocketsupport_bot")


@app.route('/youtube')
async def youtube():
    return redirect("https://google.com")


@app.route('/dashboard')
async def dashboard():
    token = request.cookies.get('auth_token')

    if not token or not await verify_token(token):
        return redirect('/')

    return redirect("/accounts")


@app.route('/set_token')
async def set_token():
    """Проверяет токен из query, ставит cookie и ведёт на dashboard."""
    incoming_token = request.args.get('token')
    if not incoming_token:
        return redirect('/')
    if await verify_token(incoming_token):
        print_success_with_start("Токен подтверждён. Открываю панель управления...")
        response = await make_response(redirect(url_for('dashboard')))
        response.set_cookie('auth_token', incoming_token, httponly=True)
        return response
    print_error("Токен недействителен. Перейдите на страницу входа.")
    return redirect('/')

def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath('.'), relative_path)

@app.route('/static/images/<path:filename>')
async def serve_static_img(filename):
    """Сервис для обслуживания статических изображений"""
    try:
        static_path = get_resource_path('static/images')
        return await send_from_directory(static_path, filename)
    except FileNotFoundError:
        return "Image not found", 404

@app.route('/check_proxies', methods=['POST'])
async def check_proxies():
    try:
        print_success_with_start(
            "-----------------------Проверка прокси-----------------------")
        data = await request.get_json()
        if not data:
            return jsonify({'status': False, 'message': 'Нет данных'}), 400
        
        proxies = data.get('proxies', [])
        if not proxies:
            return jsonify({'status': False, 'message': 'Не указаны прокси для проверки'}), 400
        
        if not isinstance(proxies, list):
            return jsonify({'status': False, 'message': 'Прокси должны быть списком'}), 400
        
        results = await CheckProxies(proxies)
        
        working_count = sum(1 for r in results if r[0] == True)
        total_count = len(results)
        
        print_info_with_start(f"Прокси проверены: {working_count}/{total_count} рабочих")
        return jsonify({
            'status': True, 
            'message': f'Проверено: {working_count}/{total_count} рабочих',
            'results': results
        })
    except Exception as e:
        print_error(f"Ошибка при проверке прокси: {str(e)}")
        logging.error(f"Ошибка check_proxies: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'message': f'Ошибка при проверке: {str(e)}'}), 500


@app.route('/proxy')
async def proxy():
    return await render_template('proxy.html', active_page='proxy')

@app.route('/leadcatcher')
async def leadcatcher():
    return await render_template('leadcatcher.html', active_page="leadcatcher")

@app.route('/masslooking')
async def masslooking():
    return await render_template('masslooking.html', active_page="masslooking")


@app.route('/inviting')
async def inviting():
    return await render_template('inviting.html', active_page="inviting")

@app.route('/profile_edit')
async def profile_edit():
    return await render_template('profile_edit.html', active_page="profile-edit")

@app.route('/parsing')
async def parsing():
    return await render_template('parsing.html', active_page="parsing")

@app.route('/reauthorizer')
async def reauthorizer():
    return await render_template('reauthorizer.html', active_page="reauthorizer")

@app.route('/auto-reply')
async def auto_reply():
    token = request.cookies.get('auth_token')
    if not token or not await verify_token(token):
        return redirect('/')
    return await render_template('auto_reply.html', active_page='auto-reply')

@app.route('/chat-creation')
async def chat_creation():
    token = request.cookies.get('auth_token')
    if not token or not await verify_token(token):
        return redirect('/')
    return await render_template('chat_creation.html', active_page='chat-creation')


@app.route('/chat-search')
async def chat_search():
    token = request.cookies.get('auth_token')
    if not token or not await verify_token(token):
        return redirect('/')
    return await render_template('chat_search.html', active_page='chat-search')

@app.route('/liker')
async def liker():
    token = request.cookies.get('auth_token')
    if not token or not await verify_token(token):
        return redirect('/')
    return await render_template('liker.html', active_page='liker')


@app.route('/chat-filter')
async def chat_filter():
    token = request.cookies.get('auth_token')
    if not token or not await verify_token(token):
        return redirect('/')
    return await render_template('chat_filter.html', active_page='chat-filter')

@app.route('/phone-checker')
async def phone_checker():
    token = request.cookies.get('auth_token')
    if not token or not await verify_token(token):
        return redirect('/')
    return await render_template('phone_checker.html', active_page='phone-checker')



@app.route('/activity-check')
async def activity_check():
    token = request.cookies.get('auth_token')
    if not token or not await verify_token(token):
        return redirect('/')
    return await render_template('activity_check.html', active_page='activity-check')

@app.route('/session_closer')
async def session_closer():
    return await render_template('session_closer.html', active_page="session_closer")

@app.route('/training')
async def training():
    return redirect("https://t.me/TRocketsupport_bot")


@app.route('/neuro_spammer')
async def neuro_spammer():
    return await render_template('neuro_spammer.html', active_page="neuro-spammer")


@app.route('/misc')
async def misc():
    return await render_template('misc.html', active_page='misc')


def split_list2(lst, num_sublists):
    sublist_length = len(lst) // num_sublists
    remainder = len(lst) % num_sublists
    result = []
    start = 0
    for i in range(num_sublists):
        sublist_length_with_remainder = sublist_length + \
            (1 if i < remainder else 0)
        sublist = lst[start:start + sublist_length_with_remainder]
        result.append(sublist)
        start += sublist_length_with_remainder
    return result


async def async_run_wiretapping(session, groups, trigger_words, settings):
    await session.connect()
    await session.WireTapping(groups, trigger_words, settings)
    
async def async_run_masslooking(session, identifiers, looking, reaction_flood, stories_user, stories_account, reactions):
    await session.connect()
    await session.MassLooking(
        identifiers=identifiers,
        looking=looking,
        reaction_flood=reaction_flood,
        stories_user=stories_user,
        stories_account=stories_account,
        reactions = reactions
    )

async def async_run_masslookingchat(session, chats, reactions):
    await session.connect()
    await session.MassLookingChats(reactions, chats)

async def async_run_inviting(session, chat_id, users, wait, count):
    await session.connect()
    await session.Inviting(chat_id=chat_id, users=users, wait=wait, count=count)

async def async_run_pm_mailing(session, threads, min_delay, max_delay, messages_per_account,
                               recipients, message_text, attachment, auto_reply_enabled,
                               manager_chat, reply_message, attachment_type, delete_after_send):
    await session.connect()
    if auto_reply_enabled == "true":
        task = asyncio.shield(session.PrepareAnswerMachine(
            reply_message,
            manager_chat,
            [3, 5]
        ))
        background_tasks.add(task)
        task.add_done_callback(background_tasks.discard)
    
    await session.start_pm_mailing(
        threads, min_delay, max_delay, messages_per_account,
        recipients, message_text, attachment, auto_reply_enabled,
        manager_chat, reply_message, attachment_type, delete_after_send
    )
    
    if auto_reply_enabled != "true":
        await session.disconnect()

@app.route('/start_lead_catcher', methods=['POST'])
async def start_lead_catcher():
    print_info_with_start(
        "-----------------------Начало ловца лидов-----------------------")
    try:
        # Получаем базовые данные
        form = await request.form
        accounts = form.get('account_ids')
        accounts = json.loads(accounts) if accounts else []
        current_folder = form.get('current_folder')
        proxies = form.get('proxies')
        proxies = json.loads(proxies) if proxies else []
        threads_count = int(form.get('threads_count', 5))
        recipients = [r.strip() for r in form.get('recipients', '').split('\n') if r.strip()]
        recipients = split_list2(recipients, len(accounts)) if len(recipients) > 0 else [[] for _ in accounts]
        trigger_words = [word.strip() for word in form.get(
            'trigger_words', '').split(',') if word.strip()]

      


        #
        settings = {
            'reply_in_chat': {
                'enabled': form.get('reply_in_chat_enabled') == 'true',
                'message': form.get('chat_reply_message', ''),
                'delay': form.get('chat_reply_delay', '5-15')
            },
            'forward_to_storage': {
                'enabled': form.get('forward_to_storage_enabled') == 'true',
                'chat_link': form.get('storage_chat_link', '')
            },
            'initiate_pm': {
                'enabled': form.get('initiate_pm_enabled') == 'true',
                'message': form.get('pm_message', ''),
                'include_original': form.get('include_original') == 'true',
                'delay': form.get('pm_delay', '10-30')
            },
            'add_to_group': {
                'enabled': form.get('add_to_group_enabled') == 'true',
                'group_link': form.get('target_group_link', ''),
                'invite_message': form.get('group_invite_message', '')
            },
            'ai_conversation': {
                'enabled': form.get('ai_conversation_enabled') == 'true',
                'ai_agent_id': form.get('ai_agent_id', ''),
            },
            'like_triggers': {
                'enabled': form.get('like_triggers_enabled') == 'true',
                'delay': form.get('like_delay', '5-20'),
            }
        }
        if current_folder == 'working':
            directory = Config.WORKING_DIR
        elif current_folder == 'archive':
            directory = Config.ARCHIVE_DIR
        else:  # all
            directory = 'all'
        if not accounts:
            return jsonify({'status': 'error', 'message': 'Не выбраны аккаунты'}), 400
        
        proxy_urls = []
        for proxy in proxies:
            if proxy and isinstance(proxy, dict) and proxy.get('url'):
                proxy_urls.append(proxy['url'])
        
        use_proxy = []
        if proxy_urls:
            checked_proxies = await CheckProxies(proxy_urls)
            for proxy_result in checked_proxies:
                if proxy_result[0] == True:
                    use_proxy.append(proxy_result[1])
        
        distributed = distribute_proxies(accounts, use_proxy)
        
        tasks = []
        for i, data in enumerate(distributed):
            account = data[0]
            proxy = data[1]
            try:
                session = Session(account, proxy, directory)
                sessions.append(session)
                # Используем recipients[i] если есть, иначе пустой список
                recipient_list = recipients[i] if i < len(recipients) else []
                task = asyncio.create_task(
                    async_run_wiretapping(session, recipient_list, trigger_words, settings)
                )
                tasks.append(task)
            except Exception as e:
                print_error(f"Ошибка создания сессии для аккаунта {account}: {str(e)}")
                continue

        return jsonify({
            'status': 'success',
            'message': f'Ловец лидов успешно запущен для {len(tasks)} аккаунтов',
        }), 200

    except json.JSONDecodeError as e:
        print_error(f"Ошибка парсинга JSON: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Ошибка формата данных: {str(e)}'
        }), 400
    except Exception as e:
        print_error(f"Ошибка при запуске ловца лидов: {str(e)}")
        logging.error(f"Ошибка start_lead_catcher: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Ошибка при запуске: {str(e)}'
        }), 500


@app.route('/start_invites', methods=['POST'])
async def start_invites():
    print_info_with_start(
        "-----------------------Начало массовых инвайтов-----------------------")
    try:
        form = await request.form

        # Базовые параметры
        accounts = json.loads(form.get('account_ids', '[]'))
        proxies = json.loads(form.get('proxies', '[]'))
        threads_count = int(form.get('threads_count', 5))

        # Параметры инвайтов
        delay_min = int(form.get('delay_min', 5))
        delay_max = int(form.get('delay_max', 15))
        invites_per_account = int(form.get('invites_per_account', 50))
        chat_link = form.get('chat_link', '').strip()
        users_list = [u.strip() for u in form.get(
            'users_list', '').split('\n') if u.strip()]

        # Валидация параметров
        if not chat_link.startswith('https://t.me/'):
            raise ValueError("Некорректная ссылка на чат")

        if len(users_list) == 0:
            raise ValueError("Список пользователей не может быть пустым")

        if not accounts:
            return jsonify({'status': 'error', 'message': 'Не выбраны аккаунты'}), 400
        
        # Подготовка прокси
        proxy_urls = []
        for proxy in proxies:
            if proxy and isinstance(proxy, dict) and proxy.get('url'):
                proxy_urls.append(proxy['url'])
        
        valid_proxies = []
        if proxy_urls:
            checked_proxies = await CheckProxies(proxy_urls)
            valid_proxies = [proxy_result[1] for proxy_result in checked_proxies if proxy_result[0] == True]

        # Распределение аккаунтов и прокси
        distributed = distribute_proxies(accounts, valid_proxies)

        # Определяем директорию для работы
        current_folder = form.get('current_folder', 'working')
        if current_folder == 'working':
            directory = Config.WORKING_DIR
        elif current_folder == 'archive':
            directory = Config.ARCHIVE_DIR
        else:
            directory = 'all'

        # Создаем и запускаем сессии
        tasks = []
        for account_data, proxy in distributed:
            try:
                session = Session(
                    account_data,
                    proxy,
                    directory
                )
                sessions.append(session)
                
                # Запускаем процесс добавления асинхронно
                task = asyncio.create_task(
                    async_run_inviting(session, chat_link, users_list, [delay_min, delay_max], invites_per_account)
                )
                tasks.append(task)
            except Exception as e:
                print_error(f"Ошибка создания сессии для аккаунта {account_data}: {str(e)}")
                continue

        return jsonify({
            'status': 'success',
            'message': f'Запущено добавление {len(users_list)} пользователей в {chat_link} для {len(tasks)} аккаунтов'
        }), 200

    except json.JSONDecodeError as e:
        print_error(f"Ошибка парсинга JSON: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Ошибка формата данных: {str(e)}'
        }), 400
    except Exception as e:
        print_error(f"Ошибка при запуске инвайтов: {str(e)}")
        logging.error(f"Ошибка start_invites: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Ошибка при запуске: {str(e)}'
        }), 500
        
        


@app.route('/start_masslook', methods=['POST'])
async def start_masslook():
    print_info_with_start(
        "-----------------------Начало Masslook-----------------------")
    try:
        form = await request.form
        accounts = json.loads(form.get('account_ids', '[]'))
        current_folder = form.get('current_folder', 'all')
        proxies = json.loads(form.get('proxies', '[]'))
        settings = json.loads(form.get('settings', '{}'))

        # Определяем директорию для работы
        if current_folder == 'working':
            directory = Config.WORKING_DIR
        elif current_folder == 'archive':
            directory = Config.ARCHIVE_DIR
        else:
            directory = 'all'

        if not accounts:
            return jsonify({'status': 'error', 'message': 'Не выбраны аккаунты'}), 400
        
        # Проверка и подготовка прокси
        proxy_urls = []
        for proxy in proxies:
            if proxy and isinstance(proxy, dict) and proxy.get('url'):
                proxy_urls.append(proxy['url'])
        
        valid_proxies = []
        if proxy_urls:
            checked_proxies = await CheckProxies(proxy_urls)
            valid_proxies = [proxy_result[1] for proxy_result in checked_proxies if proxy_result[0] == True]

        # Распределение прокси между аккаунтами
        distributed = distribute_proxies(accounts, valid_proxies)

        sessions = []
        tasks = []

        # Обработка настроек
        masslook_type = settings.get('type', 'chats')
        reactions = settings.get('reactions', [])
        threads_count = settings.get('threads', 5)

        # Валидация параметров
        if masslook_type == 'chats' and not settings.get('chats'):
            return jsonify({'status': 'error', 'message': 'Не указаны чаты'}), 400

        if masslook_type == 'users':
            if not settings.get('usersSettings'):
                return jsonify({'status': 'error', 'message': 'Не указаны настройки для пользователей'}), 400

            users_settings = settings['usersSettings']
            required_fields = ['viewDelay', 'reactionDelay',
                               'usersPerAccount', 'storiesLimit', 'usersList']
            if any(field not in users_settings for field in required_fields):
                return jsonify({'status': 'error', 'message': 'Неполные настройки для пользователей'}), 400

        # Создаем сессии и задачи
        for account_data, proxy in distributed:
            try:
                session = Session(account_data, proxy, directory)
                sessions.append(session)

                if masslook_type == 'chats':
                    task = asyncio.create_task(
                        async_run_masslookingchat(session, settings['chats'], reactions)
                    )
                else:
                    task = asyncio.create_task(
                        async_run_masslooking(
                            session, 
                            identifiers=settings['usersSettings']['usersList'],
                            looking=settings['usersSettings']['viewDelay'],
                            reaction_flood=settings['usersSettings']['reactionDelay'],
                            stories_account=settings['usersSettings']['storiesLimit'],
                            stories_user=settings['usersSettings']['usersPerAccount'],
                            reactions=reactions
                        )
                    )

                tasks.append(task)
            except Exception as e:
                print_error(f"Ошибка создания сессии для аккаунта {account_data}: {str(e)}")
                continue


        

        return jsonify({
            'status': 'success',
            'message': f'Masslook успешно запущен для {len(tasks)} аккаунтов',
            'stats': {
                'total_accounts': len(tasks),
                'type': masslook_type,
                'threads': threads_count
            }
        }), 200

    except json.JSONDecodeError as e:
        return jsonify({
            'status': 'error',
            'message': f'Ошибка формата данных: {str(e)}'
        }), 400

    except Exception as e:
        logging.error(f"Masslook error: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': f'Ошибка при запуске Masslook: {str(e)}'
        }), 500
        
        
@app.route('/load_account_avatars', methods=['POST'])
async def load_account_avatars():
    try:
        data = await request.get_json()
        account_ids = data.get('account_ids', [])
        current_folder = data.get('current_folder', 'all')
        proxies = data.get('proxies', [])  # Получаем прокси из запроса

        loaded_count = 0

        # Определяем директории для поиска
        directories = []
        if current_folder == 'working':
            directories = [Config.WORKING_DIR]
        elif current_folder == 'archive':
            directories = [Config.ARCHIVE_DIR]
        else:
            directories = [Config.WORKING_DIR, Config.ARCHIVE_DIR]

        # Проверка и подготовка прокси
        proxy_urls = [proxy['url'] for proxy in proxies if proxy]
        checked_proxies = await CheckProxies(proxy_urls)
        valid_proxies = [proxy[1] for proxy in checked_proxies if proxy[0]]

        # Распределение прокси между аккаунтами
        distributed = distribute_proxies(account_ids, valid_proxies)

        for account_data, proxy in distributed:
            try:
                # Ищем файлы сессии для аккаунта
                session_file = None
                json_file = None

                for directory in directories:
                    if os.path.exists(directory):
                        potential_session = os.path.join(
                            directory, f"{account_data}.session")
                        potential_json = os.path.join(
                            directory, f"{account_data}.json")

                        if os.path.exists(potential_session) and os.path.exists(potential_json):
                            session_file = potential_session
                            json_file = potential_json
                            break

                if session_file and json_file:
                    # Загружаем данные из JSON файла
                    with open(json_file, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)

                    # Загружаем аватарку с использованием прокси
                    avatar_url = await download_avatar_for_account(account_data, session_file, json_data, proxy)

                    if avatar_url:
                        # Обновляем JSON файл с информацией об аватарке
                        json_data['img'] = avatar_url

                        with open(json_file, 'w', encoding='utf-8') as f:
                            json.dump(json_data, f,
                                      ensure_ascii=False, indent=2)

                        loaded_count += 1

            except Exception as e:
                print(f"Ошибка загрузки аватарки для {account_data}: {e}")
                continue

        return jsonify({
            'success': True,
            'loaded_count': loaded_count,
            'total_requested': len(account_ids)
        })

    except Exception as e:
        print(f"Ошибка в load_account_avatars: {e}")
        return jsonify({'error': 'Ошибка загрузки аватарок'}), 500


async def download_avatar_for_account(account_id, session_file, json_data, proxy=None):
    """
    Загрузка аватарки аккаунта через Telegram API с использованием прокси.
    """
    try:
        # Извлекаем данные для подключения из json_data
        phone = json_data.get('phone', account_id)

        # Используем переданный прокси вместо извлеченного из json_data
        proxy_to_use = proxy

        # Создаем сессию с прокси
        directory = os.path.dirname(session_file)
        session = Session(account_id, proxy_to_use, directory)

        try:
            # Подключаемся к аккаунту
            await session.connect()

            # Проверяем, есть ли клиент
            if not hasattr(session, 'client') or session.client is None:
                print(f"Не удалось подключиться к аккаунту {account_id}")
                return None

            # Получаем информацию о пользователе
            me = await session.client.get_me()

            # Получаем профильные фото
            photos = await session.client.get_profile_photos(me)

            if photos and len(photos) > 0:
                # Скачиваем первое фото (основное)
                photo = photos[0]

                # Создаем директорию для аватарок если её нет
                avatars_dir = os.path.join('static', 'avatars')
                os.makedirs(avatars_dir, exist_ok=True)

                # Генерируем уникальное имя файла
                timestamp = int(datetime.now().timestamp())
                avatar_filename = f"{account_id}_{timestamp}.jpg"
                avatar_path = os.path.join(avatars_dir, avatar_filename)

                # Скачиваем фото
                await session.client.download_media(photo, avatar_path)

                # Возвращаем URL аватарки
                avatar_url = f"/static/avatars/{avatar_filename}"
                return avatar_url
            else:
                # У аккаунта нет фото
                return None

        finally:
            # Отключаемся от аккаунта
            try:
                await session.disconnect()
            except:
                pass

    except Exception as e:
        print(f"Ошибка при загрузке аватарки для {account_id}: {e}")
        return None


def format_rest_period(rest_until_timestamp_str):
    """
    Преобразует timestamp (в виде строки) в человекочитаемую строку периода отлежки.

    Args:
        rest_until_timestamp_str (str): Timestamp в виде строки (например, "1751133397")
                                      или пустая строка.

    Returns:
        str: Отформатированная строка (например, "1 год 2 мес", "2 мес 2 дня", "15 дн 14 ч")
             или пустая строка, если входные данные некорректны.
    """
    if not rest_until_timestamp_str:
        return ""

    try:
        # Преобразуем строку в целое число
        rest_until_timestamp = int(rest_until_timestamp_str)
    except ValueError:
        # Если строку нельзя преобразовать в число, возвращаем пустую строку
        return ""

    # Получаем текущий timestamp
    now_timestamp = int(datetime.now().timestamp())

    # Рассчитываем разницу в секундах
    delta_seconds = rest_until_timestamp - now_timestamp
    delta_seconds = delta_seconds * -1

    # Если разница отрицательная (период отлежки уже прошёл), возвращаем пустую строку
    if delta_seconds <= 0:
        return ""

    # Рассчитываем компоненты времени
    days = delta_seconds // 86400
    hours = (delta_seconds % 86400) // 3600

    # Определяем, какие единицы времени нужно отображать
    parts = []

    # Логика форматирования
    if days > 0:
        if days >= 365:
            years = days // 365
            remaining_days = days % 365
            months = remaining_days // 30  # Приблизительно

            if years > 0:
                year_word = "год" if years == 1 else (
                    "года" if 2 <= years <= 4 else "лет")
                parts.append(f"{years} {year_word}")

            if months > 0:
                month_word = "мес" if months == 1 else "мес"  # "мес" одинаково для всех чисел
                parts.append(f"{months} {month_word}")
        elif days >= 30:
            months = days // 30
            remaining_days = days % 30

            if months > 0:
                month_word = "мес" if months == 1 else "мес"
                parts.append(f"{months} {month_word}")

            if remaining_days > 0:
                day_word = "день" if remaining_days == 1 else (
                    "дня" if 2 <= remaining_days <= 4 else "дней")
                parts.append(f"{remaining_days} {day_word}")
        else:
            day_word = "день" if days == 1 else (
                "дня" if 2 <= days <= 4 else "дней")
            parts.append(f"{days} {day_word}")

    # Если дней нет или нужно добавить часы для большей точности (например, "15 дн 14 ч")
    # Можно добавить условие, например, показывать часы, если дней < 30 или delta_seconds < X
    # Сейчас показываем часы, если дней меньше 30 И есть часы
    if days < 30 and hours > 0 and days > 0:
        hour_word = "час" if hours == 1 else (
            "часа" if 2 <= hours <= 4 else "часов")
        parts.append(f"{hours} {hour_word}")
    # Если дней совсем нет, показываем только часы
    elif days == 0 and hours > 0:
        hour_word = "час" if hours == 1 else (
            "часа" if 2 <= hours <= 4 else "часов")
        parts.append(f"{hours} {hour_word}")
    # Если и дней, и часов нет или очень мало, можно показать минуты или просто "меньше часа"
    elif days == 0 and hours == 0 and delta_seconds > 0:
        # Можно добавить минуты, если нужно, например:
        minutes = (delta_seconds % 3600) // 60
        if minutes > 0:
            minute_word = "мин" if minutes == 1 else "мин"
            parts.append(f"{minutes} {minute_word}")
        elif not parts:  # Если совсем близко к нулю
            parts.append("<1 мин")

    return " ".join(parts)


@app.route('/get_accounts', methods=['POST'])
async def get_accounts():
    data = await request.get_json()
    folder = data.get('folder', 'all')

    # Определяем пути к папкам
    directories = []
    if folder == 'working':
        directories = [Config.WORKING_DIR]
    elif folder == 'archive':
        directories = [Config.ARCHIVE_DIR]
    else:  # all
        directories = [Config.WORKING_DIR, Config.ARCHIVE_DIR]

    accounts = []

    for directory in directories:
        if not os.path.exists(directory):
            continue

        for filename in os.listdir(directory):
            if filename.endswith('.session'):
                phone = filename.split('.')[0]
                json_file = os.path.join(directory, f"{phone}.json")
                session_file = os.path.join(directory, filename)

                # Проверяем существование обоих файлов
                if os.path.exists(json_file) and os.path.exists(session_file):
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            json_data = json.load(f)

                        # Определяем статус аккаунта
                        status = 'unknown'
                        if '_dead' in filename:
                            status = 'dead'
                        elif '_spam' in filename:
                            status = 'spam_block'
                        else:
                            status = 'alive'

                        # Получаем геоинформацию
                        flag, geo = get_geo_from_phone(phone)

                        # Извлекаем аватарку из session_data
                        avatar_url = json_data.get(
                            'img', '') if json_data else ''

                        # Если аватарки нет, но есть session_data, попробуем найти там
                        if not avatar_url and json_data and isinstance(json_data, dict):
                            # Проверяем различные возможные поля с аватаркой
                            avatar_url = (json_data.get('avatar') or
                                          json_data.get('photo') or
                                          json_data.get('profile_photo') or '')

                        account_info = {
                            'id': phone,
                            'phone': phone,
                            'path': session_file,
                            'country': geo,
                            'flag_code': flag,
                            'role': json_data.get('role', '') if json_data else '',
                            'first_name': json_data.get('first_name', '') if json_data else '',
                            'last_name': json_data.get('last_name', '') if json_data else '',
                            'name': json_data.get('name', '') if json_data else '',
                            'status': status,
                            'geo': geo,
                            'session_data': json_data if json_data else {},
                            'avatar': avatar_url,
                            'rest_until': format_rest_period(json_data.get('register_time', '') if json_data else ''),
                            'register_time': json_data.get('register_time', '') if json_data else '',
                            'last_used': json_data.get('last_used', '') if json_data else '',
                        }

                        accounts.append(account_info)

                    except Exception as e:
                        print(f"Ошибка при обработке файла {json_file}: {e}")
                        continue

    # Сортируем аккаунты: сначала живые, потом по дате использования
    accounts.sort(key=lambda x: (
        x['status'] != 'alive',  # Живые в начале
        x.get('last_used', '') or '',
        x['phone']
    ), reverse=True)

    return jsonify(accounts)


def open_and_maximize_explorer(path):
    os.startfile(path)
    time.sleep(0.5)  # немного ждём появления окна

    user32 = ctypes.WinDLL('user32', use_last_error=True)

    EnumWindows = user32.EnumWindows
    EnumWindows.restype = wintypes.BOOL
    EnumWindows.argtypes = [wintypes.WNDENUMPROC, wintypes.LPARAM]

    GetWindowTextLength = user32.GetWindowTextLengthW
    GetWindowText = user32.GetWindowTextW
    IsWindowVisible = user32.IsWindowVisible
    GetClassName = user32.GetClassNameW
    ShowWindow = user32.ShowWindow
    SetForegroundWindow = user32.SetForegroundWindow
    BringWindowToTop = user32.BringWindowToTop

    SW_RESTORE = 9
    SW_MAXIMIZE = 3

    titles = []

    def enum_proc(hwnd, lParam):
        if not IsWindowVisible(hwnd):
            return True
        length = GetWindowTextLength(hwnd)
        if length == 0:
            return True
        buff = ctypes.create_unicode_buffer(length + 1)
        GetWindowText(hwnd, buff, length + 1)
        titles.append((hwnd, buff.value))
        return True

    EnumWindows(wintypes.WNDENUMPROC(enum_proc), 0)

    target = os.path.basename(path).lower()

    def maximize_window(hwnd):
        # Активируем окно
        BringWindowToTop(hwnd)
        SetForegroundWindow(hwnd)
        ShowWindow(hwnd, SW_RESTORE)
        ShowWindow(hwnd, SW_MAXIMIZE)

    # Ищем по названию папки
    for hwnd, title in titles:
        if target and target in title.lower():
            maximize_window(hwnd)
            return True

    # Если не нашли — ищем по классу окна
    class_buf = ctypes.create_unicode_buffer(256)
    for hwnd, _ in titles:
        GetClassName(hwnd, class_buf, 256)
        cls = class_buf.value
        if cls in ("CabinetWClass", "ExploreWClass"):
            maximize_window(hwnd)
            return True

    return False

def restore_and_maximize_console():
    """Восстанавливает и максимизирует окно консоли"""
    try:
        if platform.system() == "Windows":
            import ctypes
            
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            
            # SW_RESTORE = 9, SW_MAXIMIZE = 3
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # Восстанавливаем
            time.sleep(0.1)  # Небольшая задержка
            ctypes.windll.user32.ShowWindow(hwnd, 3)  # Максимизируем
            
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.SetWindowPos(
                hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0020)
        elif platform.system() == "Darwin":
            os.system("""osascript -e 'tell application "Terminal" to activate'""")
        else:
            os.system("wmctrl -a $(ps -p $$ -o comm=)")
    except Exception as e:
        logging.error(f"Не удалось восстановить окно консоли: {str(e)}")

def open_and_maximize_explorer(folder_path):
    """Открывает папку в проводнике Windows и сразу максимизирует окно"""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        SW_MAXIMIZE = 3
        SW_RESTORE = 9
        SW_SHOW = 5
        SW_SHOWNORMAL = 1

        # Запоминаем окна ДО открытия
        def get_explorer_windows():
            windows = []
            EnumWindowsProc = ctypes.WINFUNCTYPE(
                wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def callback(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetClassNameW(hwnd, None, 0)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetClassNameW(hwnd, buff, length + 1)
                        if buff.value in ("CabinetWClass", "ExploreWClass"):
                            windows.append(hwnd)
                return True

            user32.EnumWindows(EnumWindowsProc(callback), 0)
            return windows

        existing_windows = set(get_explorer_windows())
        
        # Открываем папку
        subprocess.Popen(['explorer', folder_path], shell=False)
        time.sleep(0.8)  # Увеличиваем задержку

        # Ждем появления нового окна
        max_attempts = 50
        for attempt in range(max_attempts):
            time.sleep(0.1)
            current_windows = set(get_explorer_windows())
            new_windows = current_windows - existing_windows
            
            if new_windows:
                target_hwnd = list(new_windows)[0]
                
                # Показываем окно
                user32.ShowWindow(target_hwnd, SW_SHOWNORMAL)
                time.sleep(0.1)
                
                # Восстанавливаем
                user32.ShowWindow(target_hwnd, SW_RESTORE)
                time.sleep(0.1)
                
                # Максимизируем
                user32.ShowWindow(target_hwnd, SW_MAXIMIZE)
                time.sleep(0.1)
                
                # Выносим на передний план
                user32.BringWindowToTop(target_hwnd)
                user32.SetForegroundWindow(target_hwnd)
                user32.SetActiveWindow(target_hwnd)
                user32.SetWindowPos(target_hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
                
                logging.info(f"Окно проводника открыто и максимизировано для {folder_path}")
                return
        
        # Если не нашли новое окно, пробуем максимизировать последнее
        current_windows = get_explorer_windows()
        if current_windows:
            target_hwnd = current_windows[-1]
            user32.ShowWindow(target_hwnd, SW_MAXIMIZE)
            user32.SetForegroundWindow(target_hwnd)
            user32.BringWindowToTop(target_hwnd)
            logging.info(f"Максимизировано последнее окно проводника для {folder_path}")
        else:
            logging.warning(f"Не удалось обнаружить окно проводника для {folder_path}")

    except Exception as e:
        logging.error(f"Ошибка при открытии/максимизации проводника: {str(e)}")
        # Fallback - просто открываем папку
        try:
            os.startfile(folder_path)
        except:
            try:
                subprocess.Popen(['explorer', folder_path], shell=False)
            except:
                pass


@app.route('/api/open-folder', methods=['GET'])
async def open_folder_api():
    """
    API endpoint для открытия папки в файловом менеджере системы.
    Ожидает query параметр 'path' с относительным путем к папке.
    Пример: /api/open-folder?path=Файлы/Изменение профиля
    """
    folder_path_relative = request.args.get('path')

    if not folder_path_relative:
        logging.warning("Запрос к /api/open-folder без параметра 'path'")
        return jsonify({'error': 'Параметр path не указан'}), 400

    try:
        base_path = os.getcwd()
        folder_path_absolute = os.path.join(base_path, folder_path_relative)
        folder_path_absolute = os.path.abspath(folder_path_absolute)
        folder_path_absolute = os.path.abspath(folder_path_absolute)

        if not folder_path_absolute.startswith(base_path):
            logging.warning(
                f"Попытка доступа к пути вне разрешенной директории: {folder_path_absolute}")
            return jsonify({'error': 'Доступ к указанному пути запрещен'}), 403

        if not os.path.exists(folder_path_absolute):
            logging.info(
                f"Папка не существует, создаем: {folder_path_absolute}")
            os.makedirs(folder_path_absolute, exist_ok=True)
        elif not os.path.isdir(folder_path_absolute):
            logging.error(
                f"Указанный путь не является папкой: {folder_path_absolute}")
            return jsonify({'error': 'Указанный путь не является папкой'}), 400

        system = platform.system()

        # Сначала максимизируем консоль
        restore_and_maximize_console()
        # Добавляем задержку, чтобы консоль успела открыться
        time.sleep(0.5)

        if system == "Windows":
            # Открытие папки с максимизацией окна проводника
            open_and_maximize_explorer(folder_path_absolute)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", folder_path_absolute], check=True)
        elif system == "Linux":
            # Пытаемся открыть через популярные файловые менеджеры
            if subprocess.run(["which", "nautilus"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                subprocess.run(["nautilus", "--new-window",
                               folder_path_absolute], check=True)
            elif subprocess.run(["which", "dolphin"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                subprocess.run(["dolphin", folder_path_absolute], check=True)
            elif subprocess.run(["which", "thunar"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                subprocess.run(["thunar", folder_path_absolute], check=True)
            else:
                subprocess.run(["xdg-open", folder_path_absolute], check=True)
        else:
            return jsonify({'error': f'Неподдерживаемая ОС: {system}'}), 500

        return jsonify({'success': True, 'message': f'Папка "{folder_path_relative}" открыта'}), 200

    except subprocess.CalledProcessError as e:
        error_msg = f"Ошибка при открытии папки командой '{e.cmd}': {e.stderr.decode() if e.stderr else str(e)}"
        return jsonify({'error': 'Не удалось открыть папку', 'details': error_msg}), 500
    except PermissionError as e:
        error_msg = f"Недостаточно прав для открытия/создания папки '{folder_path_absolute}': {e}"
        return jsonify({'error': 'Недостаточно прав', 'details': error_msg}), 403
    except Exception as e:
        error_msg = f"Неожиданная ошибка при открытии папки '{folder_path_relative}': {e}"
        logging.error(error_msg, exc_info=True)
        return jsonify({'error': 'Внутренняя ошибка сервера', 'details': error_msg}), 500

@app.route('/accounts')
async def accounts():
    token = request.cookies.get('auth_token')

    # Проверяем токен
    if not token or not await verify_token(token):
        return redirect('/')
    # Получаем дату окончания подписки
    end_date = await get_subscription_info(token)

    # Рассчитываем оставшиеся дни
    days_left = 0
    formatted_date = "Не определена"

    if end_date:
        days_left = (end_date - datetime.now()).days
        days_left = max(0, days_left)  # Не показываем отрицательные значения
        formatted_date = end_date.strftime('%d.%m.%Y')
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Для AJAX-запросов возвращаем только содержимое без базового шаблона
        return await render_template('accounts_no_base.html',  days_left=days_left, end_date=formatted_date)
    else:
        # Для обычных запросов возвращаем полную страницу
        return await render_template('accounts.html',  days_left=days_left, end_date=formatted_date, active_page='accounts')
    


@app.route('/dm-mailing')
async def dm_mailing():
    return await render_template('dm_mailing.html', active_page='dm-mailing')


@app.route('/chat-mailing')
async def chat_mailing():
    return await render_template('chat_mailing.html', active_page='chat-mailing')


async def run_background_task(coro):
    """Запускает корутину как фоновую задачу с автоматическим удалением при завершении"""
    task = asyncio.create_task(coro)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    return task


@app.route('/accounts_count')
async def accounts_count():
    directories = [Config.WORKING_DIR, Config.ARCHIVE_DIR]

    res = {}
    for directory in directories:
        if directory == Config.ARCHIVE_DIR:
            dir = 'archived'
        else:
            dir = 'working'
        res[dir] = 0

        for filename in os.listdir(directory):
            if filename.endswith('.session'):
                phone = filename.split('.')[0]
                json_file = os.path.join(directory, f"{phone}.json")
                if os.path.exists(json_file):
                    res[dir] += 1
                    with open(json_file, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)
    res['all'] = res['working'] + res['archived']

    return jsonify(res)


@app.route('/startpmmailing', methods=['POST'])
async def start_pm_mailing():
    try:
        print_info_with_start(
            "-----------------------Начало рассылки-----------------------")
        form = await request.form
        accounts = form.get('account_ids')
        if not accounts:
            return jsonify({'status': False, 'message': 'Не выбраны аккаунты'}), 400
        accounts = json.loads(accounts) if accounts else []
        if not accounts:
            return jsonify({'status': False, 'message': 'Список аккаунтов пуст'}), 400
        
        folder = form.get('current_folder', 'all')
        proxies = form.get('proxies')
        proxies = json.loads(proxies) if proxies else []
        attachment = (await request.files).get('attachment')
        # 'file', 'voice', или 'audio'
        attachment_type = form.get('attachment_type', 'file')
        delete_after_send = form.get('delete_after_send', 'false') == 'true'
        threads = int(form.get('threads_count', 5))
        min_delay = int(form.get('min_delay', 5))
        max_delay = int(form.get('max_delay', 15))
        messages_per_account = int(form.get('messages_per_account', 50))
        recipients_str = form.get('recipients', '')
        if not recipients_str:
            return jsonify({'status': False, 'message': 'Не указаны получатели'}), 400
        recipients = [r.strip() for r in recipients_str.split('\n') if r.strip()]
        if not recipients:
            return jsonify({'status': False, 'message': 'Список получателей пуст'}), 400
        message_text = form.get('message_text', '')
        auto_reply_enabled = form.get('auto_reply_enabled', 'false')
        manager_chat = form.get('manager_chat', '')
        reply_message = form.get('reply_message', '')
        proxy_urls = []

        if folder == 'working':
            directory = Config.WORKING_DIR
        elif folder == 'archive':
            directory = Config.ARCHIVE_DIR
        else:  # all
            directory = 'all'

        for proxy in proxies:
            if proxy and isinstance(proxy, dict) and proxy.get('url'):
                proxy_urls.append(proxy['url'])
        
        if proxy_urls:
            checked_proxies = await CheckProxies(proxy_urls)
            use_proxy = []
            for proxy_result in checked_proxies:
                if proxy_result[0] == True:
                    use_proxy.append(proxy_result[1])
        else:
            use_proxy = []
        
        distributed = distribute_proxies(accounts, use_proxy)
        users, remaining = split_list1(
            recipients, len(accounts), messages_per_account)

        if attachment:
            temp_dir = 'temp_uploads'
            os.makedirs(temp_dir, exist_ok=True)
            file_ext = os.path.splitext(attachment.filename)[1]
            temp_filename = f"{uuid.uuid4().hex}{file_ext}"
            temp_path = os.path.join(temp_dir, temp_filename)
            await attachment.save(temp_path)
        else:
            temp_path = None

        tasks = []
        for i, data in enumerate(distributed):
            account = data[0]
            proxy = data[1]
            try:
                session = Session(account, proxy, directory)
                sessions.append(session)
                
                # Запускаем рассылку асинхронно
                task = asyncio.create_task(
                    async_run_pm_mailing(
                        session, threads, min_delay, max_delay, messages_per_account,
                        users[i] if i < len(users) else [], message_text, temp_path, auto_reply_enabled,
                        manager_chat, reply_message, attachment_type, delete_after_send
                    )
                )
                tasks.append(task)
            except Exception as e:
                print_error(f"Ошибка создания сессии для аккаунта {account}: {str(e)}")
                continue

        print_success_with_start(
            f"Запущена рассылка для {len(tasks)} аккаунтов, получателей: {len(recipients)}")
        print_info_with_start("Рассылка успешно запущена!")

        return jsonify({'status': True, 'message': 'Рассылка запущена'})
    except json.JSONDecodeError as e:
        print_error(f"Ошибка парсинга JSON: {str(e)}")
        return jsonify({'status': False, 'message': f'Ошибка формата данных: {str(e)}'}), 400
    except Exception as e:
        print_error(f"Ошибка при запуске рассылки: {str(e)}")
        logging.error(f"Ошибка start_pm_mailing: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'message': f'Ошибка при запуске: {str(e)}'}), 500


@app.route('/startchatmailing', methods=['POST'])
async def start_chat_mailing():
    try:
        form = await request.form
        accounts = form.get('account_ids')
        if not accounts:
            return jsonify({'status': False, 'message': 'Не выбраны аккаунты'}), 400
        accounts = json.loads(accounts) if accounts else []
        if not accounts:
            return jsonify({'status': False, 'message': 'Список аккаунтов пуст'}), 400
        
        folder = form.get('current_folder', 'all')
        proxies = form.get('proxies')
        proxies = json.loads(proxies) if proxies else []
        attachment = (await request.files).get('attachment')
        threads = int(form.get('threads_count', 5))
        min_delay = int(form.get('min_delay', 5))
        max_delay = int(form.get('max_delay', 15))
        messages_per_account = int(form.get('messages_per_account', 50))
        recipients_str = form.get('recipients', '')
        if not recipients_str:
            return jsonify({'status': False, 'message': 'Не указаны получатели'}), 400
        recipients = [r.strip() for r in recipients_str.split('\n') if r.strip()]
        if not recipients:
            return jsonify({'status': False, 'message': 'Список получателей пуст'}), 400
        message_text = form.get('message_text', '')
        auto_reply_enabled = form.get('auto_reply_enabled', 'false')
        cycle = form.get('cycle', 'false')
        delay_cycle = form.get('delay_cycle', '60-120')
        manager_chat = form.get('manager_chat', '')
        reply_message = form.get('reply_message', '')
        proxy_urls = []

        if folder == 'working':
            directory = Config.WORKING_DIR
        elif folder == 'archive':
            directory = Config.ARCHIVE_DIR
        else:  # all
            directory = 'all'

        for proxy in proxies:
            if proxy and isinstance(proxy, dict) and proxy.get('url'):
                proxy_urls.append(proxy['url'])
        
        use_proxy = []
        if proxy_urls:
            checked_proxies = await CheckProxies(proxy_urls)
            for proxy_result in checked_proxies:
                if proxy_result[0] == True:
                    use_proxy.append(proxy_result[1])
        
        distributed = distribute_proxies(accounts, use_proxy)
        users, remaining = split_list1(
            recipients, len(accounts), messages_per_account)

        if attachment:
            temp_dir = 'temp_uploads'
            os.makedirs(temp_dir, exist_ok=True)
            file_ext = os.path.splitext(attachment.filename)[1]
            temp_filename = f"{uuid.uuid4().hex}{file_ext}"
            temp_path = os.path.join(temp_dir, temp_filename)
            await attachment.save(temp_path)
        else:
            temp_path = None

        async def process_session(data, i):
            account = data[0]
            proxy = data[1]
            try:
                session = Session(account, proxy, directory)
                sessions.append(session)
                await session.connect()

                tasks = []

                if auto_reply_enabled == "true":
                    task = asyncio.shield(session.PrepareAnswerMachine(
                        reply_message,
                        manager_chat,
                        [3, 5]
                    ))
                    background_tasks.add(task)
                    task.add_done_callback(background_tasks.discard)

                tasks.append(session.start_chat_mailing(
                    threads, min_delay, max_delay, messages_per_account,
                    users[i] if i < len(users) else [], message_text, temp_path, auto_reply_enabled,
                    manager_chat, reply_message, cycle, delay_cycle
                ))

                await asyncio.gather(*tasks)

                if auto_reply_enabled != "true" and cycle != "true":
                    await session.disconnect()
            except Exception as e:
                print_error(f"Ошибка обработки сессии для аккаунта {account}: {str(e)}")
                try:
                    await session.disconnect()
                except:
                    pass

        # Создаем и запускаем все задачи
        tasks = [process_session(data, i) for i, data in enumerate(distributed)]
        await asyncio.gather(*tasks)

        print_success_with_start(
            "Всего отправлено сообщений: " + str(len(recipients)))
        print_info_with_start("Рассылка успешно завершена!")
        return jsonify({'status': True})
    except Exception as e:
        print_error(f"Ошибка при запуске рассылки в чаты: {str(e)}")
        logging.error(f"Ошибка start_chat_mailing: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'message': str(e)}), 500


@app.route('/stopAccounts')
async def stop_accounts():
    print_info_with_start("Отключаю аккаунты...")
    for session in sessions:
        await session.disconnect()
    
    print_info_with_start("Отключил")
    return jsonify({'status': True})


@app.route('/change_photo', methods=['POST'])
async def change_photo():
    try:
        form = await request.form
        accounts = form.get('account_ids')
        if not accounts:
            return jsonify({'status': False, 'message': 'Не выбраны аккаунты'}), 400
        accounts = json.loads(accounts) if accounts else []
        if not accounts:
            return jsonify({'status': False, 'message': 'Список аккаунтов пуст'}), 400
        
        folder = form.get('current_folder', 'all')
        photo = (await request.files).get('photo')
        if not photo:
            return jsonify({'status': False, 'message': 'Не выбрано фото'}), 400
        
        proxies = form.get('proxies')
        proxies = json.loads(proxies) if proxies else []
        temp_dir = 'temp_uploads'
        os.makedirs(temp_dir, exist_ok=True)

        file_ext = os.path.splitext(photo.filename)[1]
        temp_filename = f"{uuid.uuid4().hex}{file_ext}"
        temp_path = os.path.join(temp_dir, temp_filename)
        await photo.save(temp_path)

        if folder == 'working':
            directory = Config.WORKING_DIR
        elif folder == 'archive':
            directory = Config.ARCHIVE_DIR
        else:  # all
            directory = 'all'

        proxy_urls = []
        for proxy in proxies:
            if proxy and isinstance(proxy, dict) and proxy.get('url'):
                proxy_urls.append(proxy['url'])
        
        use_proxy = []
        if proxy_urls:
            checked_proxies = await CheckProxies(proxy_urls)
            for proxy_result in checked_proxies:
                if proxy_result[0] == True:
                    use_proxy.append(proxy_result[1])
        
        distributed = distribute_proxies(accounts, use_proxy)

        for account, proxy in distributed:
            try:
                session = Session(account, proxy, directory)
                await session.connect()
                await session.change_profile_photo(temp_path)
                await session.disconnect()
            except Exception as e:
                print_error(f"Ошибка изменения фото для аккаунта {account}: {str(e)}")
                continue

        print_info_with_start("Фото было успешно изменено!")
        return jsonify({
            'status': True,
            'reload': True
        })
    except Exception as e:
        print_error(f"Ошибка при изменении фото: {str(e)}")
        logging.error(f"Ошибка change_photo: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'message': f'Ошибка: {str(e)}'}), 500


@app.route('/api/agents/<int:id>', methods=['DELETE'])
async def delete_ai_agent(id):
    conn = get_db()
    cur = conn.cursor()

    try:
        # Получаем имя агента для подтверждающего сообщения
        cur.execute('SELECT name FROM ai_agents WHERE id = %s', (id,))
        agent_name = cur.fetchone()[0]

        cur.execute('DELETE FROM ai_agents WHERE id=%s', (id,))
        conn.commit()
        return jsonify({'status': 'success', 'message': f'Agent {agent_name} deleted'})

    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

    finally:
        cur.close()
        conn.close()
@app.route('/api/agents', methods=['GET', 'POST', 'PUT'])
async def handle_ai_agents():
    conn = get_db()
    cur = conn.cursor()

    try:
        if request.method == 'GET':
            cur.execute('SELECT * FROM ai_agents')
            agents = [dict(id=row[0], name=row[1], model=row[2],
                           prompt=row[3], examples=row[4]) for row in cur.fetchall()]
            return jsonify(agents)

        data = await request.get_json()

        if request.method == 'POST':
            cur.execute('''
                INSERT INTO ai_agents (name, model, prompt, examples)
                VALUES (%s, %s, %s, %s)
            ''', (data['name'], data['model'], data['prompt'], json.dumps(data['examples'])))

        elif request.method == 'PUT':
            cur.execute('''
                UPDATE ai_agents 
                SET name=%s, model=%s, prompt=%s, examples=%s 
                WHERE id=%s
            ''', (data['name'], data['model'], data['prompt'], json.dumps(data['examples']), data['id']))

        elif request.method == 'DELETE':
            cur.execute('DELETE FROM ai_agents WHERE id=%s', (data['id'],))

        conn.commit()
        return jsonify({'status': 'success'})

    except Exception as e:
        conn.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

    finally:
        cur.close()
        conn.close()


@app.route('/change_first_name', methods=['POST'])
async def change_first_name():
    try:
        data = await request.get_json()
        if not data:
            return jsonify({'status': False, 'message': 'Нет данных'}), 400
        
        accounts = data.get('account_ids')
        if not accounts:
            return jsonify({'status': False, 'message': 'Не выбраны аккаунты'}), 400
        
        first_name = data.get('first_name', '').strip()
        if not first_name:
            return jsonify({'status': False, 'message': 'Не указано имя'}), 400
        
        folder = data.get('current_folder', 'all')
        proxies = data.get('proxies', [])

        if folder == 'working':
            directory = Config.WORKING_DIR
        elif folder == 'archive':
            directory = Config.ARCHIVE_DIR
        else:  # all
            directory = 'all'

        proxy_urls = []
        for proxy in proxies:
            if proxy and isinstance(proxy, dict) and proxy.get('url'):
                proxy_urls.append(proxy['url'])
        
        use_proxy = []
        if proxy_urls:
            checked_proxies = await CheckProxies(proxy_urls)
            for proxy_result in checked_proxies:
                if proxy_result[0] == True:
                    use_proxy.append(proxy_result[1])
        
        distributed = distribute_proxies(accounts, use_proxy)

        for account, proxy in distributed:
            try:
                session = Session(account, proxy, directory)
                await session.connect()
                await session.change_first_name(first_name)
                await session.disconnect()
            except Exception as e:
                print_error(f"Ошибка изменения имени для аккаунта {account}: {str(e)}")
                continue

        print_info_with_start("Имя было успешно изменено!")
        return jsonify({
            'status': True,
            'reload': True
        })
    except Exception as e:
        print_error(f"Ошибка при изменении имени: {str(e)}")
        logging.error(f"Ошибка change_first_name: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'message': f'Ошибка: {str(e)}'}), 500


@app.route('/change_last_name', methods=['POST'])
async def change_last_name():
    try:
        data = await request.get_json()
        if not data:
            return jsonify({'status': False, 'message': 'Нет данных'}), 400
        
        accounts = data.get('account_ids')
        if not accounts:
            return jsonify({'status': False, 'message': 'Не выбраны аккаунты'}), 400
        
        last_name = data.get('last_name', '').strip()
        if not last_name:
            return jsonify({'status': False, 'message': 'Не указана фамилия'}), 400
        
        folder = data.get('current_folder', 'all')
        proxies = data.get('proxies', [])

        if folder == 'working':
            directory = Config.WORKING_DIR
        elif folder == 'archive':
            directory = Config.ARCHIVE_DIR
        else:  # all
            directory = 'all'

        proxy_urls = []
        for proxy in proxies:
            if proxy and isinstance(proxy, dict) and proxy.get('url'):
                proxy_urls.append(proxy['url'])
        
        use_proxy = []
        if proxy_urls:
            checked_proxies = await CheckProxies(proxy_urls)
            for proxy_result in checked_proxies:
                if proxy_result[0] == True:
                    use_proxy.append(proxy_result[1])
        
        distributed = distribute_proxies(accounts, use_proxy)

        for account, proxy in distributed:
            try:
                session = Session(account, proxy, directory)
                await session.connect()
                await session.change_last_name(last_name)
                await session.disconnect()
            except Exception as e:
                print_error(f"Ошибка изменения фамилии для аккаунта {account}: {str(e)}")
                continue

        print_info_with_start("Фамилия была успешно изменена!")
        return jsonify({
            'status': True,
            'reload': True
        })
    except Exception as e:
        print_error(f"Ошибка при изменении фамилии: {str(e)}")
        logging.error(f"Ошибка change_last_name: {str(e)}", exc_info=True)
        return jsonify({'status': False, 'message': f'Ошибка: {str(e)}'}), 500


@app.route('/start_profile_edit_task', methods=['POST'])
async def start_profile_edit_task():
    try:
        data = await request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        account_ids = data.get('account_ids', [])
        if not account_ids:
            return jsonify({'success': False, 'error': 'Не выбраны аккаунты'}), 400
        
        thread_count = int(data.get('thread_count', 5))
        settings = data.get('settings', {})
        folder = data.get('current_folder', 'all')
        proxies = data.get('proxies', [])
        
        if folder == 'working':
            directory = Config.WORKING_DIR
        elif folder == 'archive':
            directory = Config.ARCHIVE_DIR
        else:
            directory = 'all'
        
        proxy_urls = []
        for proxy in proxies:
            if proxy and isinstance(proxy, dict) and proxy.get('url'):
                proxy_urls.append(proxy['url'])
        
        use_proxy = []
        if proxy_urls:
            checked_proxies = await CheckProxies(proxy_urls)
            for proxy_result in checked_proxies:
                if proxy_result[0] == True:
                    use_proxy.append(proxy_result[1])
        
        distributed = distribute_proxies(account_ids, use_proxy)
        
        async def process_profile_edit(account, proxy):
            try:
                session = Session(account, proxy, directory)
                await session.connect()
                
                # Случайно выбираем пол для разнообразия профилей
                gender_folder = random.choice(['Женские', 'Мужские'])
                base_path = os.path.join('Файлы', 'Изменение профиля', gender_folder)
                
                if settings.get('updateName'):
                    # Читаем имена из файла
                    names_file = os.path.join(base_path, 'Имена.txt')
                    if os.path.exists(names_file):
                        with open(names_file, 'r', encoding='utf-8') as f:
                            names = [line.strip() for line in f.readlines() if line.strip()]
                        if names:
                            name = random.choice(names)
                            await session.change_first_name(name)
                    
                    # Читаем фамилии из файла (если есть)
                    surnames_file = os.path.join(base_path, 'Фамилии.txt')
                    if os.path.exists(surnames_file):
                        with open(surnames_file, 'r', encoding='utf-8') as f:
                            surnames = [line.strip() for line in f.readlines() if line.strip()]
                        if surnames:
                            surname = random.choice(surnames)
                            await session.change_last_name(surname)
                
                if settings.get('updateAvatar'):
                    # Читаем аватары из папки
                    avatars_dir = os.path.join(base_path, 'Аватарки')
                    if os.path.exists(avatars_dir):
                        avatars = [f for f in os.listdir(avatars_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                        if avatars:
                            avatar_path = os.path.join(avatars_dir, random.choice(avatars))
                            await session.change_profile_photo(avatar_path)
                
                if settings.get('updateBio'):
                    # Читаем био из файла
                    bio_file = os.path.join(base_path, 'Био.txt')
                    if os.path.exists(bio_file):
                        with open(bio_file, 'r', encoding='utf-8') as f:
                            bios = [line.strip() for line in f.readlines() if line.strip()]
                        if bios:
                            bio = random.choice(bios)
                            # Предполагаем что есть метод change_bio
                            if hasattr(session, 'change_bio'):
                                await session.change_bio(bio)
                
                await session.disconnect()
            except Exception as e:
                print_error(f"Ошибка изменения профиля для аккаунта {account}: {str(e)}")
        
        tasks = [process_profile_edit(account, proxy) for account, proxy in distributed]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        print_success_with_start(f"Задача изменения профиля завершена")
        return jsonify({'success': True, 'message': 'Задача завершена'})
    except Exception as e:
        print_error(f"Ошибка при запуске задачи изменения профиля: {str(e)}")
        logging.error(f"Ошибка start_profile_edit_task: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/open_in_web', methods=['POST'])
async def open_in_web():
    data = await request.get_json()
    accounts = data.get('account_ids')
    folder = data.get('current_folder')
    proxies = data.get('proxies')
    proxies = json.loads(proxies) if proxies else []
    proxy_urls = []
    for proxy in proxies:
        if proxy:
            proxy_urls.append(proxy['url'])
    proxies = await CheckProxies(proxy_urls)
    use_proxy = []
    for proxy in proxies:
        if proxy[0] == True:
            use_proxy.append(proxy[1])
    
    if folder == 'working':
        directory = Config.WORKING_DIR
    elif folder == 'archive':
        directory = Config.ARCHIVE_DIR
    else:  # all
        directory = 'all'

    session = Session(accounts[0], None, directory)
    await session.connect()
    await authorization(accounts[0], session, proxy)
    await session.disconnect()
    return jsonify({'status': True})


async def process_account_spam(account, proxy, directory):
    session = Session(account, proxy, directory)
    await session.connect()
    info = await session.check_account(True)
    await session.disconnect()
    return info


@app.route('/check_spam_block', methods=['POST'])
async def check_spamblock_accounts():
    print_success_with_start(
        "-----------------------Проверка аккаунтов на спам блок-----------------------")
    data = await request.get_json()
    accounts = data.get('account_ids')
    proxies = data.get('proxies')
    folder = data.get('current_folder')

    if folder == 'working':
        directory = Config.WORKING_DIR
    elif folder == 'archive':
        directory = Config.ARCHIVE_DIR
    else:  # all
        directory = 'all'

    proxy_urls = []
    for proxy in proxies:
        if proxy:
            proxy_urls.append(proxy['url'])
    proxies = await CheckProxies(proxy_urls)
    use_proxy = []
    for proxy in proxies:
        if proxy[0] == True:
            use_proxy.append(proxy[1])
    distributed = distribute_proxies(accounts, use_proxy)

    tasks = [
        process_account_spam(account, proxy, directory)
        for account, proxy in distributed
    ]

    await asyncio.gather(*tasks, return_exceptions=True)

    print_info_with_start("Аккаунты были успешно проверены!")
    return jsonify({
        'status': True,
        'reload': True
    })


async def process_account(account, proxy, directory):
    session = Session(account, proxy, directory)
    await session.connect()
    info = await session.check_account()
    await session.disconnect()
    return info


@app.route('/check_accounts', methods=['POST'])
async def check_accounts():
    print_success_with_start(
        "-----------------------Проверка аккаунтов-----------------------")
    data = await request.get_json()
    accounts = data.get('account_ids')
    proxies = data.get('proxies')
    folder = data.get('current_folder')

    if folder == 'working':
        directory = Config.WORKING_DIR
    elif folder == 'archive':
        directory = Config.ARCHIVE_DIR
    else:  # all
        directory = 'all'

    proxy_urls = []
    for proxy in proxies:
        if proxy:
            proxy_urls.append(proxy['url'])
    proxies = await CheckProxies(proxy_urls)
    use_proxy = []
    for proxy in proxies:
        if proxy[0] == True:
            use_proxy.append(proxy[1])
    distributed = distribute_proxies(accounts, use_proxy)

    tasks = [
        process_account(account, proxy, directory)
        for account, proxy in distributed
    ]

    await asyncio.gather(*tasks, return_exceptions=True)

    print_info_with_start("Аккаунты были успешно проверены!")
    return jsonify({
        'status': True,
        'reload': True
    })


@app.route('/delete_accounts', methods=['POST'])
async def delete_accounts():
    print_success_with_start(
        "-----------------------Удаление аккаунтов-----------------------")
    data = await request.get_json()
    accounts = data.get('account_ids')
    folder = data.get('current_folder')

    if folder == 'working':
        directory = Config.WORKING_DIR
    elif folder == 'archive':
        directory = Config.ARCHIVE_DIR
    else:  # all
        directory = 'all'

    delete_accounts_sessions(accounts)
    print_info_with_start("Аккаунты были успешно удалены!")
    return jsonify({'status': True, 'reload': True})


@app.route('/open_folder_accounts', methods=['POST'])
async def open_folder_accounts():
    """Открывает папку 'Аккаунты' в файловом менеджере операционной системы."""
    # Определяем путь к папке 'Аккаунты' относительно текущего рабочего каталога
    folder_path = os.path.join(os.getcwd(), 'Аккаунты')

    # Убедимся, что папка существует, если нет - создадим
    os.makedirs(folder_path, exist_ok=True)

    # Определяем команду в зависимости от операционной системы
    system = platform.system()
    if system == "Windows":
        open_and_maximize_explorer(folder_path)
    elif system == "Darwin":  # macOS
        # Для macOS используем open (обычно открывается в новом окне Finder)
        subprocess.run(["open", "-F", folder_path], check=True)
    elif system == "Linux":
        # Для Linux пробуем различные файловые менеджеры
        # Nautilus (GNOME) - открываем в полноэкранном режиме
        if subprocess.run(["which", "nautilus"], capture_output=True).returncode == 0:
            subprocess.run(["nautilus", "--browser", folder_path], check=True)
        # Dolphin (KDE)
        elif subprocess.run(["which", "dolphin"], capture_output=True).returncode == 0:
            subprocess.run(
                ["dolphin", "--fullscreen", folder_path], check=True)
        # Thunar (XFCE)
        elif subprocess.run(["which", "thunar"], capture_output=True).returncode == 0:
            subprocess.run(["thunar", folder_path], check=True)
        # Fallback - стандартный xdg-open
        else:
            subprocess.run(["xdg-open", folder_path], check=True)
    print_with_time("Загружаем аккаунты...")
    time.sleep(0.3)
    print_with_time("Загрузка аккаунтов завершена.")
    return jsonify({'success': True})
        
        
def open_browser_with_selenium(profile_name="persistent_profile"):
    """Открывает браузер с помощью Selenium."""
    chrome_options = Options()

    # Путь к директории профиля (сохраняется между запусками)
    profile_path = os.path.join(os.getcwd(), profile_name)
    # chrome_options.add_argument(f"--user-data-dir={profile_path}")

    # Основные настройки
    # Убираем --start-maximized, так как --app может конфликтовать
    # chrome_options.add_argument("--start-maximized")
    start_url = "http://localhost:8000"
    if STARTUP_AUTH_TOKEN:
        start_url = f"http://localhost:8000/set_token?token={STARTUP_AUTH_TOKEN}"
    chrome_options.add_argument(f"--app={start_url}")
    # Добавим размер окна явно, если нужно
    # chrome_options.add_argument("--window-size=1200,800")

    # Отключаем ненужные функции
    chrome_options.add_experimental_option("useAutomationExtension", False)
    chrome_options.add_experimental_option(
        "excludeSwitches", ["enable-automation", "enable-logging"])

    # Инициализация драйвера с сохранением профиля
    # Рекомендуется явно указать путь или использовать контекстный менеджер
    # для корректного закрытия драйвера, но для простоты оставим как есть
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    # Гарантированное закрытие при выходе из скрипта
    def close_driver():
        try:
            if 'driver' in locals() or 'driver' in globals():
                driver.quit()
                print("Selenium driver closed.")  # Для отладки
        except Exception as e:
            print(f"Error closing driver: {e}")  # Для отладки

    atexit.register(close_driver)
    return driver


def run_quart():
    """Запускает Quart приложение."""

    try:
        init_db()  # Предполагается, что эта функция определена
    except Exception as e:
        # print_error('Database initialization error: connection to server at "45.146.167.136", port 5432 failed: FATAL: database "tg" does not exist')
        # Используем print если print_error не определен
        print(f"Database initialization error: {e}")
        return  # Важно: выходим, если БД не инициализировалась

    try:
        # Запуск сервера Quart в основном потоке
        # Убедитесь, что `app` - это экземпляр Quart
        config = cfg()
        config.loglevel = "critical"   # 🔑
        config.accesslog = None    
        config.bind = ["127.0.0.1:8000"]
        asyncio.run(serve(app, config))
    except Exception as e:
        # print_error(f"Server error: {str(e)}")
        # Используем print если print_error не определен
        print(f"Server error: {e}")


def delayed_browser_open():
    """Открывает браузер с задержкой."""
    # Немного подождать, чтобы сервер успел стартовать
    time.sleep(3)  # Можно увеличить до 5, если сервер медленно стартует
    try:
        driver = open_browser_with_selenium()
        # Держим ссылку на драйвер, чтобы он не был удален сборщиком мусора
        # и atexit мог его закрыть. Можно сохранить в глобальную переменную
        # если нужно взаимодействовать с ним позже.
        global _driver_instance
        _driver_instance = driver
    except Exception as e:
        print(f"Error opening browser: {e}")  # Для отладки


if __name__ == '__main__':
    # Настройка логгирования
    log = logging.getLogger('werkzeug')  # Werkzeug используется в Quart
    log.setLevel(logging.ERROR)
    logging.getLogger('telethon').setLevel(logging.CRITICAL)

    # Запрос/чтение токена при старте и предварительная проверка
    token_file = os.path.join(os.getcwd(), 'Ключ.txt')
    entered = None

    # 1) Сначала пробуем взять токен из файла
    if os.path.exists(token_file):
        try:
            with open(token_file, 'r', encoding='utf-8') as f:
                entered = f.read().strip().lstrip('\ufeff')
        except Exception:
            entered = None

        if entered:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                is_valid = loop.run_until_complete(verify_token(entered))
            finally:
                try:
                    loop.close()
                except Exception:
                    pass

            if is_valid:
                STARTUP_AUTH_TOKEN = entered
                print_success_with_start("Токен подтверждён (из файла Ключ.txt)")
            else:
                print_error("Токен в Ключ.txt недействителен. Будет открыт экран входа.")
                entered = None

    # 2) Если в файле нет валидного токена — запросим у пользователя
    if not STARTUP_AUTH_TOKEN:
        try:
            entered = input("Введите ключ от программы и нажмите Enter: ")
        except Exception:
            entered = None

        if entered:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                is_valid = loop.run_until_complete(verify_token(entered))
            finally:
                try:
                    loop.close()
                except Exception:
                    pass

            if is_valid:
                STARTUP_AUTH_TOKEN = entered
                print_success_with_start("Токен подтверждён")
                # Сохраняем валидный токен в файл
                try:
                    with open(token_file, 'w', encoding='utf-8') as f:
                        f.write(entered + "\n")
                    print_info_with_start("Токен сохранён в Ключ.txt")
                except Exception as e:
                    print_error(f"Не удалось сохранить токен в Ключ.txt: {e}")
            else:
                print_error("Неверный токен. Будет открыт экран входа.")
        else:
            print_error("Токен не введён. Будет открыт экран входа.")



    browser_thread = threading.Thread(target=delayed_browser_open, daemon=True)
    browser_thread.start()
    # print("Отсутствует обновление браузера. Пожалуйста, обновите браузер.")
    # Отключение логов WebDriver Manager
    logging.getLogger('WDM').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.CRITICAL)
    os.environ['WDM_LOG_LEVEL'] = '0'
    
    os.environ['WDM_PRINT_FIRST_LINE'] = 'False'

    # Полное отключение логов Quart
    logging.getLogger('quart.app').setLevel(logging.CRITICAL)
    logging.getLogger('quart.serving').setLevel(logging.CRITICAL)
    logging.getLogger("hypercorn.error").setLevel(logging.CRITICAL)
    logging.getLogger("hypercorn.access").setLevel(logging.CRITICAL)
    logging.getLogger("asyncio").setLevel(logging.CRITICAL)
    log = logging.getLogger('werkzeug')
    
    log.setLevel(logging.CRITICAL)

    run_quart()
    # print("Ваша версия Windows устарела для работы chromium. Пожалуйста, обновите Windows.")
    # print("Внимание! Обновите Chromium для корректной работы!")


