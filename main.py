import logging
import asyncio
import json
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
TASKS_FILE = os.getenv("TASKS_FILE")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()

tasks = {}


def load_tasks():
    global tasks
    try:
        with open(TASKS_FILE, 'r') as f:
            tasks = json.load(f)
            logging.info(f'Loaded tasks: {tasks}')
    except (FileNotFoundError, json.JSONDecodeError):
        logging.info('Tasks file not found or invalid')
        tasks = {}

def save_tasks():
    global tasks
    try:
        with open(TASKS_FILE, 'w') as f:
            json.dump(tasks, f, indent=4)
    except Exception as e:
        logging.error(f'Failed to save tasks: {e}')

def get_user_data(user_id: str) -> dict:
    if user_id not in tasks:
        tasks[user_id] = {'tasks': [], 'categories': ['General']}
    return tasks[user_id]

def get_user_tasks(user_id: str) -> list:
    return get_user_data(user_id)['tasks']

def get_user_categories(user_id: str) -> list:
    return get_user_data(user_id)['categories']

def build_tasks_with_keyboard(user_id: str) -> tuple[str, InlineKeyboardMarkup]:
    user_tasks = get_user_tasks(user_id)
    if not user_tasks:
        return 'Список задач пуст', None
    res = ''
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for index, task in enumerate(user_tasks, start=1):
        buttons = [
            InlineKeyboardButton(text=f'Выполнить {index}', callback_data=f'done_{index}'),
            InlineKeyboardButton(text=f'Удалить {index}', callback_data=f'delete_{index}')
        ]
        keyboard.inline_keyboard.append(buttons)
        priority = task.get('priority', 'Medium')  # По умолчанию Medium
        res += (f"{index}. {task['task_name']} - {'Выполнено' if task['completed'] else 'Не выполнено'} - "
                f"{task['category']} - {priority}\n")
    return res.rstrip(), keyboard

def category_keyboard(task_name: str, categories: list) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    buttons = [
        InlineKeyboardButton(text=category, callback_data=f'category_{category}_{task_name}')
        for category in categories
    ]
    keyboard.inline_keyboard.append(buttons)
    return keyboard

def priority_keyboard(category: str, task_name: str) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    priorities = ['High', 'Medium', 'Low']
    buttons = [
        InlineKeyboardButton(text=priority, callback_data=f'priority_{priority}_{category}_{task_name}')
        for priority in priorities
    ]
    keyboard.inline_keyboard.append(buttons)
    return keyboard

@dp.message(Command(commands=['start']))
async def start(message: types.Message):
    await message.reply("Добро пожаловать! Я простой бот.\n"
                        "Используйте /add <задача> для добавления задач.")

@dp.message(Command(commands=['hello']))
async def hello(message: types.Message):
    await message.reply("Привет! Чем могу помочь?")

@dp.message(Command(commands=['categories']))
async def manage_categories(message: types.Message):
    user_id = str(message.from_user.id)
    parts = message.text.split(maxsplit=2)
    user_categories = get_user_categories(user_id)

    if len(parts) == 1:
        if not user_categories:
            await message.reply("У вас нет категорий. Добавьте с помощью /categories add <название>")
        else:
            await message.reply("Ваши категории:\n" + "\n".join(user_categories))
    elif len(parts) >= 2:
        action = parts[1].lower()
        if action == 'add' and len(parts) == 3:
            new_category = parts[2]
            if new_category in user_categories:
                await message.reply(f"Категория '{new_category}' уже существует")
            else:
                user_categories.append(new_category)
                save_tasks()
                await message.reply(f"Категория '{new_category}' добавлена")
        elif action == 'remove' and len(parts) == 3:
            category_to_remove = parts[2]
            if category_to_remove not in user_categories:
                await message.reply(f"Категория '{category_to_remove}' не найдена")
            elif category_to_remove == 'General':
                await message.reply("Нельзя удалить категорию 'General'")
            else:
                # Проверяем, используется ли категория в задачах
                if any(task['category'] == category_to_remove for task in get_user_tasks(user_id)):
                    await message.reply(f"Нельзя удалить '{category_to_remove}', так как она используется в задачах")
                else:
                    user_categories.remove(category_to_remove)
                    save_tasks()
                    await message.reply(f"Категория '{category_to_remove}' удалена")
        else:
            await message.reply("Используйте: /categories [add|remove] <название>")
    else:
        await message.reply("Используйте: /categories [add|remove] <название>")

@dp.message(Command(commands=['add']))
async def add(message: types.Message):
    try:
        user_id = str(message.from_user.id)
        task_name = message.text.split(maxsplit=1)[1]
        user_categories = get_user_categories(user_id)
        await message.reply('Выберите категорию', reply_markup=category_keyboard(task_name, user_categories))
    except IndexError:
        await message.reply('Укажите название задачи после /add\nПример: /add Buy milk')

