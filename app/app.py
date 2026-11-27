import os

# URLL = os.getenv("URLL")
URLL = "allo"

def notify():
    print("Sending alert...")
    if URLL:
        # Here you would add the code to send a notification to the webhook
        print(f"Alert sent to {URLL}")
    else:
        print("No webhook URL configured.")