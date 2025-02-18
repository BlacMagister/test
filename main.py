import asyncio
import csv
import logging
import os
import time
from datetime import datetime

import zendriver as zd
from colorama import Fore, Style, init

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
proxy_extension_path = os.path.join(BASE_DIR, "extensions")

init(autoreset=True)

DELAY_TIME = 5
CSV_FILE = "user.csv"
PROXY_FILE = "proxy.txt"
MAX_RETRIES = 3


def log_message(index, total, message, status="info"):
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
    if not os.path.exists(file_path):
        return []
    with open(file_path, mode="r", newline="") as file:
        reader = csv.DictReader(file)
        return list(reader)


def write_csv(file_path, users):
    if users:
        with open(file_path, mode="w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=users[0].keys())
            writer.writeheader()
            writer.writerows(users)
    else:
        os.remove(file_path)


def save_proxy(proxy):
    with open(PROXY_FILE, "a") as file:
        file.write(proxy + "\n")


async def check_ip(browser, index, total_users):
    ip_tab = await browser.get("https://api64.ipify.org?format=text")
    await ip_tab.sleep(5)

    ip = await ip_tab.evaluate('document.body.innerText.trim()')

    if ip:
        log_message(index, total_users, f"IP Using: {ip}", "success")
        return ip.strip()
    else:
        log_message(index, total_users, "Failed get ip", "error")
        return None


async def process_user(email, password, index, total_users, attempt=1):
    cfg = zd.Config()
    cfg._default_browser_args = [
        "--headless=new",
        "--no-first-run",
        "--remote-allow-origins=*",
        "--no-service-autorun",
        "--no-default-browser-check",
        "--homepage=about:blank",
        "--no-pings",
        "--password-store=basic",
        "--disable-infobars",
        "--disable-breakpad",
        "--disable-component-update",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-background-networking",
        "--disable-dev-shm-usage",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-session-crashed-bubble",
        "--disable-search-engine-choice-screen",
        # f"--load-extension={proxy_extension_path}"
    ]

    try:
        browser = await zd.start(config=cfg)
        log_message(index, total_users,
                    f"Processing register WebShare (Attempt {attempt}/{MAX_RETRIES})", "process")
        time.sleep(5)
        ip = await check_ip(browser, index, total_users)

        tab = await browser.get("https://dashboard.webshare.io/register?source=home_hero_button_register")
        await tab.sleep(DELAY_TIME)

        create_account = await tab.find("Sign Up With Google", best_match=True)
        await create_account.click()
        log_message(index, total_users,
                    "Click sign up with google done", "success")
        await tab.sleep(DELAY_TIME)

        tabs = browser.tabs
        google_tab = tabs[-1]
        await google_tab.activate()

        email_input = await google_tab.select("input[type=email]")
        await email_input.send_keys(email)
        log_message(index, total_users, "Enter email done", "success")
        await google_tab.sleep(DELAY_TIME)

        next_button = await google_tab.find("Next", best_match=True)
        await next_button.click()
        log_message(index, total_users, "Click next button done", "success")
        await google_tab.sleep(DELAY_TIME)

        password_input = await google_tab.select("input[type=password]")
        await password_input.send_keys(password)
        log_message(index, total_users, "Input password done", "success")
        await google_tab.sleep(DELAY_TIME)

        next_button = await google_tab.find("Next", best_match=True)
        await next_button.click()
        log_message(index, total_users, "Login Done", "success")
        await google_tab.sleep(DELAY_TIME)

        try:
            saya_mengerti = await google_tab.find("#confirm", best_match=True, timeout=30)
            if saya_mengerti:
                await saya_mengerti.click()
                log_message(index, total_users,
                            "Confirm click done", "success")
                await google_tab.sleep(DELAY_TIME)
        except Exception:
            log_message(
                index, total_users, "Confirm not found, go to button continue", "warning")

        setuju_button = await google_tab.find("Continue", best_match=True)
        await setuju_button.click()
        log_message(index, total_users,
                    "Click Continue button done", "success")
        await google_tab.sleep(DELAY_TIME)

        main_tab = tabs[0]
        await main_tab.activate()
        log_message(index, total_users, "Back to homepage", "success")

        await main_tab.sleep(DELAY_TIME)
        await main_tab.get("https://dashboard.webshare.io/proxy/list?authenticationMethod=%22username_password%22&connectionMethod=%22rotating%22&proxyControl=%220%22&rowsPerPage=10&page=0&order=%22asc%22&orderBy=null&searchValue=%22%22&filterByCountryOpen=false&exampleCodeOpen=true")

        await main_tab.sleep(DELAY_TIME)

        proxy_text = await main_tab.evaluate('document.querySelector("#simple-tabpanel-0 > div > pre > code > span > span:nth-child(3)")?.textContent.trim()')

        if proxy_text:
            proxy_text = proxy_text.replace('"', '')
            log_message(index, total_users,
                        f"Get proxy : {proxy_text}", "success")
            save_proxy(proxy_text)
            await browser.stop()
            return True
        else:
            log_message(index, total_users,
                        "Failed get proxy", "error")
            await browser.stop()
            return False

    except Exception as e:
        log_message(index, total_users, f"ERROR: {str(e)}", "error")
        await browser.stop()
        return False


async def main():
    users = read_csv(CSV_FILE)
    if not users:
        print(Fore.RED + "No user found in user.csv" + Style.RESET_ALL)
        return

    total_users = len(users)

    for i, user in enumerate(users.copy(), start=1):
        email = user.get("Email") or user.get(
            "Email Address [Required]", "").strip()
        password = user.get("Password") or user.get(
            "Password [Required]", "").strip()

        if not email or not password:
            log_message(i, total_users,
                        " Error bang", "warning")
            continue

        for attempt in range(1, MAX_RETRIES + 1):
            success = await process_user(email, password, i, total_users, attempt)

            if success:
                users.remove(user)
                write_csv(CSV_FILE, users)
                break
            else:
                log_message(i, total_users,
                            f"Retry {attempt}/{MAX_RETRIES}", "warning")
                await asyncio.sleep(5)

    print(Fore.MAGENTA + "\n[*] Done all account!" + Style.RESET_ALL)

if __name__ == "__main__":
    asyncio.run(main())
