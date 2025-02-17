import asyncio
import logging
import sqlite3

from aiogram import Bot, Dispatcher
from aiogram.types import Message, BotCommand
from aiogram.types import CallbackQuery


from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F, Router

from Database import add_user, get_user_id, init_database

callback_router = Router()


class NewTask(StatesGroup):
    topic = State()
    description = State()
    recipient = State()
    deadline = State()
    importance = State()



TOKEN = "8125138623:AAGVv6Dl_nNx222okT1W0DsoQDHW4UwPR5c"

DB_FILE = "tasks.db"
# Connect to SQLite database
db = sqlite3.connect(DB_FILE)
cursor = db.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT UNIQUE
    )
''')


cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic TEXT NOT NULL,
        description TEXT NOT NULL,
        sender TEXT NOT NULL,
        recipient INTEGER NOT NULL,
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



async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Launch the bot"),
        BotCommand(command="new_task", description="Create a task"),
        BotCommand(command="my_tasks", description="List of sent tasks"),
        BotCommand(command="tasks_for_me", description="List of received tasks"),
    ]
    await bot.set_my_commands(commands)


# Start command
@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username if message.from_user.username else f"user_{user_id}"

    # Store user details in the database
    add_user(user_id, username)

    await message.answer("👋 Welcome! You can now receive tasks or Use /new_task to create a task ")


# New Task command
@dp.message(Command("new_task"))
async def new_task_command(message: Message, state: FSMContext):
    await message.answer("Enter the task **Topic**:")
    await state.set_state(NewTask.topic)

@dp.message(NewTask.topic)
async def process_topic(message: Message, state: FSMContext):
    await state.update_data(topic=message.text)
    await message.answer("Enter the **Task Description**:")
    await state.set_state(NewTask.description)

@dp.message(NewTask.description)
async def process_description(message: Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Enter the **Recipient's Username** (@username):")
    await state.set_state(NewTask.recipient)


@dp.message(NewTask.recipient)
async def process_recipient(message: Message, state: FSMContext):
    recipient_username = message.text.strip()

    # Remove '@' if user entered it
    if recipient_username.startswith("@"):
        recipient_username = recipient_username[1:]

    # Fetch user ID from database (if already stored)
    recipient_id = get_user_id(recipient_username)

    if recipient_id is None:
        await message.answer("❌ Error: I cannot find this user. The recipient must first **start the bot**.")
        return

    await state.update_data(recipient_id=recipient_id, recipient_username=recipient_username)
    await message.answer("Enter the **Deadline** (YYYY-MM-DD):")
    await state.set_state(NewTask.deadline)


@dp.message(NewTask.deadline)
async def process_deadline(message: Message, state: FSMContext):
    await state.update_data(deadline=message.text)
    await message.answer("Enter the **Importance** (Low, Average, High):")
    await state.set_state(NewTask.importance)

@dp.message(NewTask.importance)
async def process_importance(message: Message, state: FSMContext):
    importance = message.text.capitalize()
    if importance not in ["Low", "Average", "High"]:
        await message.answer("Invalid choice! Please enter **Low, Average, or High**.")
        return

    await state.update_data(importance=importance)

    # Retrieve all task details from FSM
    task_data = await state.get_data()
    sender = message.from_user.username if message.from_user.username else message.from_user.full_name

    # Save task to database
    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO tasks (topic, description, sender, recipient, due_date, importance, status) VALUES (?, ?, ?, ?, ?, ?, 'New')",
        (task_data['topic'], task_data['description'], sender, task_data['recipient_id'], task_data['deadline'], task_data['importance'])
    )
    db.commit()
    task_id = cursor.lastrowid  # Get the last inserted task ID
    db.close()

    # Send task notification to recipient
    recipient_id = task_data['recipient_id']  # Fetch user ID from stored data
    accept_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Accept Task", callback_data=f"accept_task_{task_id}")]
    ])

    try:
        await bot.send_message(chat_id=recipient_id, text=f"📢 **New Task Assigned!**\n\n"
                                 f"📝 **Topic:** {task_data['topic']}\n"
                                 f"📄 **Description:** {task_data['description']}\n"
                                 f"📅 **Deadline:** {task_data['deadline']}\n"
                                 f"⚡ **Importance:** {task_data['importance']}\n"
                                 f"📌 **Assigned by:** @{sender}\n\n"
                                 f"Click below to accept this task:", reply_markup=accept_button)
    except Exception as e:
        print(f"⚠️ Error sending message: {e}")
        await message.answer("❌ I couldn't send the task notification. The recipient must first start the bot.")

    # Confirm to sender
    await message.answer(f"✅ **Task Created Successfully!**\n\nThe recipient has been notified.")

    # Finish FSM
    await state.clear()


@dp.callback_query(F.data.startswith("accept_task_"))
async def accept_task_callback(callback_query: CallbackQuery):
    task_id = callback_query.data.split("_")[2]
    recipient_username = callback_query.from_user.username if callback_query.from_user.username else callback_query.from_user.full_name

    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()

    cursor.execute("SELECT sender FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()

    if not task:
        await callback_query.answer("⚠️ Task not found!")
        db.close()
        return

    sender_username = task[0]  # Extract sender username

    cursor.execute("SELECT user_id FROM users WHERE username = ?", (sender_username,))
    sender = cursor.fetchone()

    if sender:
        sender_id = sender[0]  # Extract stored user ID
    else:
        sender_id = None  # Sender hasn't started the bot

    cursor.execute("UPDATE tasks SET status = 'Accepted' WHERE id = ?", (task_id,))
    db.commit()
    db.close()

    end_task_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ End Task", callback_data=f"complete_task_{task_id}")]
    ])

    await callback_query.message.edit_text(f"✅ Task **{task_id}** has been **accepted** by @{recipient_username}!\n"
                                           f"Click below when the task is complete:", reply_markup=end_task_button)

    if sender_id:
        try:
            await bot.send_message(sender_id, f"📢 **Task Accepted!**\n\n"
                                              f"Your task **{task_id}** has been accepted by **@{recipient_username}**.")
        except Exception as e:
            print(f"⚠️ Could not send message to sender: {e}")

    await callback_query.answer("Task Accepted ✅")


@dp.callback_query(F.data.startswith("complete_task_"))
async def complete_task_callback(callback_query: CallbackQuery):
    task_id = callback_query.data.split("_")[2]
    recipient_username = callback_query.from_user.username if callback_query.from_user.username else callback_query.from_user.full_name

    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()

    cursor.execute("SELECT sender FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()

    if not task:
        await callback_query.answer("⚠️ Task not found!")
        db.close()
        return

    sender_username = task[0]  # Extract sender username

    cursor.execute("SELECT user_id FROM users WHERE username = ?", (sender_username,))
    sender = cursor.fetchone()

    if sender:
        sender_id = sender[0]  # Extract stored user ID
    else:
        sender_id = None  # Sender hasn't started the bot

    cursor.execute("UPDATE tasks SET status = 'Completed' WHERE id = ?", (task_id,))
    db.commit()
    db.close()


    await callback_query.message.edit_text(f"🎉 Task **{task_id}** has been **marked as completed** by @{recipient_username}!")

    if sender_id:
        try:
            await bot.send_message(sender_id, f"🎉 **Task Completed!**\n\n"
                                              f"Your task **{task_id}** has been marked as **completed** by **@{recipient_username}**.")
        except Exception as e:
            print(f"⚠️ Could not send message to sender: {e}")

    await callback_query.answer("Task Completed ✅")



@dp.message(Command("my_tasks"))
async def my_tasks_command(message: Message):
    sender = message.from_user.username if message.from_user.username else message.from_user.full_name

    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()
    cursor.execute("SELECT id, topic, due_date, importance, status FROM tasks WHERE sender = ?", (sender,))
    tasks = cursor.fetchall()
    db.close()

    if not tasks:
        await message.answer("📌 **You haven't assigned any tasks yet.**")
        return

    response = "📌 **Your Sent Tasks:**\n\n"
    for task in tasks:
        response += f"🆔 **Task ID:** {task[0]}\n" \
                    f"📌 **Topic:** {task[1]}\n" \
                    f"📅 **Deadline:** {task[2]}\n" \
                    f"⚡ **Importance:** {task[3]}\n" \
                    f"📌 **Status:** `{task[4]}`\n\n"

    await message.answer(response, parse_mode="Markdown")


@dp.message(Command("tasks_for_me"))
async def tasks_for_me_command(message: Message):
    recipient = message.from_user.username if message.from_user.username else message.from_user.full_name

    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()
    cursor.execute("SELECT id, topic, sender, due_date, importance, status FROM tasks WHERE recipient = ?", (recipient,))
    tasks = cursor.fetchall()
    db.close()

    if not tasks:
        await message.answer("📌 **No tasks have been assigned to you.**")
        return

    response = "📌 **Tasks Assigned to You:**\n\n"
    for task in tasks:
        response += f"🆔 **Task ID:** {task[0]}\n" \
                    f"📌 **Topic:** {task[1]}\n" \
                    f"📌 **Assigned by:** @{task[2]}\n" \
                    f"📅 **Deadline:** {task[3]}\n" \
                    f"⚡ **Importance:** {task[4]}\n" \
                    f"📌 **Status:** `{task[5]}`\n\n"

    await message.answer(response, parse_mode="Markdown")


# Run bot
async def main():
    init_database()
    await set_bot_commands(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
