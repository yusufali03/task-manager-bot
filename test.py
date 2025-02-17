# import calendar
#
# test_months = ["02", "11", "03", "00", None]
#
# for month in test_months:
#     try:
#         month_int = int(month.lstrip("0")) if month and month not in ["00", None] else 0
#         month_name = calendar.month_name[month_int] if 1 <= month_int <= 12 else "Unknown"
#     except (ValueError, TypeError):
#         month_name = "Unknown"
#
#     print(f"Extracted Month: {month}, Converted: {month_int}, Month Name: {month_name}")


import asyncio
from reminder import send_reminder

asyncio.run(send_reminder())  # ✅ This will manually trigger reminders NOW
