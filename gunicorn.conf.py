import multiprocessing
import os

bind = "0.0.0.0:10000"

IS_FREE_PLAN = os.environ.get("RENDER_PLAN", "free") == "free"

workers = 2 if IS_FREE_PLAN else max(2, (2 * multiprocessing.cpu_count()) + 1)
threads = 2 if IS_FREE_PLAN else 4
worker_class = "gthread"

timeout = 120
keepalive = 5
max_requests = 300
max_requests_jitter = 50
preload_app = True

worker_tmp_dir = None