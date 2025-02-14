import asyncio
import logging
import sqlite3  # Using SQLite

from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.utils import executor

TOKEN = "8125138623:AAGVv6Dl_nNx222okT1W0DsoQDHW4UwPR5c"

DB_FILE = "tasks.db"
db = sqlite3.connect(DB_FILE)
cursor = db.cursor()

# Create the tasks table
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        description TEXT NOT NULL,
        sender TEXT NOT NULL,
        recipient TEXT NOT NULL,
        due_date TEXT NOT NULL,
        importance TEXT CHECK (importance IN ('Low', 'Average', 'High')),
        status TEXT CHECK (status IN ('New', 'Accepted', 'Completed')) DEFAULT 'New'
    )
''')
db.commit()
db.close()

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Start command
@dp.message(Command("start"))
async def start_command(message: Message):
    await message.answer("Welcome! Use /new_task to create a task.")

# New Task command
@dp.message(Command("new_task"))
async def new_task_command(message: Message):
    await message.answer(
        "Send the task details in the format:\nTopic | Description | Recipient | Due Date (YYYY-MM-DD) | Importance (Low, Average, High)")

# My Tasks command
@dp.message(Command("my_tasks"))
async def my_tasks_command(message: Message):
    await message.answer("List of sent tasks")

# Receiving tasks
@dp.message(Command("tasks_for_me"))
async def receive_task(message: Message):
    try:
        data = message.text.split('|')
        if len(data) != 5:
            await message.answer("Invalid format! Use: Topic | Description | Recipient | Due Date | Importance")
            return

        topic, description, recipient, due_date, importance = [x.strip() for x in data]
        sender = message.from_user.username if message.from_user.username else message.from_user.full_name

        # Save to database
        db = sqlite3.connect(DB_FILE)
        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO tasks (topic, description, sender, recipient, due_date, importance, status) VALUES (?, ?, ?, ?, ?, ?, 'New')",
            (topic, description, sender, recipient, due_date, importance))
        db.commit()
        db.close()

        await message.answer(f"Task '{topic}' assigned to {recipient}!")
    except Exception as e:
        logging.error(f"Error: {e}")
        await message.answer("Something went wrong! Try again.")

# Run bot
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
