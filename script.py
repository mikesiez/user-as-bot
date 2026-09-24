import json
import os
import time
import requests
from collections import deque
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import undetected_chromedriver as uc
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote

# HEADLESS SERVER DEPENDENCY
from pyvirtualdisplay import Display

from dotenv import load_dotenv
load_dotenv()

def getgame(name):
    domain = os.getenv("domain")
    cookie = os.getenv("cookie")
    referer = os.getenv("referer")

    link = f"{domain}/{quote(name)}"
    print(f"getting {link}")

    try:
        headers = {
            "Cookie": cookie,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer,
        }

        res = requests.get(link, headers=headers, timeout=10)

        html = res.text

        soup = BeautifulSoup(html, "html.parser")

        links = None

        for div in soup.find_all("div"):
            if div.get_text(strip=True) == "Gofile":
                data = div.get("data-links")

                if data:
                    links = json.loads(data)
                    break

        msg = ""

        for link in links:
            msg += f"[{link['file_name']}]({link['direct_link']})\n"

        return msg;

    except Exception as e:
        return f"something went wrong: {e}.\n> Hint: If type error then doesnt exist or you mispelled"
    One

def prompt(msg,username):

    # model = "qwen3:8b"
    model = "clyde" #custom client-side model
    # personality = "You are jarvis. System built by tony stark. Robotic, serious, but humourstic when appropriate. You work for tony stark, the stark industries aka iron man. Reply to people as if you are talking to them, not in the third person."
    endpoint = "http://localhost:11434/api/chat" #can use /chat if want to make context or more system related hints to the ai

    payload = {
        "model": model,
        "stream": False,
        "think":False,
        "messages": [
            # {
            #     "role": "system",
            #     "content": personality
            # },
            {
                "role": "user",
                "content": f"{username} says: {msg}"
            }
        ]
    }

    print(f"prompted from {username} with {msg}")
    try:
        response = requests.post(
            endpoint,
            headers={"Content-Type": "application/json"},
            json=payload
        )
    except Exception as e:
        print(f"err: {e}")
        return f"err: {e}"
    data = response.json()

    #thought_time = data["total_duration"]
    answer = data["message"]["content"]

    if len(answer) > 2000:  # max Discord character limit
        answer = f"{answer[:2000 - 3]}..."

    return answer

def send_message(driver, text):
    """Finds Discord's message input box, types the text, and sends Enter."""
    try:
        wait = WebDriverWait(driver, 10)

        # Discord's actual message composer
        input_box = wait.until(
            EC.element_to_be_clickable(
                (By.CSS_SELECTOR, 'div[role="textbox"][data-slate-editor="true"][contenteditable="true"]')
            )
        )

        input_box.click()
        time.sleep(0.2)

        # Type text while preserving newlines as Discord line breaks
        parts = text.split("\n")

        for i, part in enumerate(parts):
            input_box.send_keys(part)

            if i < len(parts) - 1:
                input_box.send_keys(Keys.SHIFT, Keys.ENTER)

        time.sleep(1)

        input_box.send_keys(Keys.ENTER)
        input_box.send_keys(Keys.ENTER)

        print(f"[REPLIED] Sent: {text}")

    except Exception as e:
        print(f"Failed to send message: {e}")

