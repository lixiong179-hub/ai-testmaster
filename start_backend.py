import subprocess
import time
import os

# Change to project directory
os.chdir(r"c:\Users\Administrator\Desktop\ai-testmaster(2)\ai-testmaster")

# Start backend
print("Starting backend server...")
subprocess.Popen(
    ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
    creationflags=subprocess.CREATE_NEW_CONSOLE
)
print("Backend server started. Waiting 5 seconds...")
time.sleep(5)
print("Done!")
