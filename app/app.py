import os

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
def notify():
    print("Sending alert...")
    if WEBHOOK_URL:
        # Here you would add the code to send a notification to the webhook
        print(f"Alert sent to {WEBHOOK_URL}")
    else:
        print("No webhook URL configured.")