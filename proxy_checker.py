import requests
import threading
from queue import Queue

# تنظیمات
test_url = "http://httpbin.org/ip"
proxies_to_check = [
    "http://185.105.102.189:80",  # فقط چند پروکسی برای تست
    "http://209.97.150.167:8080",
    "http://51.178.43.70:3128"
]
working_proxies = []
queue = Queue()

# تابع تست پروکسی
def check_proxy(proxy):
    try:
        response = requests.get(test_url, proxies={"http": proxy, "https": proxy}, timeout=5)
        if response.status_code == 200:
            print(f"پروکسی {proxy} کار می‌کنه!")
            working_proxies.append(proxy)
        else:
            print(f"پروکسی {proxy} کار نمی‌کنه! کد پاسخ: {response.status_code}")
    except:
        print(f"پروکسی {proxy} خرابه!")

# تابع چندنخی
def worker():
    while True:
        proxy = queue.get()
        if proxy is None:
            break
        check_proxy(proxy)
        queue.task_done()

# پر کردن صف و اجرای تست
for proxy in proxies_to_check:
    queue.put(proxy)

threads = []
for _ in range(3):  # فقط ۳ نخ برای تست
    thread = threading.Thread(target=worker)
    threads.append(thread)
    thread.start()

queue.join()

# توقف رشته‌ها
for _ in range(3):
    queue.put(None)
for thread in threads:
    thread.join()

# نمایش پروکسی‌های سالم
print("\nپروکسی‌های سالم:")
for proxy in working_proxies:
    print(proxy)
