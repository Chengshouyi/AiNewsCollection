from datetime import datetime
import pytz
   
# 獲取當前時間
now = datetime.now()
print(f"Local time: {now}")

# 獲取系統時區
import time
print(f"System timezone: {time.tzname}")

# 獲取 pytz 時區
tz = pytz.timezone('Asia/Taipei')
taipei_time = datetime.now(tz)
print(f"Taipei time: {taipei_time}")