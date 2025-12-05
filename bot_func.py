import asyncio
import datetime
import json
import os
import random
import re
from telethon import TelegramClient, errors, events
import threading
from telethon.tl import functions
from telethon.tl.types import InputPhoto, ReactionEmoji
from telethon.errors import FloodWaitError
from telethon.errors.rpcerrorlist import UserAlreadyParticipantError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.stories import ReadStoriesRequest, SendReactionRequest, GetPeerStoriesRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from config import Config
from database import get_ai_agent_by_id
from server import *


class Session:
    def __init__(self, session: str,  proxy: str = None, working_dir: str = None):
        self.proxy = proxy
        self.client = None
        self.me = None
        self.result = {}

        

        if working_dir == 'all':

            possible_paths = [
                os.path.join(Config.WORKING_DIR, session),
                os.path.join(Config.ARCHIVE_DIR, session),
                session 
            ]
            
            for path in possible_paths:
                if os.path.exists(path + '.session'):
                    self.session = path + '.session'
                    break
            else:
                raise FileNotFoundError(f"Session file not found for {session}")
        else:
          
            self.session = os.path.join(working_dir, session + '.session')
        
        self.phone = os.path.basename(self.session).replace('.session', '')
        self.params = self.GetParams()
        with open(self.session.replace(".session", ".json"), mode='r', encoding='utf-8') as f:
            self.session_data = json.load(f)
    
    def _get_value(self, file_json, *keys):
        for key in keys:
            if key in file_json:
                return file_json[key]
        return None

    
    def GetParams(self):
        if not os.path.exists(self.session.replace(".session", ".json")):
            return

        with open(self.session.replace(".session", ".json"), mode='r', encoding='utf-8') as f:
            try:
                json_data = json.loads(f.read())
            except (json.decoder.JSONDecodeError, UnicodeDecodeError):
                return

            return {
                'api_id': self._get_value(json_data, 'api_id', 'app_id', 'apiId', 'appId'),
                'api_hash': self._get_value(json_data, 'api_hash', 'app_hash', 'apiHash', 'appHash'),
                'device_model': self._get_value(json_data, 'deviceModel', 'device'),
                'system_version': self._get_value(json_data, 'systemVersion', 'system_version', 'appVersion', 'app_version'),
                'app_version': self._get_value(json_data, 'appVersion', 'app_version'),
                'lang_code': self._get_value(json_data, 'lang_pack', 'langPack', 'lang_code', 'langCode'),
                'system_lang_code': self._get_value(json_data, 'system_lang_pack', 'systemLangPack', 'system_lang_code', 'systemLangCode'),
                '2fa': self._get_value(json_data, 'twoFA', '2fa', '2FA', 'password'),
            }

    async def connect(self):
        try:
            self.client = TelegramClient(
                self.session,
                proxy=ProxyFromUrl(self.proxy) if self.proxy is not None else None,
                system_version="4.16.30-vxCUSTOM",
                api_id=self.params['api_id'],
                api_hash=self.params['api_hash'],
            )
            await self.client.connect()

            if not await self.client.is_user_authorized():
                print_error_with_start(f"Аккаунт {self.phone} забанен")

            self.me = await self.client.get_me()
            return True
        except Exception as e:
            print_error_with_start(f"Ошибка подключения к аккаунту {self.phone}: {e}")
            return False

    async def Check(self, spam_block: bool = False):
        """Проверка аккаунта (алиас для check_account для совместимости)"""
        result = await self.check_account(check_spam=spam_block)
        if isinstance(result, tuple):
            # Возвращаем True если успешно, иначе строку с ошибкой
            return result[0] if result[0] else result[1]
        return result

    async def check_account(self, check_spam: bool = False):

        session_data = self.session_data
        
        if not self.client or not self.client.is_connected():
            if not await self.connect():
                print_error(f"Ошибка подключения к аккаунту {self.phone}")
                return False, "Ошибка подключения"

        try:
     
            if not await self.client.is_user_authorized():
                print_error(f"Аккаунт {self.phone} забанен")
                session_data['status'] = 'dead'
                with open(self.session.replace(".session", ".json"), mode='w', encoding='utf-8') as f:
                    json.dump(session_data, f)
                return False, "Account not authorized"

      
            try:
                self.me = await self.client.get_me()
            except errors.FloodWaitError as e:
                return False, f"Flood wait: {e.seconds} seconds"
            except errors.AuthKeyError:
                
                print_error(f"Аккаунт {self.phone} забанен")
                session_data['status'] = 'dead'
                with open(self.session.replace(".session", ".json"), mode='w', encoding='utf-8') as f:
                    json.dump(session_data, f)
                return False, "Auth key error"


            if check_spam:
                spam_result = await self._check_spam_block()
                if spam_result is not None:
                    return False, spam_result


            try:
                await self.client(functions.account.UpdateStatusRequest(offline=False))
            except Exception:
                pass  
        

            
            
            session_data['status'] = 'alive'
            first_name = self.me.first_name if self.me.first_name else ""
            last_name = self.me.last_name if self.me.last_name else ""
            session_data['name'] = first_name + " " + last_name
            with open(self.session.replace(".session", ".json"), mode='w', encoding='utf-8') as f:
                json.dump(session_data, f)
            print_success_with_start(f"Аккаунт {self.phone} живой")
            return True, None

        except Exception as e:
            return False, f"Check error: {str(e)}"
    
    async def _check_spam_block(self):
        """Проверяет блокировку через SpamBot"""
        session_data = self.session_data
        try:
            await self.client(functions.contacts.UnblockRequest(id='SpamBot'))
            async with self.client.conversation('SpamBot') as conv:
                await conv.send_message('/start')
                msg = await conv.get_response()

                spam_phrases = [
                    'UTC', 'limited', 'antispam',
                    'abnormal', 'Ваш аккаунт ограничен',
                    'phone numbers'
                ]

                if any(phrase in msg.text for phrase in spam_phrases):
                    self.spamblock = True
                    session_data['status'] = 'spam_block'
                    with open(self.session.replace(".session", ".json"), mode='w', encoding='utf-8') as f:
                        json.dump(session_data, f)
                    print_warning(f"Аккаунт {self.phone} в спам блоке")
                    return "Account limited by spam protection"

        except errors.FloodWaitError as e:
            return f"Flood wait from SpamBot: {e.seconds} sec"
        except Exception:
            return "Failed to check spam status"

        return None
    
    
    async def change_first_name(self, first_name: str):
        session_data = self.session_data
        if not self.client or not self.client.is_connected():
            if not await self.connect():
                return False, "Failed to connect"

        try:
            await self.client(functions.account.UpdateProfileRequest(
                first_name=first_name,
                last_name=self.me.last_name if self.me.last_name else ""
            ))
            last_name = self.me.last_name if self.me.last_name else ""
            print_success_with_start(f"Аккаунт {self.phone} измененил имя с {self.me.first_name} на {first_name}")
            session_data['name'] = first_name + " " + last_name
            with open(self.session.replace(".session", ".json"), mode='w', encoding='utf-8') as f:
                json.dump(session_data, f)
            return True
        except errors.FloodWaitError as e:
            return False, f"Flood wait: {e.seconds} seconds"
        except Exception as e:
            return False, str(e)

    async def change_last_name(self, last_name: str):
        session_data = self.session_data
        if not self.client or not self.client.is_connected():
            if not await self.connect():
                return False, "Failed to connect"

        try:
            await self.client(functions.account.UpdateProfileRequest(
                first_name=self.me.first_name if self.me.first_name else "",
                last_name=last_name
            ))
            first_name = self.me.first_name if self.me.first_name else ""
            session_data['name'] = first_name + " " + last_name
            print_success_with_start(f"Аккаунт {self.phone} измененил фамилию с {self.me.last_name} на {last_name}")
            with open(self.session.replace(".session", ".json"), mode='w', encoding='utf-8') as f:
                json.dump(session_data, f)
            return True
            
        except errors.FloodWaitError as e:
            return False, f"Flood wait: {e.seconds} seconds"
        except Exception as e:
            return False, str(e)
        
    async def change_profile_photo(self, photo_path: str):
        """
        Изменяет аватарку профиля
        
        :param photo_path: Путь к изображению
        :return: Tuple[bool, str] - (Успех, Сообщение об ошибке/статусе)
        """
        if not self.client or not self.client.is_connected():
            status = await self.Check()
            if status is not True and "ограничен" not in str(status):
                return False, status

        try:
           
            photos = await self.client.get_profile_photos("me")
            input_photos = [InputPhoto(
                id=photo.id,
                access_hash=photo.access_hash,
                file_reference=photo.file_reference
            ) for photo in photos]

            await self.client(functions.photos.DeletePhotosRequest(input_photos))

          
            file = await self.client.upload_file(photo_path)
            await self.client(functions.photos.UploadProfilePhotoRequest(file=file))

            print_success_with_start(f"Аватар профиля успешно изменен для аккаунта {self.me.phone}")
            return True, "Фото профиля успешно изменено"

        except errors.FloodWaitError as e:
            return False, f"Flood wait: {e.seconds} seconds"
        except Exception as e:
            self.logger.error(f"Ошибка при изменении аватарки: {str(e)}")
            return False, str(e)

    async def GetConfirmationCode(self):
        """
        Получает код подтверждения из сообщения от Telegram (777000)
        Возвращает:
            - (True, {'code': код, '2fa': пароль}) при успехе
            - (None, error_message) при ошибке
        """
        try:
            async for message in self.client.iter_messages(777000, limit=1):
                match = re.search(r'(\d+)', message.message)
                if match:
                    return True, {
                        'code': match.group(1),
                        '2fa': self.params.get('2fa', '-') if self.params else "-"
                    }
            return None, "Сообщение с кодом не найдено"

        except errors.rpcerrorlist.FloodWaitError as e:
            return None, f"Флуд-задержка превысила {e.seconds} сек."
        except errors.rpcerrorlist.AuthKeyDuplicatedError:
            return None, "Авторизован с другого IP-адреса"
        except (errors.rpcerrorlist.PhoneNumberInvalidError,
                errors.rpcerrorlist.PhoneNumberBannedError,
                errors.rpcerrorlist.PhonePasswordFloodError,
                errors.rpcerrorlist.PhoneCodeInvalidError) as e:
            return None, str(e)
        except ConnectionError:
            return None, "Подключение было прервано"
        except Exception as e:
            return None, str(e)

    async def start_pm_mailing(self, threads, min_delay, max_delay, messages_per_account,
                            recipients, message_text, attachment, auto_reply_enabled,
                            manager_chat, reply_message, attachment_type='file',
                            delete_after_send=False):
        start_time = datetime.datetime.now()
        success_count = 0
        error_count = 0
        flood_waits = 0
        total_recipients = len(recipients)

        # --- Логика для репоста ---
        repost_info = None
        if message_text:
            # Ищем подстроку "repost <url>" в тексте сообщения (без учета регистра)
            repost_match = re.search(r'repost\s+https?://t\.me/([^/]+)/(\d+)', message_text, re.IGNORECASE)
            if repost_match:
                channel_username_or_id = repost_match.group(1)
                try:
                    message_id = int(repost_match.group(2))
                    repost_info = {
                        'channel': channel_username_or_id,
                        'message_id': message_id
                    }
                    # Опционально: удалить "repost <url>" из основного текста сообщения
                    # message_text = re.sub(r'repost\s+https?://t\.me/[^/]+/\d+', '', message_text, flags=re.IGNORECASE).strip()
                    print_info(f"Найдена ссылка для репоста: канал={channel_username_or_id}, сообщение={message_id}")
                except ValueError:
                    print_warning("ID сообщения в ссылке репоста не является числом.")

        # --- Конец логики для репоста ---

        print(
            f"📬 Аккаунт {self.phone} начал рассылку для {total_recipients} получателей")

        try:
            for i, user in enumerate(recipients):
                try:
                    sent_message = None

                    # --- Отправка сообщения ---
                    if repost_info:
                        # --- Логика репоста ---
                        try:
                            # Пересылаем сообщение
                            # from_peer может быть именем пользователя, ID или объектом InputPeer
                            # messages - список ID сообщений
                            forwarded_msgs = await self.client.forward_messages(
                                entity=user,
                                from_peer=repost_info['channel'],
                                messages=[repost_info['message_id']]
                            )
                            # forward_messages возвращает список пересланных сообщений
                            if forwarded_msgs:
                                sent_message = forwarded_msgs[0]
                            print_success(f"🔁 Отправлен репост пользователю: {user}")
                            success_count += 1
                        except Exception as e:
                            error_count += 1
                            print_error(f"❌ Ошибка репоста для {user}: {str(e)}")
                        # --- Конец логики репоста ---

                    else:
                        # Отправляем сообщение в зависимости от типа вложения (как было)
                        if attachment:
                            if attachment_type == 'voice':
                                sent_message = await self.client.send_file(
                                    user,
                                    file=attachment,
                                    caption=message_text if message_text else None,
                                    parse_mode='html',
                                    video_note=True
                                )
                                print_success(f"🎤 Отправлен кружочек: {user}")
                            elif attachment_type == 'audio':
                                sent_message = await self.client.send_file(
                                    user,
                                    file=attachment,
                                    caption=message_text if message_text else None,
                                    parse_mode='html',
                                    voice_note=True
                                )
                                print_success(
                                    f"🎵 Отправлено голосовое сообщение: {user}")
                            else:
                                sent_message = await self.client.send_file(
                                    user,
                                    file=attachment,
                                    caption=message_text,
                                    parse_mode='html'
                                )
                                print_success(f"✅ Отправлено с вложением: {user}")
                        else:
                            # Отправляем только текст
                            sent_message = await self.client.send_message(
                                user,
                                message_text,
                                parse_mode='html'
                            )
                            print_success(f"✉️ Отправлено сообщение: {user}")
                        success_count += 1

                        # --- Удаление сообщения ---
                        # (Логика удаления применяется только к сообщениям, отправленным send_message/send_file)
                        # forward_messages не создает сообщение у отправителя, которое можно удалить таким образом.
                        # Если нужно удалить пересланное сообщение у получателя, это сложнее и требует других методов.
                        if delete_after_send and sent_message and not repost_info:
                            try:
                                await self.client.delete_messages(
                                    entity=self.me.id, # Или user, если нужно удалить у получателя (но это не всегда возможно)
                                    message_ids=[sent_message.id],
                                    revoke=False # True чтобы удалить у всех (если возможно)
                                )
                                print_info(
                                    f"🗑️ Сообщение удалено у отправителя: {user}")
                            except Exception as delete_error:
                                print_warning(
                                    f"⚠️ Не удалось удалить сообщение для {user}: {str(delete_error)}")
                        # --- Конец удаления ---

                    # --- Промежуточная статистика ---
                    if (i+1) % 10 == 0 or (i+1) == total_recipients:
                        elapsed = datetime.datetime.now() - start_time
                        elapsed_sec = elapsed.total_seconds()
                        mins, secs = divmod(int(elapsed_sec), 60)
                        elapsed_str = f"{mins}:{secs:02d}"

                        remaining = total_recipients - (i+1)
                        avg_time = elapsed_sec / (i+1) if i > 0 else 0
                        est_remaining = datetime.timedelta(
                            seconds=round(avg_time * remaining))

                        print(
                            f"\n📊 АККАУНТ {self.phone} - ПРОМЕЖУТОЧНАЯ СТАТИСТИКА:")
                        print(f"   👤 Обработано: {i+1}/{total_recipients}")
                        print(f"   ✅ Успешно: {success_count}")
                        print(f"   ⚠️ Ошибок: {error_count}")
                        print(f"   ⏱️ Время: {elapsed_str}")
                        if remaining > 0:
                            print(
                                f"   🕐 Осталось: ~{str(est_remaining).split('.')[0]}")
                        print(
                            f"   📈 Скорость: {success_count/(elapsed_sec/60):.1f} сообщ/мин")
                    # --- Конец статистики ---

                    # Задержка между отправками
                    await asyncio.sleep(random.randint(min_delay, max_delay))

                except errors.FloodWaitError as e:
                    flood_waits += 1
                    print_warning(f"⏳ Флуд-контроль! Ожидаем {e.seconds} сек.")
                    await asyncio.sleep(e.seconds)
                except Exception as e: # Для других ошибок, не связанных с репостом
                    if not repost_info: # Ошибка уже обработана в блоке репоста
                        error_count += 1
                        print_error(f"❌ Ошибка для {user}: {str(e)}")

            # --- Итоговая статистика ---
            elapsed = datetime.datetime.now() - start_time
            elapsed_sec = elapsed.total_seconds()
            mins, secs = divmod(int(elapsed_sec), 60)
            hours, mins = divmod(mins, 60)
            elapsed_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"

            print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА АККАУНТА {self.phone}:")
            print(f"✉️ Обработано получателей: {success_count + error_count}/{total_recipients}")
            print(f"✅ Успешно отправлено/переслано: {success_count}")
            print(f"⚠️ Ошибок: {error_count}")
            print(f"🚫 Flood Wait: {flood_waits} раз")
            print(f"⏱️ Время работы: {elapsed_str}")
            if elapsed_sec > 0:
                print(f"📈 Скорость: {success_count/(elapsed_sec/60):.1f} сообщ/мин")
            # --- Конец статистики ---

            return success_count

        except Exception as e:
            print_error(f"🛑 Критическая ошибка: {str(e)}")
            return 0


    async def start_chat_mailing(self, threads, min_delay, max_delay, messages_per_account, recipients, message_text, attachment, auto_reply_enabled, manager_chat, reply_message, cycle, delay_cycle):
        start_time = datetime.datetime.now()
        cycle_count = 0
        total_sent = 0
        error_count = 0
        flood_waits = 0
        is_cycle = cycle.lower() == "true"
        total_recipients = len(recipients)

        print(
            f"📢 Аккаунт {self.phone} начал чат-рассылку для {total_recipients} чатов")

        while True:
            try:
                cycle_count += 1
                cycle_sent = 0
                cycle_errors = 0

                for i, user in enumerate(recipients):
                    try:
                        await self.client(functions.channels.JoinChannelRequest(user))

                        if attachment:
                            await self.client.send_file(user, file=attachment, caption=message_text, parse_mode='html')
                            print_success(f"📎 Отправлено в {user}")
                        else:
                            await self.client.send_message(user, message_text, parse_mode='html')
                            print_success(f"💬 Отправлено в {user}")

                        total_sent += 1
                        cycle_sent += 1

                        # Промежуточная статистика
                        if (total_sent) % 10 == 0 or (i+1) == total_recipients:
                            elapsed = datetime.datetime.now() - start_time
                            elapsed_sec = elapsed.total_seconds()
                            mins, secs = divmod(int(elapsed_sec), 60)
                            elapsed_str = f"{mins}:{secs:02d}"

                            print(
                                f"\n📊 АККАУНТ {self.phone} - ПРОМЕЖУТОЧНАЯ СТАТИСТИКА:")
                            print(f"   🔄 Цикл: {cycle_count}")
                            print(f"   💬 Отправлено: {total_sent} сообщений")
                            print(f"   ⚠️ Ошибок: {error_count}")
                            print(f"   ⏱️ Время: {elapsed_str}")
                            print(
                                f"   📈 Скорость: {total_sent/(elapsed_sec/60):.1f} сообщ/мин")

                        await asyncio.sleep(random.randint(min_delay, max_delay))

                    except errors.FloodWaitError as e:
                        flood_waits += 1
                        print_warning(f"⏳ Флуд-контроль! Ожидаем {e.seconds} сек.")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        error_count += 1
                        cycle_errors += 1
                        print_error(f"❌ Ошибка для {user}: {str(e)}")

                # Статистика цикла
                print(f"\n🔄 АККАУНТ {self.phone} ЗАВЕРШИЛ ЦИКЛ {cycle_count}:")
                print(f"   💬 Отправлено: {cycle_sent}/{total_recipients}")
                print(f"   ⚠️ Ошибок: {cycle_errors}")

                if not is_cycle:
                    break

                dl = list(map(int, delay_cycle.split("-")))
                delay = random.randint(dl[0], dl[1])
                print(f"⏳ Ожидание следующего цикла: {delay} сек.")
                await asyncio.sleep(delay)

            except Exception as e:
                error_count += 1
                print_error(f"🛑 Ошибка цикла: {str(e)}")

        # Финальная статистика
        elapsed = datetime.datetime.now() - start_time
        elapsed_sec = elapsed.total_seconds()
        mins, secs = divmod(int(elapsed_sec), 60)
        hours, mins = divmod(mins, 60)
        elapsed_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"

        print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА АККАУНТА {self.phone}:")
        print(f"💬 Всего отправлено: {total_sent}")
        print(f"🔄 Циклов выполнено: {cycle_count}")
        print(f"⚠️ Ошибок: {error_count}")
        print(f"🚫 Flood Wait: {flood_waits} раз")
        print(f"⏱️ Общее время: {elapsed_str}")
        print(f"📈 Скорость: {total_sent/(elapsed_sec/60):.1f} сообщ/мин")
        
    async def PrepareAnswerMachine(self, text, url_answer_machine, wait):
        url = url_answer_machine
        try:
            if "joinchat" in url or "+" in url:
                channel_id = url.split('/')[-1].replace('+', '')

                await self.client(functions.messages.ImportChatInviteRequest(channel_id))
                channel = await self.client.get_entity(url)
                chat_id = channel.id
            else:
                channel = await self.client.get_entity(url)
                await self.client(functions.channels.JoinChannelRequest(channel))
                chat_id = channel.id
            print_success_with_start(f'Клиент {self.me.phone} присоединился к {url}')
        except UserAlreadyParticipantError:
            channel = await self.client.get_entity(url)
            chat_id = channel.id
        except Exception as e:
            self.logger.error(
                f'Клиент {self.me.phone} не смог присоединиться к {url}: {e}')
        self.client.add_event_handler(lambda event: prepare_answer(
            event, text, url_answer_machine, wait), events.NewMessage(func=lambda e: e.is_private))
    

    async def WireTapping(self, groups, trigerwords, settings):
        if not self.client or not self.client.is_connected():
            status = await self.Check()
            if status is not True and "ограничен" not in str(status):
                return None, status

        start_time = datetime.datetime.now()
        groups_joined = 0
        groups_failed = 0
        flood_waits = 0
        handlers_added = 0
        total_groups = len(groups)
        
        print(f"👂 Аккаунт {self.phone} начал прослушку в {total_groups} группах")

        async def join_with_retry(channel, group_name):
            nonlocal flood_waits, groups_joined, groups_failed
            attempt = 1
            while attempt <= 3:  # Максимум 3 попытки
                try:
                    await self.client(JoinChannelRequest(channel))
                    groups_joined += 1
                    print_success(f"✅ Вошли в группу: {group_name}")
                    await asyncio.sleep(random.randint(10, 15))
                    return True
                except FloodWaitError as e:
                    flood_waits += 1
                    print_warning(f"⏳ Флуд-контроль! Ожидаем {e.seconds} сек.")
                    await asyncio.sleep(e.seconds)
                    attempt += 1
                except Exception as e:
                    groups_failed += 1
                    print_error(f"❌ Ошибка входа в '{group_name}': {str(e)}")
                    return False
            
            groups_failed += 1
            print_error(f"🛑 Не удалось войти в '{group_name}' после 3 попыток")
            return False

        # Статистика перед началом настройки
        print(f"\n⚙️ АККАУНТ {self.phone} - НАСТРОЙКА ПРОСЛУШКИ:")
        print(f"   🔍 Триггер-слова: {len(trigerwords)}")
        print(f"   📌 Действия:")
        for action, config in settings.items():
            if config['enabled']:
                print(f"      • {action.replace('_', ' ').title()}: {'включено'}")
        
        # Обработка групп
        for group in groups:
            group = group.replace('\r', '').replace('\n', '')
            try:
                channel = await self.client.get_input_entity(group)
                joined = await join_with_retry(channel, group)
                
                if not joined:
                    continue
                    
                group_id = channel.channel_id if hasattr(channel, 'channel_id') else channel.id
                
                # Обработка различных действий
                if settings["reply_in_chat"]["enabled"]:
                    self.client.add_event_handler(
                        lambda event: wiretapping_reply_in_chat(event, settings["reply_in_chat"], trigerwords), 
                        events.NewMessage(chats=[group_id])
                    )
                    handlers_added += 1
                    
                if settings["forward_to_storage"]["enabled"]:
                    url = settings["forward_to_storage"]["chat_link"]
                    try:
                        if "joinchat" in url or "+" in url:
                            channel_id = url.split('/')[-1].replace('+', '')
                            await self.client(functions.messages.ImportChatInviteRequest(channel_id))
                        else:
                            await self.client(functions.channels.JoinChannelRequest(url))
                        print_success(f"✅ Вошли в storage-чат: {url}")
                    except (UserAlreadyParticipantError, FloodWaitError) as e:
                        if isinstance(e, FloodWaitError):
                            flood_waits += 1
                            await asyncio.sleep(e.seconds)
                    except Exception as e:
                        print_error(f"❌ Ошибка входа в storage-чат: {str(e)}")
                    
                    self.client.add_event_handler(
                        lambda event: wiretapping_forward_to_storage(event, settings["forward_to_storage"], trigerwords, group), 
                        events.NewMessage(chats=[group_id])
                    )
                    handlers_added += 1
                    
                if settings["like_triggers"]["enabled"]:
                    self.client.add_event_handler(
                        lambda event: wiretapping_like_triggers(event, settings["like_triggers"], trigerwords), 
                        events.NewMessage(chats=[group_id])
                    )
                    handlers_added += 1
                    
                if settings["add_to_group"]["enabled"]:
                    self.client.add_event_handler(
                        lambda event: wiretapping_add_to_group(event, settings["add_to_group"], trigerwords), 
                        events.NewMessage(chats=[group_id])
                    )
                    handlers_added += 1
                    
                if settings["initiate_pm"]["enabled"]:
                    self.client.add_event_handler(
                        lambda event: wiretapping_initiate_pm(event, settings["initiate_pm"], trigerwords), 
                        events.NewMessage(chats=[group_id])
                    )
                    handlers_added += 1
                    
                if settings['ai_conversation']['enabled']:
                    ai_agent = get_ai_agent_by_id(settings['ai_conversation']['ai_agent_id'])
                    self.client.add_event_handler(
                        lambda event: wiretapping_ai_conversation(event, ai_agent, trigerwords), 
                        events.NewMessage(chats=[group_id])
                    )
                    handlers_added += 1
                    
            except Exception as e:
                groups_failed += 1
                print_error(f"❌ Ошибка обработки группы {group}: {str(e)}")
        
        # Статистика настройки
        elapsed = datetime.datetime.now() - start_time
        elapsed_sec = elapsed.total_seconds()
        mins, secs = divmod(int(elapsed_sec), 60)
        elapsed_str = f"{mins}:{secs:02d}"
        
        print(f"\n📊 АККАУНТ {self.phone} - СТАТИСТИКА НАСТРОЙКИ:")
        print(f"   👥 Группы: {groups_joined}/{total_groups} успешно")
        print(f"   ⚠️ Ошибок: {groups_failed}")
        print(f"   🔗 Обработчиков: {handlers_added}")
        print(f"   ⏱️ Время: {elapsed_str}")
        print(f"   🚫 Flood Wait: {flood_waits} раз")
        
        print(f"\n👂 Аккаунт {self.phone} начал прослушку. Ожидание триггеров...")
        
        # Основной цикл прослушки
        trigger_count = 0
        last_report_time = datetime.datetime.now()
        
        while True:
            try:
                await asyncio.sleep(60)  # Проверка каждую минуту
                
                # Периодическая статистика (каждые 5 минут)
                current_time = datetime.datetime.now()
                if (current_time - last_report_time).total_seconds() >= 300:
                    elapsed_total = current_time - start_time
                    elapsed_sec = elapsed_total.total_seconds()
                    hours, remainder = divmod(int(elapsed_sec), 3600)
                    mins, secs = divmod(remainder, 60)
                    elapsed_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"
                    
                    print(f"\n📊 АККАУНТ {self.phone} - СТАТУС ПРОСЛУШКИ:")
                    print(f"   ⏱️ Время работы: {elapsed_str}")
                    print(f"   🔔 Триггеров: {trigger_count}")
                    print(f"   👥 Групп в работе: {groups_joined}")
                    
                    last_report_time = current_time
                    
            except Exception as e:
                print_error(f"❌ Ошибка в основном цикле: {str(e)}")
                break

    async def MassLookingChats(self, reactions, chats, looking=[3, 5], reaction_flood=[3, 5], wait=[3, 5]):
        if not self.client or not self.client.is_connected():
            status = await self.Check()
            if status is not True and "ограничен" not in str(status):
                return None, status

        start_time = datetime.datetime.now()
        total_chats = len(chats)
        
        # Создаем словарь для статистики вместо nonlocal
        stats = {
            'viewed_stories': 0,
            'reactions_sent': 0,
            'errors': 0,
            'flood_waits': 0,
            'users_processed': 0,
            'processed_chats': 0
        }
        
        print(f"👀 Аккаунт {self.phone} начал массовый просмотр в {total_chats} чатах")

        async def masslook_chat(chat, looking, reaction_flood, reactions, stats):
            # Статистика для текущего чата
            chat_stats = {
                'viewed': 0,
                'reactions': 0,
                'errors': 0,
                'flood_waits': 0,
                'users': 0
            }
            
            try:
                full = await self.client(functions.channels.GetFullChannelRequest(chat))
            except (errors.rpcerrorlist.ChannelPrivateError,
                    errors.rpcerrorlist.TimeoutError,
                    errors.rpcerrorlist.ChannelPublicGroupNaError):
                print_error(f"❌ [{self.phone}] Нет доступа к чату: {chat}")
                chat_stats['errors'] += 1
                stats['errors'] += 1
                return chat_stats
            except ValueError:
                print_error(f"❌ [{self.phone}] Чат не существует: {chat}")
                chat_stats['errors'] += 1
                stats['errors'] += 1
                return chat_stats
            except errors.rpcerrorlist.FloodWaitError as e:
                stats['flood_waits'] += 1
                chat_stats['flood_waits'] += 1
                print_warning(f"⏳ [{self.phone}] Флуд-контроль! Ожидаем {e.seconds} сек.")
                await asyncio.sleep(e.seconds + 5)
                try:
                    full = await self.client(functions.channels.GetFullChannelRequest(chat))
                except Exception as e:
                    print_error(f"❌ [{self.phone}] Ошибка после ожидания: {str(e)}")
                    chat_stats['errors'] += 1
                    stats['errors'] += 1
                    return chat_stats

            full_channel = full.full_chat
            chat_id = full_channel.id
            messages_count = (await self.client.get_messages(chat_id)).total
            message_current = 0
            
            print_success(f"🔍 [{self.phone}] Начат просмотр чата {chat} ({messages_count} сообщений)")
            
            try:
                async for msg in self.client.iter_messages(chat_id, limit=messages_count):
                    try:
                        sender = await msg.get_sender()
                        message_current += 1
                        
                        if message_current % 100 == 0:
                            print(f"   📨 [{self.phone}] Обработано сообщений: {message_current}/{messages_count}")
                        
                        if not (sender and sender.__class__.__name__ == "User" and not sender.bot):
                            continue
                        if not (not sender.stories_unavailable and not sender.stories_hidden and 
                                sender.stories_max_id and sender.username):
                            continue
                        
                        identifier = sender.username
                        stats['users_processed'] += 1
                        chat_stats['users'] += 1
                        
                        try:
                            stories = await self.client(GetPeerStoriesRequest(identifier))
                        except FloodWaitError as e:
                            stats['flood_waits'] += 1
                            chat_stats['flood_waits'] += 1
                            print_warning(f"⏳ [{self.phone}] Флуд-контроль! Ожидаем {e.seconds} сек.")
                            await asyncio.sleep(e.seconds)
                            stories = await self.client(GetPeerStoriesRequest(identifier))
                        
                        if not stories.stories.stories:
                            await asyncio.sleep(random.randint(*looking))
                            continue
                        
                        user = stories.users[0]
                        stories_to_view = stories.stories.stories[0]
                        
                        # Просмотр истории
                        try:
                            await self.client(ReadStoriesRequest(user, max_id=stories_to_view.id))
                            stats['viewed_stories'] += 1
                            chat_stats['viewed'] += 1
                            await asyncio.sleep(random.randint(*looking))
                        except FloodWaitError as e:
                            stats['flood_waits'] += 1
                            chat_stats['flood_waits'] += 1
                            print_warning(f"⏳ [{self.phone}] Флуд-контроль! Ожидаем {e.seconds} сек.")
                            await asyncio.sleep(e.seconds)
                        
                        # Реакция (случайным образом)
                        if random.randint(0, 2) == 0:
                            try:
                                await self.client(SendReactionRequest(
                                    user,
                                    stories_to_view.id,
                                    reaction=ReactionEmoji(emoticon=random.choice(reactions))
                                ))
                                stats['reactions_sent'] += 1
                                chat_stats['reactions'] += 1
                                await asyncio.sleep(random.randint(*reaction_flood))
                            except FloodWaitError as e:
                                stats['flood_waits'] += 1
                                chat_stats['flood_waits'] += 1
                                print_warning(f"⏳ [{self.phone}] Флуд-контроль! Ожидаем {e.seconds} сек.")
                                await asyncio.sleep(e.seconds)
                    
                    except Exception as e:
                        stats['errors'] += 1
                        chat_stats['errors'] += 1
                        print_error(f"❌ [{self.phone}] Ошибка обработки сообщения: {str(e)}")
            
            except FloodWaitError as e:
                stats['flood_waits'] += 1
                chat_stats['flood_waits'] += 1
                print_warning(f"⏳ [{self.phone}] Флуд-контроль! Ожидаем {e.seconds} сек.")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                stats['errors'] += 1
                chat_stats['errors'] += 1
                print_error(f"❌ [{self.phone}] Критическая ошибка в чате {chat}: {str(e)}")
            
            print_success(f"✅ [{self.phone}] Завершен просмотр чата {chat}")
            return chat_stats

        # Обработка чатов
        all_results = []
        batch_size = 1
        
        for chat in chats:
            chat_start = datetime.datetime.now()
            
            result = await masslook_chat(chat, looking, reaction_flood, reactions, stats)
            all_results.append(result)
            stats['processed_chats'] += 1
            
            # Статистика после обработки чата
            chat_elapsed = datetime.datetime.now() - chat_start
            chat_sec = chat_elapsed.total_seconds()
            mins, secs = divmod(int(chat_sec), 60)
            chat_time = f"{mins}:{secs:02d}"
            
            print(f"\n📊 [{self.phone}] ОТЧЕТ ПО ЧАТУ {chat}:")
            print(f"   👤 Пользователей: {result.get('users', 0)}")
            print(f"   👀 Просмотров историй: {result.get('viewed', 0)}")
            print(f"   ❤️ Реакций: {result.get('reactions', 0)}")
            print(f"   ⏱️ Время: {chat_time}")
            print(f"   ⚠️ Ошибок: {result.get('errors', 0)}")
            print(f"   🚫 Flood Wait: {result.get('flood_waits', 0)}")
            
            # Общая промежуточная статистика
            elapsed = datetime.datetime.now() - start_time
            elapsed_sec = elapsed.total_seconds()
            mins, secs = divmod(int(elapsed_sec), 60)
            elapsed_str = f"{mins}:{secs:02d}"
            
            remaining = total_chats - stats['processed_chats']
            avg_time = elapsed_sec / stats['processed_chats'] if stats['processed_chats'] > 0 else 0
            est_remaining = datetime.timedelta(seconds=round(avg_time * remaining))
            
            print(f"\n📊 [{self.phone}] ОБЩАЯ СТАТИСТИКА:")
            print(f"   💬 Чаты: {stats['processed_chats']}/{total_chats}")
            print(f"   👤 Пользователей: {stats['users_processed']}")
            print(f"   👀 Просмотров историй: {stats['viewed_stories']}")
            print(f"   ❤️ Реакций: {stats['reactions_sent']}")
            print(f"   ⏱️ Время: {elapsed_str}")
            print(f"   ⚠️ Ошибок: {stats['errors']}")
            print(f"   🚫 Flood Wait: {stats['flood_waits']}")
            if remaining > 0:
                print(f"   🕐 Осталось: ~{str(est_remaining).split('.')[0]}")
            
            await asyncio.sleep(random.randint(*wait))
        
        # Итоговая статистика
        elapsed = datetime.datetime.now() - start_time
        elapsed_sec = elapsed.total_seconds()
        hours, remainder = divmod(int(elapsed_sec), 3600)
        mins, secs = divmod(remainder, 60)
        elapsed_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"
        
        success_chats = sum(1 for r in all_results if r.get('viewed', 0) > 0)
        
        print(f"\n📊 [{self.phone}] ИТОГОВАЯ СТАТИСТИКА:")
        print(f"💬 Обработано чатов: {stats['processed_chats']}/{total_chats}")
        print(f"✅ Успешных чатов: {success_chats} ({success_chats/stats['processed_chats']*100:.1f}%)")
        print(f"👤 Всего пользователей: {stats['users_processed']}")
        print(f"👀 Просмотрено историй: {stats['viewed_stories']}")
        print(f"❤️ Отправлено реакций: {stats['reactions_sent']}")
        print(f"⏱️ Время работы: {elapsed_str}")
        print(f"⚠️ Ошибок: {stats['errors']}")
        print(f"🚫 Flood Wait: {stats['flood_waits']} раз")
        
        return all_results
        
    async def MassLooking(self, reactions, looking, reaction_flood, stories_account, stories_user, identifiers):
        start_time = datetime.datetime.now()
        total_users = len(identifiers)
        processed_users = 0
        viewed_stories = 0
        reactions_sent = 0
        errors = 0
        flood_waits = 0

        looking_range = list(map(int, looking.split('-')))
        reaction_flood_range = list(map(int, reaction_flood.split('-')))

        print(
            f"👀 Аккаунт {self.phone} начал массовый просмотр для {total_users} пользователей")

        for idx, identifier in enumerate(identifiers, 1):
            try:
                processed_users = idx

                # Проверка лимита историй
                if stories_account > 0 and viewed_stories >= stories_account:
                    print(
                        f"⚠️ Достигнут лимит историй: {viewed_stories}/{stories_account}")
                    break

                stories = await self.client(GetPeerStoriesRequest(identifier))
                if not stories.stories.stories:
                    continue

                user = stories.users[0]
                stories_to_view = stories.stories.stories[:
                                                        stories_user if stories_user > 0 else None]

                # Просмотр историй
                for story in stories_to_view:
                    try:
                        await self.client(ReadStoriesRequest(user, max_id=story.id))
                        viewed_stories += 1
                        await asyncio.sleep(random.randint(*looking_range))
                    except errors.FloodWaitError as e:
                        flood_waits += 1
                        print_warning(f"⏳ Флуд-контроль! Ожидаем {e.seconds} сек.")
                        await asyncio.sleep(e.seconds)

                # Реакции
                for story in stories_to_view:
                    try:
                        await self.client(SendReactionRequest(
                            user,
                            story.id,
                            reaction=ReactionEmoji(
                                emoticon=random.choice(reactions))
                        ))
                        reactions_sent += 1
                        await asyncio.sleep(random.randint(*reaction_flood_range))
                    except errors.FloodWaitError as e:
                        flood_waits += 1
                        print_warning(f"⏳ Флуд-контроль! Ожидаем {e.seconds} сек.")
                        await asyncio.sleep(e.seconds)

                # Промежуточная статистика
                if idx % 10 == 0 or idx == total_users:
                    elapsed = datetime.datetime.now() - start_time
                    elapsed_sec = elapsed.total_seconds()
                    mins, secs = divmod(int(elapsed_sec), 60)
                    elapsed_str = f"{mins}:{secs:02d}"

                    remaining_users = total_users - idx
                    avg_time_per_user = elapsed_sec / idx if idx > 0 else 0
                    est_remaining = datetime.timedelta(
                        seconds=round(avg_time_per_user * remaining_users))

                    speed = viewed_stories / \
                        (elapsed_sec/60) if elapsed_sec > 0 else 0

                    print(f"\n📊 АККАУНТ {self.phone} - ПРОМЕЖУТОЧНАЯ СТАТИСТИКА:")
                    print(f"   👤 Обработано: {idx}/{total_users}")
                    print(f"   👀 Stories: {viewed_stories}")
                    print(f"   ❤️ Реакций: {reactions_sent}")
                    print(f"   ⏱️ Время: {elapsed_str}")
                    if remaining_users > 0:
                        print(
                            f"   🕐 Осталось: ~{str(est_remaining).split('.')[0]}")
                    print(f"   📈 Скорость: {speed:.1f} stories/мин")

            except Exception as e:
                errors += 1
                print_error(f"❌ Ошибка для {identifier}: {str(e)}")

        # Итоговая статистика
        elapsed = datetime.datetime.now() - start_time
        elapsed_sec = elapsed.total_seconds()
        mins, secs = divmod(int(elapsed_sec), 60)
        hours, mins = divmod(mins, 60)
        elapsed_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"

        speed = viewed_stories / (elapsed_sec/60) if elapsed_sec > 0 else 0

        print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА АККАУНТА {self.phone}:")
        print(f"👥 Обработано пользователей: {processed_users}/{total_users}")
        print(f"👀 Просмотрено Stories: {viewed_stories}")
        print(f"❤️ Отправлено реакций: {reactions_sent}")
        print(f"⏱️ Время работы: {elapsed_str}")
        print(f"⚠️ Ошибок: {errors}")
        print(f"🚫 Flood Wait: {flood_waits} раз")
        print(f"📈 Скорость: {speed:.1f} stories/мин")
        return True


    
    async def Inviting(self, users, chat_id, wait, count=0, remaining=[]):
        start_time = datetime.datetime.now()
        total_users = len(users)
        success_count = 0
        error_count = 0
        flood_waits = 0

        print(
            f"👥 Аккаунт {self.phone} начал приглашение {total_users} пользователей в чат {chat_id}")

        try:
            for i, user in enumerate(users):
                try:
                    result = await self.Invite(chat_id, user)
                    if result:
                        success_count += 1
                        print_success(f"✅ Приглашен: {user}")
                    else:
                        print_warning(f"⚠️ Не удалось пригласить: {user}")

                    # Промежуточная статистика
                    if (i+1) % 10 == 0 or (i+1) == total_users:
                        elapsed = datetime.datetime.now() - start_time
                        elapsed_sec = elapsed.total_seconds()
                        mins, secs = divmod(int(elapsed_sec), 60)
                        elapsed_str = f"{mins}:{secs:02d}"

                        remaining_users = total_users - (i+1)
                        avg_time = elapsed_sec / (i+1) if i > 0 else 0
                        est_remaining = datetime.timedelta(
                            seconds=round(avg_time * remaining_users))

                        success_rate = success_count/(i+1)*100 if (i+1) > 0 else 0

                        print(
                            f"\n📊 АККАУНТ {self.phone} - ПРОМЕЖУТОЧНАЯ СТАТИСТИКА:")
                        print(f"   👤 Обработано: {i+1}/{total_users}")
                        print(f"   ✅ Успешно: {success_count}")
                        print(f"   ⚠️ Ошибок: {error_count}")
                        print(f"   ⏱️ Время: {elapsed_str}")
                        if remaining_users > 0:
                            print(
                                f"   🕐 Осталось: ~{str(est_remaining).split('.')[0]}")
                        print(f"   📈 Успешных приглашений: {success_rate:.1f}%")

                    await asyncio.sleep(random.randint(*wait))

                except errors.FloodWaitError as e:
                    flood_waits += 1
                    print_warning(f"⏳ Флуд-контроль! Ожидаем {e.seconds} сек.")
                    await asyncio.sleep(e.seconds)
                except Exception as e:
                    error_count += 1
                    print_error(f"❌ Ошибка для {user}: {str(e)}")

        except Exception as e:
            error_count += 1
            print_error(f"🛑 Критическая ошибка: {str(e)}")

        # Итоговая статистика
        elapsed = datetime.datetime.now() - start_time
        elapsed_sec = elapsed.total_seconds()
        mins, secs = divmod(int(elapsed_sec), 60)
        hours, mins = divmod(mins, 60)
        elapsed_str = f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"

        success_rate = success_count/total_users*100 if total_users > 0 else 0

        print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА АККАУНТА {self.phone}:")
        print(f"👥 Всего пользователей: {total_users}")
        print(f"✅ Успешно приглашено: {success_count}")
        print(f"⚠️ Ошибок: {error_count}")
        print(f"🚫 Flood Wait: {flood_waits} раз")
        print(f"⏱️ Время работы: {elapsed_str}")
        print(f"📈 Успешных приглашений: {success_rate:.1f}%")
        return success_count
    
    
    async def Invite(self, chat, user):
        try:
            chats = await self.client.get_entity(chat)
            users = await self.client.get_entity(user)
            invite = await self.client(
                functions.channels.InviteToChannelRequest(
                    chats,
                    [users],
                )
            )

            if invite.missing_invitees:
                if invite.missing_invitees[0].premium_required_for_pm:
                    print_success_with_start(
                        f"Пользователь {user} не может быть приглашен в {chat} (На аккаунте необходим ТГ премиум)")
                elif invite.missing_invitees[0].premium_would_allow_invite:
                    print_success_with_start(
                        f"Пользователь {user} не может быть приглашен в {chat} (На аккаунте необходим ТГ премиум и нельзя пригласить из за настроек приватности.)")
                else:
                    print_success_with_start(
                        f"Пользователь {user} не может быть приглашен в {chat} (Нельзя пригласить из за настроек приватности)")

            else:
                print_success_with_start(f"Пользователь {user} приглашен в чат {chat}")
                return True
        except (errors.rpcerrorlist.ChatAdminRequiredError):
            return None, "Нужны админ-права"
        except (errors.rpcerrorlist.ChatWriteForbiddenError):
            return None, "У вас нет доступа к данному чату"
        except (errors.rpcerrorlist.UserNotMutualContactError):
            print_error_with_start(
                f"Аккаунт {self.me.phone} получил флуд на добавление пользователей")
        except (
            errors.rpcerrorlist.InputUserDeactivatedError, errors.rpcerrorlist.PeerIdInvalidError,
            errors.rpcerrorlist.UserAlreadyParticipantError, errors.rpcerrorlist.UserIdInvalidError,
            errors.rpcerrorlist.UserPrivacyRestrictedError,
            errors.rpcerrorlist.PeerFloodError, errors.rpcerrorlist.UserKickedError,
            ValueError, errors.rpcerrorlist.UserChannelsTooMuchError, TypeError
        ) as e:
            print_error_with_start(f"error: {str(e)}")

        except errors.rpcerrorlist.AuthKeyDuplicatedError:
            await self.client.connect()
        except asyncio.IncompleteReadError:
            await self.client.connect()
        except ConnectionError:
            await self.client.connect()
        except errors.rpcerrorlist.UsersTooMuchError:
            return None, "В чате уже набрано максимальное количество пользователей"
        except errors.rpcerrorlist.FloodWaitError:
            return None, f"Флуд-задержка превысила {self.client.flood_sleep_threshold} сек."
        except (errors.ChannelsTooMuchError, errors.rpcerrorlist.ChannelPrivateError, errors.rpcerrorlist.InviteRequestSentError):
            return None, "У вас нет доступа к чату"
        except (errors.ChannelInvalidError):
            return None, "Чат не существует"
        except Exception as e:
            self.logger.error(e)
        # else:
        #     return True

    async def disconnect(self):
        if self.client and self.client.is_connected():
            await self.client.disconnect()
