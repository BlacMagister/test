import asyncio
import csv
import logging
import os
import time
from datetime import datetime

import zendriver as zd
from colorama import Fore, Style, init

# Konfigurasi awal
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
proxy_extension_path = os.path.join(BASE_DIR, "extensions")

init(autoreset=True)

DELAY_TIME = 5
CSV_FILE = "user.csv"
PROXY_FILE = "proxy.txt"
MAX_RETRIES = 3


def log_message(index, total, message, status="info"):
    """Fungsi untuk mencetak log dengan warna berdasarkan status."""
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    color = {
        "success": Fore.GREEN,
        "error": Fore.RED,
        "warning": Fore.YELLOW,
        "process": Fore.CYAN,
        "info": Fore.WHITE
    }.get(status, Fore.WHITE)

    log = f"[{now}] [{index}/{total}] {color}{message}{Style.RESET_ALL}"
    print(log)
    logging.info(log)


def read_csv(file_path):
    """Membaca file CSV dan mengembalikan daftar user."""
    if not os.path.exists(file_path):
        return []
    with open(file_path, mode="r", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)


def write_csv(file_path, users):
    """Menulis ulang file CSV setelah akun berhasil diproses."""
    if users:
        with open(file_path, mode="w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=users[0].keys())
            writer.writeheader()
            writer.writerows(users)
    else:
        os.remove(file_path)


def save_proxy(proxy):
    """Menyimpan proxy yang berhasil diambil."""
    with open(PROXY_FILE, "a") as file:
        file.write(proxy + "\n")


async def check_ip(browser, index, total_users):
    """Mengecek IP yang sedang digunakan."""
    ip_tab = await browser.get("https://api64.ipify.org?format=text")
    await ip_tab.sleep(5)

    ip = await ip_tab.evaluate('document.body.innerText.trim()')

    if ip:
        log_message(index, total_users, f"IP Using: {ip}", "success")
        return ip.strip()
    else:
        log_message(index, total_users, "Failed get IP", "error")
        return None


async def process_user(email, password, index, total_users, attempt=1):
    """Proses registrasi WebShare dengan akun Gmail GSuite."""
    cfg = zd.Config()
    cfg._default_browser_args = [
        "--headless=new",
        "--no-first-run",
        "--remote-allow-origins=*",
        "--disable-infobars",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-dev-shm-usage",
        "--disable-session-crashed-bubble",
    ]

    try:
        browser = await zd.start(config=cfg)
        log_message(index, total_users, f"Processing register WebShare (Attempt {attempt}/{MAX_RETRIES})", "process")
        time.sleep(5)
        ip = await check_ip(browser, index, total_users)

        tab = await browser.get("https://dashboard.webshare.io/register?source=home_hero_button_register")
        await tab.sleep(DELAY_TIME)

        create_account = await tab.find("Sign Up With Google", best_match=True, timeout=10)
        await create_account.click()
        log_message(index, total_users, "Clicked 'Sign Up with Google'", "success")
        await tab.sleep(DELAY_TIME)

        # Beralih ke tab login Google
        tabs = browser.tabs
        google_tab = tabs[-1]
        await google_tab.activate()

        email_input = await google_tab.select("input[type=email]", timeout=10)
        await email_input.send_keys(email)
        log_message(index, total_users, "Entered email", "success")
        await google_tab.sleep(DELAY_TIME)

        next_button = await google_tab.find("Next", best_match=True, timeout=10)
        await next_button.click()
        log_message(index, total_users, "Clicked Next after email", "success")
        await google_tab.sleep(DELAY_TIME)

        password_input = await google_tab.select("input[type=password]", timeout=10)
        await password_input.send_keys(password)
        log_message(index, total_users, "Entered password", "success")
        await google_tab.sleep(DELAY_TIME)

        next_button = await google_tab.find("Next", best_match=True, timeout=10)
        await next_button.click()
        log_message(index, total_users, "Logged in successfully", "success")
        await google_tab.sleep(DELAY_TIME)

        # Menangani halaman konfirmasi jika muncul
        try:
            saya_mengerti = await google_tab.find("#confirm", best_match=True, timeout=10)
            if saya_mengerti:
                await saya_mengerti.click()
                log_message(index, total_users, "Confirmed agreement", "success")
                await google_tab.sleep(DELAY_TIME)
        except Exception:
            log_message(index, total_users, "No confirmation needed", "warning")

        # Mencoba mencari tombol "Continue"
        try:
            setuju_button = await google_tab.find("Continue", best_match=True, timeout=10)
            await setuju_button.click()
            log_message(index, total_users, "Clicked Continue button", "success")
            await google_tab.sleep(DELAY_TIME)
        except Exception:
            log_message(index, total_users, "No Continue button found, proceeding", "warning")

        # Kembali ke tab utama
        main_tab = tabs[0]
        await main_tab.activate()
        log_message(index, total_users, "Back to WebShare dashboard", "success")

        await main_tab.sleep(DELAY_TIME)
        await main_tab.get("https://dashboard.webshare.io/proxy/list")

        await main_tab.sleep(DELAY_TIME)

        proxy_text = await main_tab.evaluate(
            'document.querySelector("#simple-tabpanel-0 pre code span span:nth-child(3)")?.textContent.trim()'
        )

        if proxy_text:
            proxy_text = proxy_text.replace('"', '')
            log_message(index, total_users, f"Proxy retrieved: {proxy_text}", "success")
            save_proxy(proxy_text)
            await browser.stop()
            return True
        else:
            log_message(index, total_users, "Failed to get proxy", "error")
            await browser.stop()
            return False

    except Exception as e:
        log_message(index, total_users, f"ERROR: {str(e)}", "error")
        await browser.stop()
        return False


async def main():
    """Fungsi utama untuk memproses daftar akun."""
    users = read_csv(CSV_FILE)
    if not users:
        print(Fore.RED + "No user found in user.csv" + Style.RESET_ALL)
        return

    total_users = len(users)

    for i, user in enumerate(users.copy(), start=1):
        email = user.get("Email") or user.get("Email Address [Required]", "").strip()
        password = user.get("Password") or user.get("Password [Required]", "").strip()

        if not email or not password:
            log_message(i, total_users, "Invalid user data", "warning")
            continue

        for attempt in range(1, MAX_RETRIES + 1):
            success = await process_user(email, password, i, total_users, attempt)

            if success:
                users.remove(user)
                write_csv(CSV_FILE, users)
                break
            else:
                log_message(i, total_users, f"Retry {attempt}/{MAX_RETRIES}", "warning")
                await asyncio.sleep(5)

    print(Fore.MAGENTA + "\n[*] Done processing all accounts!" + Style.RESET_ALL)


if __name__ == "__main__":
    asyncio.run(main())
