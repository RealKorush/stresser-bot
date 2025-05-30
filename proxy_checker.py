import requests
import time

# نام فایل حاوی پروکسی‌ها
PROXY_FILE = "working_proxies.txt"

# آدرس‌های مورد استفاده برای تست
# httpbin.org/ip آی‌پی شما (یا پروکسی) را برمی‌گرداند
TARGET_URL_HTTP = "http://httpbin.org/ip"
TARGET_URL_HTTPS = "https://httpbin.org/ip"

# زمان انتظار برای هر درخواست (به ثانیه)
REQUEST_TIMEOUT = 10 # می‌توانید این مقدار را کم یا زیاد کنید

def load_proxies(filename=PROXY_FILE):
    """پروکسی‌ها را از فایل می‌خواند و http:// را در صورت نیاز اضافه می‌کند."""
    proxies_list = []
    try:
        with open(filename, 'r') as f:
            for line in f:
                proxy = line.strip()
                if proxy and not proxy.startswith("#"): # نادیده گرفتن خطوط خالی و کامنت‌ها
                    if not proxy.startswith("http://") and not proxy.startswith("https://"):
                        proxies_list.append(f"http://{proxy}")
                    else:
                        proxies_list.append(proxy)
        if not proxies_list:
            print(f"[-] هیچ پروکسی در فایل '{filename}' یافت نشد یا همه خطوط کامنت شده بودند.")
        else:
            print(f"[+] تعداد {len(proxies_list)} پروکسی از فایل '{filename}' خوانده شد.")
        return proxies_list
    except FileNotFoundError:
        print(f"[!] فایل پروکسی '{filename}' یافت نشد.")
        return []
    except Exception as e:
        print(f"[!] خطا در خواندن فایل پروکسی: {e}")
        return []

def test_proxy(proxy_url):
    """یک پروکسی را برای دسترسی به اهداف HTTP و HTTPS تست می‌کند."""
    print(f"\n--- تست پروکسی: {proxy_url} ---")
    
    proxies_dict = {
        "http": proxy_url,
        "https": proxy_url, # برای درخواست‌های HTTPS، requests از تونل CONNECT استفاده می‌کند
    }
    
    # تست با هدف HTTP
    print(f"  [1] تست مقصد HTTP: {TARGET_URL_HTTP}")
    try:
        start_time = time.time()
        response_http = requests.get(TARGET_URL_HTTP, proxies=proxies_dict, timeout=REQUEST_TIMEOUT)
        duration = time.time() - start_time
        print(f"    [+] وضعیت: {response_http.status_code} (زمان: {duration:.2f} ثانیه)")
        try:
            # اگر پاسخ JSON باشد و کلید 'origin' را داشته باشد (که httpbin.org/ip دارد)
            print(f"    [+] IP گزارش شده توسط پروکسی (HTTP): {response_http.json().get('origin', 'N/A')}")
        except requests.exceptions.JSONDecodeError:
            print(f"    [-] پاسخ HTTP، JSON معتبر نبود. محتوا (تا ۱۰۰ کاراکتر): {response_http.text[:100]}")

    except requests.exceptions.ProxyError as e:
        print(f"    [!] خطای پروکسی (HTTP): {e}")
        print(f"        ممکن است این پروکسی با دستور CONNECT (برای HTTPS) مشکل داشته باشد یا نوع آن HTTP نباشد.")
        print(f"        اگر پیام خطا حاوی '400 Bad Request' یا مشابه آن است، مشکل از خود پروکسی است.")
    except requests.exceptions.ConnectTimeout:
        print(f"    [!] خطای Timeout در اتصال (HTTP)")
    except requests.exceptions.ReadTimeout:
        print(f"    [!] خطای Timeout در خواندن پاسخ (HTTP)")
    except requests.exceptions.RequestException as e:
        print(f"    [!] خطای دیگر در درخواست (HTTP): {e}")

    print(f"  ----------------------------------")

    # تست با هدف HTTPS
    print(f"  [2] تست مقصد HTTPS: {TARGET_URL_HTTPS}")
    try:
        start_time = time.time()
        response_https = requests.get(TARGET_URL_HTTPS, proxies=proxies_dict, timeout=REQUEST_TIMEOUT, verify=True)
        duration = time.time() - start_time
        print(f"    [+] وضعیت: {response_https.status_code} (زمان: {duration:.2f} ثانیه)")
        try:
            print(f"    [+] IP گزارش شده توسط پروکسی (HTTPS): {response_https.json().get('origin', 'N/A')}")
        except requests.exceptions.JSONDecodeError:
            print(f"    [-] پاسخ HTTPS، JSON معتبر نبود. محتوا (تا ۱۰۰ کاراکتر): {response_https.text[:100]}")

    except requests.exceptions.ProxyError as e:
        print(f"    [!] خطای پروکسی (HTTPS): {e}")
        print(f"        این خطا معمولاً نشان می‌دهد پروکسی در ایجاد تونل امن HTTPS (دستور CONNECT) مشکل دارد.")
        print(f"        اگر پیام خطا حاوی 'Cannot connect to proxy.' و سپس '400 Bad Request' یا مشابه آن است،")
        print(f"        یعنی خود سرور پروکسی درخواست ایجاد تونل را رد کرده است.")
    except requests.exceptions.ConnectTimeout:
        print(f"    [!] خطای Timeout در اتصال (HTTPS)")
    except requests.exceptions.ReadTimeout:
        print(f"    [!] خطای Timeout در خواندن پاسخ (HTTPS)")
    except requests.exceptions.SSLError as e:
        print(f"    [!] خطای SSL (HTTPS): {e}")
        print(f"        این ممکن است به دلیل مشکل در گواهی SSL پروکسی یا نحوه مدیریت تونل امن باشد.")
    except requests.exceptions.RequestException as e:
        print(f"    [!] خطای دیگر در درخواست (HTTPS): {e}")


if __name__ == "__main__":
    proxies_to_test = load_proxies()
    
    if proxies_to_test:
        print(f"\n[***] شروع تست {len(proxies_to_test)} پروکسی [***]\n")
        for i, proxy in enumerate(proxies_to_test):
            print(f"پروکسی شماره {i+1}/{len(proxies_to_test)}")
            test_proxy(proxy)
            if i < len(proxies_to_test) - 1:
                print("\n=========================================\n") # جداکننده بین تست پروکسی‌ها
        print("\n[***] پایان تست همه پروکسی‌ها [***]")
    else:
        print("[-] هیچ پروکسی برای تست وجود ندارد.")
