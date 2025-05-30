import requests
import threading
import logging
from queue import Queue

# تنظیمات لاگ‌گیری
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# لیست برای ذخیره پروکسی‌های سالم
healthy_proxies = []
lock = threading.Lock()

# صف برای نگهداری پروکسی‌ها جهت بررسی
proxy_queue = Queue()

# تعداد تردها برای بررسی همزمان
NUM_THREADS = 50 # می‌توانید این عدد را بر اساس توان سیستم خود تغییر دهید

# آدرس برای تست پروکسی
TEST_URL = 'http://httpbin.org/ip' # این سایت IP شما (یا پروکسی) را برمی‌گرداند
# می‌توانید از سایت‌های دیگری مانند 'http://www.google.com' هم استفاده کنید،
# اما توجه داشته باشید که برخی سایت‌ها ممکن است درخواست‌های زیاد از یک IP را مسدود کنند.

def check_proxy(q):
    """
    یک پروکسی را از صف برداشته و سلامت آن را بررسی می‌کند.
    """
    while not q.empty():
        proxy = q.get()
        proxy_url = f"http://{proxy}" # اضافه کردن http://
        proxies = {
            "http": proxy_url,
            "https": proxy_url, # برخی پروکسی‌ها برای https هم همین آدرس را استفاده می‌کنند
        }
        timeout_seconds = 5 # زمان انتظار برای پاسخ (ثانیه)
        try:
            logging.info(f"درحال بررسی پروکسی: {proxy_url}")
            response = requests.get(TEST_URL, proxies=proxies, timeout=timeout_seconds, verify=False) # verify=False برای نادیده گرفتن خطاهای SSL است، در صورت نیاز می‌توانید آن را True کنید.
            if response.status_code == 200:
                with lock:
                    healthy_proxies.append(proxy_url)
                logging.info(f"پروکسی سالم: {proxy_url} - وضعیت: {response.status_code}")
            else:
                logging.warning(f"پروکسی ناسالم: {proxy_url} - وضعیت: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logging.error(f"خطا در اتصال به پروکسی: {proxy_url} - خطا: {e}")
        finally:
            q.task_done()

def load_proxies_from_file(filename="proxies.txt"):
    """
    لیست پروکسی‌ها را از یک فایل می‌خواند.
    هر پروکسی باید در یک خط جداگانه و با فرمت IP:PORT باشد.
    """
    try:
        with open(filename, 'r') as f:
            proxies_list = [line.strip() for line in f if line.strip()]
        if not proxies_list:
            logging.warning(f"فایل '{filename}' خالی است یا هیچ پروکسی معتبری در آن یافت نشد.")
            return []
        logging.info(f"تعداد {len(proxies_list)} پروکسی از فایل '{filename}' خوانده شد.")
        return proxies_list
    except FileNotFoundError:
        logging.error(f"فایل '{filename}' یافت نشد. لطفاً فایل را در مسیر صحیح قرار دهید یا نام آن را در کد اصلاح کنید.")
        return []
    except Exception as e:
        logging.error(f"خطا در خواندن فایل پروکسی: {e}")
        return []

if __name__ == "__main__":
    # خواندن پروکسی‌ها از فایل
    proxies_to_check = load_proxies_from_file("proxies.txt") # مطمئن شوید نام فایل صحیح است

    if proxies_to_check:
        # اضافه کردن پروکسی‌ها به صف
        for p in proxies_to_check:
            proxy_queue.put(p)

        logging.info(f"شروع بررسی {proxy_queue.qsize()} پروکسی با {NUM_THREADS} ترد...")

        # ایجاد و اجرای تردها
        threads = []
        for _ in range(NUM_THREADS):
            thread = threading.Thread(target=check_proxy, args=(proxy_queue,))
            thread.daemon = True # تردها با بسته شدن برنامه اصلی بسته می‌شوند
            thread.start()
            threads.append(thread)

        # منتظر ماندن تا تمام آیتم‌های صف پردازش شوند
        proxy_queue.join()

        # منتظر ماندن تا تمام تردها کار خود را تمام کنند (اختیاری، چون join صف کار مشابهی انجام می‌دهد)
        # for t in threads:
        # t.join()

        logging.info("بررسی تمام پروکسی‌ها به پایان رسید.")

        # چاپ نتایج
        print("\n--- پروکسی‌های سالم ---")
        if healthy_proxies:
            for hp in healthy_proxies:
                print(hp)
            print(f"\nتعداد کل پروکسی‌های سالم: {len(healthy_proxies)}")
        else:
            print("هیچ پروکسی سالمی یافت نشد.")
    else:
        print("هیچ پروکسی برای بررسی وجود ندارد.")
