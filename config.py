import os
from pathlib import Path
import sys
from dotenv import load_dotenv


def get_base_dir():
    # Если мы запускаем из .exe, берём директорию где лежит .exe
    if getattr(sys, 'frozen', False):
        # Возвращаем родительскую папку для exe
        return Path(sys.executable).parent.parent
    # Иначе используем обычную базовую директорию (папка с .py)
    return Path(__file__).parent

class Config:
    SECRET_KEY = '157c58a6d03c40ed45b6d98bf64545afc673d82c67bb3a54b23857a14df18d418447db6676d3ab4557a563b55b2b2298a2a2135e1a1655d5fb5b805e38539a7a1fed907ff1cd1fec1cb7bf42c466ead6888ce931d079954f7bf7e840fcea768de0b5dbdce469a2ebd343fcf4ebdf9b8c85d1b452d4fbe382679ad0da0bcae1ba6802bee49c28fcd119e1586b8e3c6a25a92e7f764d988a822151aa64f9603d2637cc3f6d4d7605b62edf52af5fe38ff0e54383282dfdf39303c4eaf6ced20a25d069567127f0dae8353390aa5ea8d54a8c51421f80c9a06987f86a32b134872676b025fa33e838b17bb6a918a2a9a34e0324d49a642a54ce5c1536c584a766238366ca14000979be6ba87ca7b10daaf3ae18a4b4ac472061e0da28b58881b1e8bc326d10d7a877fe09f5a5bc7278ee3742c6bc97530f0291f0808ee285dcc10704b67ffadaea777289cf732735dab586ee6079605408d7eb8ad9d77517d143b794c6095b345ddea70274845508d0890ea87bf3d5d949b94cd9be233215095b8aef4e8cc0785a78c9a06c05861accd8223238f235ad5d68b8eec07d41f2ae6a3195e73a04a3f2e819236f1bd838d6b8d567d831d19903e4e891f1997ea38acdb01ac1868d438cb7d6ca2a346b14c4d86c3e8fcdd1c9228b73d00f155201df80bf13b04e331a46362258ed08b2d0f76a3efc09ac160c3341ed7c4a49387ee62f87'
    DATABASE_URL = 'postgresql://postgres:KbfNsrkPzwGU@45.146.167.136:5432/tg'
    BASE_DIR = get_base_dir()
    ACCOUNTS_DIR = BASE_DIR / 'Аккаунты'
    WORKING_DIR = ACCOUNTS_DIR / 'Для работы'
    ARCHIVE_DIR = ACCOUNTS_DIR / 'Архив'
    ADMIN_PASSWORD = 'Mike895489R'
    API_KEY ="AIzaSyCno7SIRjTcU6yUSdxs9KcAG8PGgALns48"