@dp.message(Command(commands=['list']))
async def list_tasks(message: types.Message):
    user_id = str(message.from_user.id)
    res, keyboard = build_tasks_with_keyboard(user_id)
    await message.reply(res, reply_markup=keyboard)

@dp.message(Command(commands=['done']))
async def done(message: types.Message):
    user_id = str(message.from_user.id)
    user_tasks = get_user_tasks(user_id)
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            raise IndexError
        task_number = int(parts[1])
        if not (1 <= task_number <= len(user_tasks)):
            raise ValueError
        task = user_tasks[task_number - 1]
        task["completed"] = True
        save_tasks()
        await message.reply(f"'{task['task_name']}' отмечено как выполненное, у вас {len(user_tasks)} задач")
    except ValueError:
        await message.reply('Укажите корректный номер задачи (целое число) после /done')
    except IndexError:
        await message.reply('Укажите номер задачи после /done')

@dp.message(Command(commands=['delete']))
async def delete(message: types.Message):
    user_id = str(message.from_user.id)
    user_tasks = get_user_tasks(user_id)
    try:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            raise IndexError
        task_number = int(parts[1])
        if not (1 <= task_number <= len(user_tasks)):
            raise ValueError
        task = user_tasks[task_number - 1]
        del user_tasks[task_number - 1]
        save_tasks()
        await message.reply(f"'{task['task_name']}' удалено, у вас {len(user_tasks)} задач")
    except ValueError:
        await message.reply('Укажите корректный номер задачи (целое число) после /delete')
    except IndexError:
        await message.reply('Укажите номер задачи после /delete')

@dp.message(Command(commands=['clear']))
async def clear(message: types.Message):
    user_id = str(message.from_user.id)
    user_tasks = get_user_tasks(user_id)
    if not user_tasks:
        await message.reply('Ваш список задач пуст')
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text='Очистить', callback_data='clear'),
            InlineKeyboardButton(text='Отмена', callback_data='cancel')
        ]])
        await message.reply('Вы уверены, что хотите удалить все задачи?', reply_markup=keyboard)

@dp.callback_query(lambda c: c.data.startswith('done_') or c.data.startswith('delete_'))
async def process_task_callback(query: types.CallbackQuery):
    user_id = str(query.from_user.id)
    data = query.data
    user_tasks = get_user_tasks(user_id)
    try:
        if data.startswith('done_'):
            task_number = int(data.split('_')[1])
            if 1 <= task_number <= len(user_tasks):
                task = user_tasks[task_number - 1]
                task['completed'] = True
                save_tasks()
                await query.answer(f"'{task['task_name']}' отмечено как выполненное")
        elif data.startswith('delete_'):
            task_number = int(data.split('_')[1])
            if 1 <= task_number <= len(user_tasks):
                task = user_tasks[task_number - 1]
                del user_tasks[task_number - 1]
                save_tasks()
                await query.answer(f"'{task['task_name']}' удалено")
    except (ValueError, IndexError):
        await query.answer("Ошибка: неверный номер задачи")
        return

    res, keyboard = build_tasks_with_keyboard(user_id)
    await query.message.edit_text(res, reply_markup=keyboard)
    await query.answer()

@dp.callback_query(lambda c: c.data in ('clear', 'cancel'))
async def process_clear_callback(query: types.CallbackQuery):
    user_id = str(query.from_user.id)
    data = query.data
    user_tasks = get_user_tasks(user_id)
    if data == 'clear' and user_tasks:
        tasks[user_id]['tasks'] = []
        save_tasks()
        await query.message.edit_text('Список задач очищен')
        await query.answer('Очистка выполнена')
    else:
        await query.message.edit_text('Очистка отменена' if data == 'cancel' else 'Список задач уже пуст')
        await query.answer('Отмена')

@dp.callback_query(lambda c: c.data.startswith('category_'))
async def process_category_callback(query: types.CallbackQuery):
    try:
        user_id = str(query.from_user.id)
        data = query.data
        _, category, task_name = data.split('_', 2)
        await query.message.edit_text('Выберите приоритет',
                                      reply_markup=priority_keyboard(category, task_name))
        await query.answer()
    except ValueError:
        await query.answer('Ошибка при выборе категории')

@dp.callback_query(lambda c: c.data.startswith('priority_'))
async def process_priority_callback(query: types.CallbackQuery):
    try:
        user_id = str(query.from_user.id)
        data = query.data
        _, priority, category, task_name = data.split('_', 3)
        user_tasks = get_user_tasks(user_id)
        user_tasks.append({
            'task_name': task_name,
            'completed': False,
            'category': category,
            'priority': priority
        })
        save_tasks()
        await query.message.edit_text(f"'{task_name}' добавлено в [{category}, {priority}], "
                                      f"у вас {len(user_tasks)} задач")
        await query.answer(f"Задача '{task_name}' сохранена")
    except ValueError:
        await query.answer('Ошибка при добавлении задачи')

async def main():
    load_tasks()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())