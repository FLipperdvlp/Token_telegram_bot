import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    bot_token: str
    admin_id: int
    database_path: str


def load_config() -> Config:
    token = os.getenv('BOT_TOKEN', '').strip()
    admin = os.getenv('ADMIN_ID', '').strip()
    if not token or not admin.isdecimal():
        raise RuntimeError('Создайте .env рядом с bot.py и укажите BOT_TOKEN и числовой ADMIN_ID (пример в .env.example)')
    return Config(token, int(admin), os.getenv('DATABASE_PATH', 'filebind.sqlite3'))
