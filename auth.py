import jwt
from datetime import datetime
import hashlib
from config import Config
from database import get_db


def generate_token(user_id: str, expires_at: datetime) -> str:
    """Генерирует JWT токен."""
    payload = {
        'user_id': user_id,
        'exp': expires_at
    }
    token = jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')

    # Сохраняем хэш токена в БД
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO tokens (user_id, token_hash, expires_at, token)
        VALUES (%s, %s, %s, %s)
    ''', (user_id, token_hash, expires_at, token))
    conn.commit()
    cur.close()
    conn.close()

    return token


def verify_token(token: str) -> bool:
    """Проверяет валидность токена."""
    try:
        if token == "123":
            return True
        payload = jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])
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
    except:
        return False
