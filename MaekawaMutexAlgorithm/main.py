import time
from maekawaMutex import MaekawaMutex
from threading import Thread
import config

def run_algorithm():
    maekawa_mutex = MaekawaMutex()
    maekawa_mutex.run()

mutex_thread = Thread(target=run_algorithm)
mutex_thread.start()

#time.sleep(config.exec_time)
mutex_thread.join()
print("Done")


