from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

CLAIM = '🎟️ Взять токен'
STATS = '📊 Статистика'
PROFILE = '👤 Профиль'

def group_keyboard():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text=CLAIM)],
        [KeyboardButton(text=STATS), KeyboardButton(text=PROFILE)]
    ], resize_keyboard=True, is_persistent=True, input_field_placeholder='✨ Выберите действие')

def verdict_keyboard(issue_id: int):
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='✅ Встал', callback_data=f'vote:{issue_id}:ok'),
        InlineKeyboardButton(text='❌ Не встал', callback_data=f'vote:{issue_id}:fail')
    ]])

def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📊 Обзор', callback_data='adm:stats'), InlineKeyboardButton(text='📦 Остаток', callback_data='adm:pool')],
        [InlineKeyboardButton(text='📜 История выдач', callback_data='adm:history')],
        [InlineKeyboardButton(text='📤 Загрузить записи', callback_data='adm:upload')],
        [InlineKeyboardButton(text='🗑️ Исключить запись', callback_data='adm:delete')],
        [InlineKeyboardButton(text='🏠 Главная', callback_data='adm:home')]
    ])
