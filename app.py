import streamlit as st
import time
import os
import json
import subprocess
import sys

STATUS_FILE = "aternos_status.json"
BOT_FILE = "aternos_bot.py"

def load_status():
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {"status": "starting", "detail": "", "online_elapsed": 0, "current_state": ""}

def is_bot_running():
    if not os.path.exists("aternos_bot.pid"):
        return False
    try:
        with open("aternos_bot.pid", "r") as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except:
        return False

def start_bot():
    proc = subprocess.Popen(
        [sys.executable, BOT_FILE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    with open("aternos_bot.pid", "w") as f:
        f.write(str(proc.pid))
    print(f"[MAIN] Bot started with PID {proc.pid}")

BOT_CODE = '''
import json
import time
import os
import re
import subprocess
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

COOKIE_FILE = "cookies.json"
SERVER_NAME = "meracraft-ox3w"
RESTART_INTERVAL = 30 * 60
STATUS_FILE = "aternos_status.json"

def save_status(status="", detail="", online_elapsed=0, current_state=""):
    with open(STATUS_FILE, "w") as f:
        json.dump({
            "status": status,
            "detail": detail,
            "online_elapsed": int(online_elapsed),
            "current_state": current_state
        }, f)
        f.flush()
        os.fsync(f.fileno())
    print(f"[BOT] status={status} | current_state={current_state} | detail={detail}")

def get_chrome_version():
    cmds = [
        ["google-chrome", "--version"],
        ["google-chrome-stable", "--version"],
        ["chromium-browser", "--version"],
        ["chromium", "--version"],
        ["/usr/bin/google-chrome", "--version"],
        ["/usr/bin/chromium-browser", "--version"],
    ]
    for cmd in cmds:
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode()
            match = re.search(r"(\\d+)\\.\\d+\\.\\d+\\.\\d+", out)
            if match:
                version = int(match.group(1))
                print(f"[BOT] Detected Chrome version: {version}")
                return version
        except:
            continue
    return None

def run_relentless_headless_bot():
    save_status(status="detecting_chrome", current_state="Detecting Chrome version...")

    chrome_version = get_chrome_version()
    save_status(status="installing_driver", current_state="Installing ChromeDriver...")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.page_load_strategy = "eager"

    try:
        if chrome_version:
            driver_path = ChromeDriverManager(driver_version=str(chrome_version)).install()
        else:
            driver_path = ChromeDriverManager().install()
        service = Service(driver_path)
        driver = webdriver.Chrome(service=service, options=options)
    except Exception as e:
        save_status(status="driver_error", detail=str(e)[:80], current_state="Driver install failed")
        return

    online_start_time = None

    try:
        save_status(status="loading_page", current_state="Loading Aternos...")
        driver.get("https://aternos.org/servers/")

        if os.path.exists(COOKIE_FILE):
            with open(COOKIE_FILE, "r") as f:
                cookies = json.load(f)
                for cookie in cookies:
                    clean_cookie = {k: v for k, v in cookie.items() if k not in ["sameSite", "size"]}
                    try:
                        driver.add_cookie(clean_cookie)
                    except:
                        pass

        driver.refresh()
        save_status(status="monitoring", current_state="Monitoring Aternos...")

        while True:
            try:
                if "/servers/" in driver.current_url:
                    server_cards = driver.find_elements(By.XPATH,
                        f"//*[contains(@class, \'server-name\') and contains(text(), \'{SERVER_NAME}\')]")
                    if server_cards:
                        driver.execute_script("arguments[0].click();", server_cards[0])
                        time.sleep(1)

                status_elements = driver.find_elements(By.CLASS_NAME, "statuslabel-label")
                status = status_elements[0].text.strip() if status_elements else ""

                confirms = driver.find_elements(By.CSS_SELECTOR, ".btn-success, #start")
                for btn in confirms:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].click();", btn)
                        btn_text = btn.text.strip() or "Start/Confirm"
                        save_status(status="clicked_button", detail=f"Clicked: {btn_text}", current_state=f"Clicked: {btn_text}")
                        online_start_time = None

                if status == "Online":
                    if online_start_time is None:
                        online_start_time = time.time()

                    elapsed = time.time() - online_start_time
                    remaining = max(0, RESTART_INTERVAL - elapsed)

                    if elapsed >= RESTART_INTERVAL:
                        restart_btn = driver.find_elements(By.ID, "restart")
                        if restart_btn and restart_btn[0].is_displayed():
                            driver.execute_script("arguments[0].click();", restart_btn[0])
                            save_status(status="restarting", current_state="Restarting — 30 min reached")
                            online_start_time = None
                    else:
                        save_status(
                            status="Online",
                            detail=f"Restart in {int(remaining//60)}m {int(remaining%60)}s",
                            online_elapsed=int(elapsed),
                            current_state="Online"
                        )
                else:
                    online_start_time = None

                    display_status = status
                    if "Waiting in queue" in status:
                        q_pos = driver.find_elements(By.CLASS_NAME, "queue-position")
                        q_time = driver.find_elements(By.CLASS_NAME, "queue-time")
                        pos_text = q_pos[0].text.strip() if q_pos else "..."
                        time_text = q_time[0].text.strip() if q_time else "..."
                        display_status = f"Waiting in queue [{pos_text}] ({time_text})"

                    if display_status:
                        save_status(status=display_status, current_state=display_status)

            except Exception as e:
                pass

            time.sleep(1)

    except Exception as e:
        save_status(status="crashed", detail=str(e)[:80], current_state="Crashed")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_relentless_headless_bot()
'''

with open(BOT_FILE, "w") as f:
    f.write(BOT_CODE)

status = load_status()
if any(x in status.get("status", "") for x in ["crashed", "driver_error"]):
    if os.path.exists("aternos_bot.pid"):
        os.remove("aternos_bot.pid")

if not is_bot_running():
    start_bot()

# --- UI ---
st.set_page_config(page_title="Aternos Bot Dashboard", page_icon="⚡", layout="centered")
st.title("⚡ Aternos Bot Dashboard")
st.caption("Refreshes every 3 seconds.")

status = load_status()
phase = status.get("status", "starting")
detail = status.get("detail", "")
online_elapsed = status.get("online_elapsed", 0)
current_state = status.get("current_state", "")

st.caption(f"🔧 Raw status: `{phase}` | bot process: `{is_bot_running()}`")

# --- Current State Banner (always visible) ---
if current_state:
    st.info(f"📡 Current State: **{current_state}**")

st.divider()

if phase == "Online":
    elapsed_min = online_elapsed // 60
    elapsed_sec = online_elapsed % 60
    st.success(f"🟢 Server is **Online**")
    st.info(f"⏱️ Online for: **{elapsed_min}m {elapsed_sec}s** &nbsp;|&nbsp; {detail}")
elif phase == "restarting":
    st.warning("🔄 **Restarting server...** 30 minutes reached.")
elif phase == "clicked_button":
    st.success(f"✅ **{detail}**")
elif "queue" in phase.lower():
    st.warning(f"🕐 **{phase}**")
elif phase in ["Loading", "Preparing", "Starting"]:
    st.info(f"⏳ Server is **{phase}**...")
elif phase == "Offline":
    st.error("🔴 Server is **Offline** — attempting to start...")
elif phase == "monitoring":
    st.info("👀 Monitoring Aternos...")
elif phase == "loading_page":
    st.info("🌐 Loading Aternos page...")
elif phase == "detecting_chrome":
    st.info("🔍 Detecting Chrome version...")
elif phase == "installing_driver":
    st.info("📦 Installing matching ChromeDriver...")
elif phase == "driver_error":
    st.error(f"❌ ChromeDriver error: {detail}")
elif phase == "crashed":
    st.error(f"💀 Bot crashed: {detail}")
elif phase == "starting":
    st.info("🚀 Bot starting up...")
else:
    st.info(f"🤖 {phase} {detail}")

st.divider()
st.subheader("📋 Server Info")
col1, col2 = st.columns(2)
col1.metric("Server", "meracraft-ox3w")
col2.metric("Restart Interval", "30 minutes")

time.sleep(3)
st.rerun()
