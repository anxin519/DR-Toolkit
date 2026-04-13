import time

class ProgressThrottler:
    """
    一个简单的防抖节流组件，用于限制 GUI 更新频率。
    """
    def __init__(self, callback, interval_ms=50):
        self.callback = callback
        self.interval = interval_ms / 1000.0
        self.last_run = 0
        self.last_value = None

    def update(self, value, force=False):
        """
        更新进度。如果距离上次更新时间超过间隔，则调用回调。
        """
        now = time.time()
        self.last_value = value
        if force or (now - self.last_run >= self.interval):
            self.callback(value)
            self.last_run = now

    def finalize(self, value=None):
        """
        最后一次更新，确保输出最终进度。
        """
        val = value if value is not None else self.last_value
        self.callback(val)
        self.last_run = time.time()
