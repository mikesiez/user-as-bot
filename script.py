import os
import time
from collections import deque
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException
import undetected_chromedriver as uc

from dotenv import load_dotenv
load_dotenv()

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

        input_box.send_keys(text)
        time.sleep(0.5)

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
    seen_message_ids = set()
    last_known_username = "Unknown/System"

    MY_BOT_USERNAME = "Jarvis"

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
                    seen_message_ids.add(msg_id)

                    print(f"[NEW] {username}: {content}")

                    # --- AUTO-REPLY LOGIC ---
                    # Ignore messages sent by yourself to avoid infinite reply loops
                    if username != MY_BOT_USERNAME and content:
                        content_lower = content.lower()

                        if "!ping" in content_lower:
                            send_message(driver, f"Pong! @{username}")
                        elif "!hello" in content_lower:
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

    options = uc.ChromeOptions()
    options.add_argument('--disable-gpu')
    options.add_argument('--headless') # Remove this if you need to debug visually
    
    driver = uc.Chrome(options=options)
    
    try:
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
        recent_messages = watch_messages(driver, max_history=15)
    
    finally:
        driver.quit()

if __name__ == "__main__":
    run_with_uc()