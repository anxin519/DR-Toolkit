# -*- coding: utf-8 -*-
"""日志管理模块"""
import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

class Logger:
    """日志管理器"""
    
    _loggers = {}
    
    @staticmethod
    def get_logger(name, log_dir="logs"):
        """获取日志记录器"""
        if name in Logger._loggers:
            return Logger._loggers[name]
        
        # 创建日志目录
        os.makedirs(log_dir, exist_ok=True)
        
        # 创建logger
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)
        
        # 避免重复添加handler
        if logger.handlers:
            return logger
        
        # 文件handler - 按日期命名
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = os.path.join(log_dir, f"{name}_{today}.log")
        
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        
        # 控制台handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 格式化
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        Logger._loggers[name] = logger
        return logger
