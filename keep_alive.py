"""
Keep-alive script to prevent bot from sleeping on free hosting
"""
import threading
import time
import requests
import os
from urllib.parse import urlparse

def keep_alive():
    """Send periodic requests to keep the server alive"""
    # Get the current domain from environment or use default
    base_url = os.environ.get('REPLIT_DOMAINS', 'localhost:5000').split(',')[0]
    if not base_url.startswith('http'):
        base_url = f'https://{base_url}'
    
    while True:
        try:
            # Send a ping every 5 minutes
            response = requests.get(f'{base_url}/')
            print(f"Keep-alive ping: {response.status_code}")
        except Exception as e:
            print(f"Keep-alive error: {e}")
        
        # Wait 5 minutes before next ping
        time.sleep(300)

def start_keep_alive():
    """Start the keep-alive thread"""
    thread = threading.Thread(target=keep_alive, daemon=True)
    thread.start()
    print("Keep-alive service started")

if __name__ == "__main__":
    start_keep_alive()
    # Keep the main thread alive
    while True:
        time.sleep(60)