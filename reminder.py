import sqlite3
import datetime
from aiogram import Bot, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

DB_FILE = "tasks.db"
TOKEN = "8125138623:AAGVv6Dl_nNx222okT1W0DsoQDHW4UwPR5c"

scheduler = AsyncIOScheduler()

async def send_reminder():
    from telegramBot import bot, dp  # ✅ Import bot and dispatcher

    db = sqlite3.connect(DB_FILE)
    cursor = db.cursor()

    # ✅ Get today's date and future dates
    today = datetime.date.today()
    future_dates = {
        "5 days": today + datetime.timedelta(days=5),
        "3 days": today + datetime.timedelta(days=3),
        "1 day": today + datetime.timedelta(days=1),
    }

    # ✅ Fetch uncompleted tasks
    cursor.execute("""
        SELECT id, topic, recipient, due_date 
        FROM tasks 
        WHERE status != 'Completed'
    """)
    tasks = cursor.fetchall()
    db.close()

    for task in tasks:
        task_id, topic, recipient_id, due_date_str = task
        due_date = datetime.datetime.strptime(due_date_str, "%Y-%m-%d").date()

        for days, reminder_date in future_dates.items():
            if due_date == reminder_date:
                try:
                    # ✅ Create "End Task" button
                    end_task_button = InlineKeyboardMarkup(
                        inline_keyboard=[[InlineKeyboardButton(text="✅ End Task", callback_data=f"end_task_{task_id}")]]
                    )

                    await bot.send_message(
                        chat_id=recipient_id,
                        text=f"⏳ **Reminder: Your task is due in {days}!**\n\n"
                             f"📌 **Task:** {topic}\n"
                             f"📅 **Due Date:** {due_date_str}\n\n"
                             f"✅ Please complete it on time!",
                        reply_markup=end_task_button
                    )
                    print(f"Sent reminder for Task ID {task_id} due in {days}")
                except Exception as e:
                    print(f"⚠️ Failed to send reminder to {recipient_id}: {e}")

# ✅ Schedule the job to run daily at 09:00 AM
scheduler.add_job(send_reminder, "cron", hour=9, minute=0)
