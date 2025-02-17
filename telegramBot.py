import asyncio
import logging
import sqlite3

from aiogram import Bot, Dispatcher
from aiogram.types import Message, BotCommand


from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F, Router

from Database import add_user, get_user_id, init_database, DB_FILE, get_all_usernames
from reminder import scheduler, send_reminder

callback_router = Router()

from aiogram.types import CallbackQuery
from aiogram_calendar.simple_calendar import SimpleCalendar, SimpleCalendarCallback
calendar = SimpleCalendar()




class NewTask(StatesGroup):
    topic = State()
    description = State()
    recipient = State()
    deadline = State()
    importance = State()



TOKEN = "8125138623:AAGVv6Dl_nNx222okT1W0DsoQDHW4UwPR5c"

# Initialize bot and dispatcher
bot = Bot(token=TOKEN)
dp = Dispatcher()



async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Launch the bot"),
        BotCommand(command="new_task", description="Create a task"),
        BotCommand(command="my_tasks", description="List of sent tasks"),
        BotCommand(command="tasks_for_me", description="List of received tasks"),
        BotCommand(command="stats", description="List of statistics"),
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
    users = get_all_usernames()

    if not users:
        await message.answer("⚠️ No users found in the system.")
        return

    user_list = "\n".join([f"`@{user}`" for user in users])

    await message.answer(
        f"📌 **Available Users:**\n{user_list}\n\n"
        "Enter the task **Topic**:")
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
    recipient_username = message.text.strip().lstrip("@")
    recipient_id = get_user_id(recipient_username)

    if recipient_id is None:
        await message.answer("❌ The recipient **has not started the bot yet**. They need to send `/start` first.")
        return

    await state.update_data(recipient_id=recipient_id, recipient_username=recipient_username)

    await message.answer("📅 **Choose a deadline date:**", reply_markup=await SimpleCalendar().start_calendar())

@dp.callback_query(SimpleCalendarCallback.filter())
async def process_calendar_selection(callback_query: CallbackQuery, callback_data: dict, state: FSMContext):
    selected, date = await SimpleCalendar().process_selection(callback_query, callback_data)

    if selected:
        formatted_date = date.strftime("%Y-%m-%d")  # Convert to YYYY-MM-DD format

        # ✅ Store selected date in FSM
        await state.update_data(deadline=formatted_date)

        await callback_query.message.answer(f"📌 **Deadline Selected:** {formatted_date}\nNow enter the **importance (Low, Average, High)**:")
        await state.set_state(NewTask.importance)




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
    recipient_id = callback_query.from_user.id  # ✅ Get recipient ID
    recipient_username = callback_query.from_user.username if callback_query.from_user.username else callback_query.from_user.full_name

    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()

    cursor.execute("SELECT sender, topic, description, due_date, importance FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()

    if not task:
        await callback_query.answer("⚠️ Task not found!")
        db.close()
        return

    sender_username, topic, description, deadline, importance = task

    cursor.execute("SELECT user_id FROM users WHERE username = ?", (sender_username,))
    sender = cursor.fetchone()
    sender_id = sender[0] if sender else None  # Extract sender ID or set to None

    # ✅ Update task status to "Accepted"
    cursor.execute("UPDATE tasks SET status = 'Accepted' WHERE id = ?", (task_id,))
    db.commit()
    db.close()

    # ✅ Keep the task message but replace buttons with "End Task" button
    new_text = (f"📢 **New Task Assigned!**\n\n"
                f"📝 **Topic:** {topic}\n"
                f"📄 **Description:** {description}\n"
                f"📅 **Deadline:** {deadline}\n"
                f"⚡ **Importance:** {importance}\n"
                f"📌 **Assigned by:** @{sender_username}\n\n"
                f"✅ **Task Accepted** by @{recipient_username}!")

    # ✅ Show only "End Task" button after accepting
    end_task_button = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ End Task", callback_data=f"complete_task_{task_id}")]
    ])

    await callback_query.message.edit_text(new_text, reply_markup=end_task_button)  # ✅ Keep message + End Task button

    # ✅ Notify the sender (delete message after 5 sec)
    if sender_id:
        try:
            sent_message = await bot.send_message(sender_id, f"📢 **Task Accepted!**\n\n"
                                                             f"Your task **{task_id}** has been accepted by **@{recipient_username}**.")
            await asyncio.sleep(5)
            await bot.delete_message(sender_id, sent_message.message_id)
        except Exception as e:
            print(f"⚠️ Could not send message to sender: {e}")

    await callback_query.answer("Task Accepted ✅")




