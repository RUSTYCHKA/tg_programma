from quart import flash
from datetime import datetime
from auth import generate_token
from config import Config


async def handle_admin_form(password: str, user_id: str, expires_at: str, request) -> str:
    """Обрабатывает форму админки и возвращает токен."""
    if password != Config.ADMIN_PASSWORD:
        await flash('Неверный пароль', 'error')
        return None

    if not user_id or not expires_at:
        await flash('Заполните все поля', 'error')
        return None

    try:
        expires_at = datetime.strptime(expires_at, '%Y-%m-%dT%H:%M')
    except ValueError:
        await flash('Неправильный формат даты. Используйте ГГГГ-ММ-ДД ЧЧ:ММ', 'error')
        return None

    token = generate_token(user_id, expires_at)
    return token