def watch_messages(driver, max_history=25):
    wait = WebDriverWait(driver, 15)
    container = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'ol[data-list-id="chat-messages"]'))
    )

    # Fixed-size buffer for the last N messages
    message_buffer = deque(maxlen=max_history)

    SEEN_IDS_FILE = "seen_message_ids.json"
    # Load previously seen message IDs
    try:
        with open(SEEN_IDS_FILE, "r") as f:
            seen_message_ids = set(json.load(f))
        print(f"Loaded {len(seen_message_ids)} previously seen message IDs.")
    except FileNotFoundError:
        seen_message_ids = set()
        print("No previous message ID file found. Starting fresh.")

    last_known_username = "Unknown/System"

    MY_BOT_USERNAME = os.getenv("username")

    print(f"--- Started watching chat (keeping last {max_history} messages) ---")

    while True:
        try:
            # Query all list items currently in DOM
            message_items = container.find_elements(By.CSS_SELECTOR, 'li[id^="chat-messages-"]')

            for item in message_items:
                try:
                    msg_id = item.get_attribute("id")
                    
                    if not msg_id or msg_id in seen_message_ids:
                        continue

                    try:
                        article = item.find_element(By.CSS_SELECTOR, 'div[role="article"]')
                    except Exception:
                        continue

                    # Extract Username
                    try:
                        username_elem = article.find_element(By.CSS_SELECTOR, 'span[class*="username_"]')
                        username = username_elem.text.strip()
                        last_known_username = username
                    except Exception:
                        username = last_known_username

                    # Extract Content
                    try:
                        content_elem = article.find_element(By.CSS_SELECTOR, 'div[id^="message-content-"]')
                        content = content_elem.text.strip()
                    except Exception:
                        content = ""

                    payload = {"id": msg_id, "username": username, "content": content}
                    message_buffer.append(payload)

                    # Mark as seen
                    seen_message_ids.add(msg_id)

                    # Save immediately
                    with open(SEEN_IDS_FILE, "w") as f:
                        json.dump(list(seen_message_ids), f)

                    print(f"[NEW] {username}: {content}")

                    # --- AUTO-REPLY LOGIC ---
                    # Ignore messages sent by yourself to avoid infinite reply loops
                    if username != MY_BOT_USERNAME and content:

                        if f"@{MY_BOT_USERNAME.lower()}" in content.lower():
                            send_message(driver,prompt(content,username))
                            # send_message(driver, prompt(content,username))
                        elif (content.lower())[:5] == "/game":
                            gameName = content[6:]
                            send_message(driver, getgame(gameName))

                        elif (content.lower())[:6] == "/image":
                            send_message(driver, f"{os.getenv("api")}{quote(content[7:])}")

                        elif "!hello" in content:
                            send_message(driver, f"Hey {username}, what's up?")

                except StaleElementReferenceException:
                    # If Discord DOM updates while iterating, skip gracefully
                    continue

            # Polling interval to reduce CPU utilization
            time.sleep(1)

        except KeyboardInterrupt:
            print("\nStopped watching messages.")
            break
        except Exception as e:
            time.sleep(1)

    return list(message_buffer)

def run_with_uc():
    # Retrieve token from environment variables
    # (Looks for DISCORD_USER_TOKEN in your system environment)
    USER_TOKEN = os.getenv("token")
    
    if not USER_TOKEN:
        raise ValueError(
            "Error: DISCORD_USER_TOKEN environment variable is not set. "
            "Please set it before running the script."
        )

    # 1. Fire up the virtual frame buffer monitor
    print("Starting Virtual Display...")
    display = Display(visible=0, size=(1920, 1080))
    display.start()

    driver = None
    try:
        options = uc.ChromeOptions()
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--headless') # Remove this if you need to debug visually
        
        driver = uc.Chrome(options=options)

        driver.get('https://discord.com/login')
        time.sleep(3)

        script = """
        (function(token) {
            var iframe = document.createElement('iframe');
            document.body.appendChild(iframe);
            iframe.contentWindow.localStorage.setItem('token', JSON.stringify(token));
            return iframe.contentWindow.localStorage.getItem('token');
        })(arguments[0]);
        """
        driver.execute_script(script, USER_TOKEN)

        gc = os.getenv("gc")
        driver.get(f"https://discord.com/channels/@me/{gc}")
        
        # Start watching live updates
        watch_messages(driver, max_history=15)

    except Exception as e:
        print(f"An execution crash occurred: {e}")
    
    finally:
        print("Cleaning up resources...")
        if driver:
            try:
                driver.quit()
            except:
                pass
        display.stop()
        print("Teardown finished.")

if __name__ == "__main__":
    run_with_uc()