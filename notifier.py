# ------------------ notifier.py ------------------
import requests
import config  # Imports credentials from your config.py

def send_notification(message: str):
    """
    Sends a message to all configured notification services.
    """
    print("--- Sending Notifications ---")
    _send_to_telegram(message)
    _send_to_discord(message)
    print("--- Notifications Sent ---")

def _send_to_telegram(message: str):
    """Sends a message to a Telegram chat."""
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID

    if not token or not chat_id or "YOUR_" in token:
        print("Telegram credentials not set in config.py. Skipping.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    params = {"chat_id": chat_id, "text": message}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes
        print("✅ Telegram message sent successfully!")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to send Telegram message: {e}")

def _send_to_discord(message: str):
    """Sends a message to a Discord channel using a Bot token and Channel ID."""
    token = config.DISCORD_BOT_TOKEN
    channel_id = config.DISCORD_CHANNEL_ID

    if not token or not channel_id or "YOUR_" in token:
        print("Discord bot token or channel ID not set in config.py. Skipping.")
        return

    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    payload = {"content": message}

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ Discord message sent successfully (via bot)!")
    except requests.exceptions.RequestException as e:
        # Print HTTP status code and response text if available for easier debugging
        status = getattr(e.response, "status_code", None)
        text = getattr(e.response, "text", None)
        print(f"❌ Failed to send Discord message: {e} (status={status})")
        if text:
            print("Response body:", text)
