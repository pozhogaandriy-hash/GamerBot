"""
Запуск API та бота разом

Термінал 1:
    python app.py

Термінал 2:
    python main.py
"""

import subprocess
import sys
import time

def run_bot():
    return subprocess.Popen([sys.executable, "main.py"])

def run_api():
    return subprocess.Popen([sys.executable, "app.py"])

if __name__ == "__main__":
    print("🚀 Starting Discord Bot...")
    bot_process = run_bot()
    
    time.sleep(2)
    
    print("🚀 Starting API Server...")
    api_process = run_api()
    
    print("✅ Both services running on:")
    print("   - API: http://localhost:5000")
    print("   - Bot: Discord")
    print("\nPress Ctrl+C to stop")
    
    try:
        bot_process.wait()
        api_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        bot_process.terminate()
        api_process.terminate()