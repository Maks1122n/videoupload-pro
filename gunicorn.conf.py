import os

# Gunicorn configuration
bind = "0.0.0.0:10000"
workers = 1
worker_class = "sync"
timeout = 1200  # 20 минут для больших файлов
keepalive = 5
max_requests = 50
max_requests_jitter = 5
preload_app = True
worker_tmp_dir = "/dev/shm"
worker_connections = 500
max_worker_memory = 200
graceful_timeout = 60
worker_restart_limit = 3

# Логирование
loglevel = "info"
accesslog = "-"
errorlog = "-"
capture_output = True
enable_stdio_inheritance = True

# Стабильность
preload_app = True
reuse_port = True 