import subprocess
import sys
from threading import Thread

def run_bot():
    subprocess.run([sys.executable, "main_bot.py"])

def run_streamlit():
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"])

if __name__ == "__main__":
    bot_thread = Thread(target=run_bot)
    streamlit_thread = Thread(target=run_streamlit)
    
    bot_thread.start()
    streamlit_thread.start()
    
    bot_thread.join()
    streamlit_thread.join()
