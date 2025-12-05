import psycopg2
from config import Config


def get_db():
    """Возвращает соединение с базой данных."""
    return psycopg2.connect(Config.DATABASE_URL)


def init_db():
    """Инициализирует базу данных (создает таблицы, если их нет)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ai_agents (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            model VARCHAR(255) NOT NULL,
            prompt TEXT NOT NULL,
            examples JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(255) NOT NULL,
            token_hash VARCHAR(255) NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            is_revoked BOOLEAN DEFAULT FALSE,
            token VARCHAR(255) NOT NULL
        )
    ''')
    conn.commit()
    cur.close()
    conn.close()


def get_ai_agent_by_id(id):
    """Возвращает ai_agent по id."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM ai_agents WHERE id = %s", (id,))
    ai_agent = cur.fetchone()
    cur.close()
    conn.close()
    return ai_agent