@dp.callback_query(F.data.startswith("complete_task_"))
async def complete_task_callback(callback_query: CallbackQuery):
    task_id = callback_query.data.split("_")[2]
    recipient_id = callback_query.from_user.id  # ✅ Get recipient ID
    recipient_username = callback_query.from_user.username if callback_query.from_user.username else callback_query.from_user.full_name

    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()

    # ✅ Get task details
    cursor.execute("SELECT sender, topic, description, due_date, importance FROM tasks WHERE id = ?", (task_id,))
    task = cursor.fetchone()

    if not task:
        await callback_query.answer("⚠️ Task not found!")
        db.close()
        return

    sender_username, topic, description, deadline, importance = task

    # ✅ Get sender's Telegram ID
    cursor.execute("SELECT user_id FROM users WHERE username = ?", (sender_username,))
    sender = cursor.fetchone()
    sender_id = sender[0] if sender else None  # Extract sender ID or set to None

    # ✅ Update task status to "Completed"
    cursor.execute("UPDATE tasks SET status = 'Completed' WHERE id = ?", (task_id,))
    db.commit()
    db.close()

    # ✅ Keep task message but remove buttons
    new_text = (f"📢 **New Task Assigned!**\n\n"
                f"📝 **Topic:** {topic}\n"
                f"📄 **Description:** {description}\n"
                f"📅 **Deadline:** {deadline}\n"
                f"⚡ **Importance:** {importance}\n"
                f"📌 **Assigned by:** @{sender_username}\n\n"
                f"✅ **Task Completed** by @{recipient_username}! 🎉")

    await callback_query.message.edit_text(new_text)  # ✅ Keep message but remove buttons

    # ✅ Notify the sender (delete message after 5 sec)
    if sender_id:
        try:
            sent_message = await bot.send_message(sender_id, f"🎉 **Task Completed!**\n\n"
                                                             f"Your task **{task_id}** has been marked as **completed** by **@{recipient_username}**.")
            await asyncio.sleep(5)
            await bot.delete_message(sender_id, sent_message.message_id)
        except Exception as e:
            print(f"⚠️ Could not send message to sender: {e}")

    await callback_query.answer("Task Completed ✅")

@dp.message(Command("my_tasks"))
async def my_tasks_command(message: Message):
    print("DEBUG: /my_tasks command triggered")  # ✅ Debugging line

    sender = message.from_user.username if message.from_user.username else message.from_user.full_name

    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()
    cursor.execute("SELECT id, topic, recipient, due_date, importance, status FROM tasks WHERE sender = ?", (sender,))
    tasks = cursor.fetchall()
    db.close()

    if not tasks:
        await message.answer("📌 **No tasks have been sent by you.**")
        return

    response = "📌 **Your Sent Tasks:**\n\n"
    for task in tasks:
        response += f"🆔 **Task ID:** {task[0]}\n" \
                    f"📌 **Topic:** {task[1]}\n" \
                    f"📌 **Recipient:** @{task[2]}\n" \
                    f"📅 **Deadline:** {task[3]}\n" \
                    f"⚡ **Importance:** {task[4]}\n" \
                    f"📌 **Status:** `{task[5]}`\n\n"

    await message.answer(response, parse_mode="Markdown")


@dp.message(Command("tasks_for_me"))
async def tasks_for_me_command(message: Message):
    recipient = str(message.from_user.id)  # ✅ FIX: Use Telegram user ID instead of username


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






import calendar
@dp.message(Command("stats"))
async def stats_command(message: Message):
    user_id = message.from_user.id

    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()

    # ✅ Count "In Progress" tasks
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE recipient = ? AND status = 'Accepted'", (user_id,))
    in_progress = cursor.fetchone()[0]

    # ✅ Count "Completed" tasks per month
    cursor.execute("""
        SELECT COALESCE(substr(due_date, 6, 2), '00') AS month, COUNT(*) 
        FROM tasks 
        WHERE recipient = ? AND status = 'Completed' 
        GROUP BY month 
        ORDER BY month ASC
    """, (user_id,))
    completed_tasks = cursor.fetchall()

    # ✅ Count "Assigned" tasks per month
    cursor.execute("""
        SELECT COALESCE(substr(due_date, 6, 2), '00') AS month, COUNT(*) 
        FROM tasks 
        WHERE sender = ? 
        GROUP BY month 
        ORDER BY month ASC
    """, (user_id,))
    assigned_tasks = cursor.fetchall()

    db.close()


    # ✅ Format response
    response = "📊 **Task Statistics:**\n\n"
    response += f"📌 **In Progress Tasks:** {in_progress}\n\n"

    # ✅ Format Completed Tasks
    response += "✅ **Completed Tasks Per Month:**\n"
    if completed_tasks:
        for month, count in completed_tasks:
            try:
                month_int = int(month.lstrip("0")) if month and month not in ["00", None] else 0
                if 1 <= month_int <= 12:
                    month_name = calendar.month_name[month_int]  # ✅ FIXED HERE
                else:
                    month_name = "Unknown"
            except (ValueError, TypeError):
                month_name = "Unknown"
            print(f"DEBUG: Month={month}, Converted={month_int}, Month Name={month_name}")  # ✅ Debugging
            response += f"📅 {month_name}: {count}\n"
    else:
        response += "No completed tasks yet.\n"

    response += "\n"

    # ✅ Format Assigned Tasks
    response += "📌 **Assigned Tasks Per Month:**\n"
    if assigned_tasks:
        for month, count in assigned_tasks:
            try:
                month_int = int(month.lstrip("0")) if month and month not in ["00", None] else 0
                if 1 <= month_int <= 12:
                    month_name = calendar.month_name[month_int]  # ✅ FIXED HERE
                else:
                    month_name = "Unknown"
            except (ValueError, TypeError):
                month_name = "Unknown"
    else:
        response += "No assigned tasks yet.\n"

    await message.answer(response)


# Run bot
async def main():
    init_database()
    scheduler.start()
    await set_bot_commands(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())



