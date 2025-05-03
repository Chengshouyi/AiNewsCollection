import eventlet
eventlet.monkey_patch()

bind = "0.0.0.0:8000"
worker_class = "eventlet"
workers = 4  # 根據需求調整
