import os
import time

folder = "images"
expire_seconds = 24 * 60 * 60  # 24小时

now = time.time()

for filename in os.listdir(folder):
    file_path = os.path.join(folder, filename)
    if os.path.isfile(file_path):
        file_age = now - os.path.getmtime(file_path)
        if file_age > expire_seconds:
            os.remove(file_path)
            print(f"Deleted old file: {filename}")
