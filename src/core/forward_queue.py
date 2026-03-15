# -*- coding: utf-8 -*-
"""转发队列管理"""
import json
import os
import threading
import time
from datetime import datetime, timedelta

try:
    from core.logger import Logger
except ImportError:
    from src.core.logger import Logger

class ForwardQueue:
    """转发队列管理器"""
    
    def __init__(self, queue_file="config/forward_queue.json"):
        self.queue_file = queue_file
        self.queue = []
        self.lock = threading.Lock()
        self.logger = Logger.get_logger('forward')
        self.running = False
        self.thread = None
        self.load_queue()
    
    def load_queue(self):
        """加载队列"""
        if os.path.exists(self.queue_file):
            try:
                with open(self.queue_file, 'r', encoding='utf-8') as f:
                    self.queue = json.load(f)
            except:
                self.queue = []
    
    def save_queue(self):
        """保存队列"""
        os.makedirs(os.path.dirname(self.queue_file), exist_ok=True)
        with open(self.queue_file, 'w', encoding='utf-8') as f:
            json.dump(self.queue, f, indent=2, ensure_ascii=False)
    
    def add_task(self, filepath, target_node, source_ae=""):
        """添加转发任务"""
        with self.lock:
            task = {
                "id": f"{int(time.time() * 1000)}",
                "filepath": filepath,
                "target_node": target_node,
                "source_ae": source_ae,
                "status": "pending",  # pending, success, failed
                "retry_count": 0,
                "max_retries": 3,
                "created_at": datetime.now().isoformat(),
                "next_retry_at": None,
                "error": None
            }
            self.queue.append(task)
            self.save_queue()
            self.logger.info(f"添加转发任务: {filepath} -> {target_node['name']}")
    
    def mark_success(self, task_id):
        """标记任务成功"""
        with self.lock:
            for task in self.queue:
                if task['id'] == task_id:
                    task['status'] = 'success'
                    self.logger.info(f"转发成功: {task['filepath']} -> {task['target_node']['name']}")
                    break
            self.save_queue()
    
    def mark_failed(self, task_id, error):
        """标记任务失败"""
        with self.lock:
            for task in self.queue:
                if task['id'] == task_id:
                    task['retry_count'] += 1
                    task['error'] = str(error)
                    
                    if task['retry_count'] >= task['max_retries']:
                        task['status'] = 'failed'
                        self.logger.error(f"转发失败（已达最大重试次数）: {task['filepath']} -> {task['target_node']['name']}, 错误: {error}")
                    else:
                        # 5分钟后重试
                        task['next_retry_at'] = (datetime.now() + timedelta(minutes=5)).isoformat()
                        self.logger.warning(f"转发失败（将重试）: {task['filepath']} -> {task['target_node']['name']}, 错误: {error}")
                    break
            self.save_queue()
    
    def get_pending_tasks(self):
        """获取待处理任务"""
        with self.lock:
            now = datetime.now()
            tasks = []
            for task in self.queue:
                if task['status'] == 'pending':
                    # 检查是否到重试时间
                    if task['next_retry_at']:
                        retry_time = datetime.fromisoformat(task['next_retry_at'])
                        if now >= retry_time:
                            tasks.append(task)
                    else:
                        tasks.append(task)
            return tasks
    
    def get_failed_tasks(self):
        """获取失败任务"""
        with self.lock:
            return [t for t in self.queue if t['status'] == 'failed']
    
    def retry_task(self, task_id):
        """手动重试任务"""
        with self.lock:
            for task in self.queue:
                if task['id'] == task_id and task['status'] == 'failed':
                    task['status'] = 'pending'
                    task['retry_count'] = 0
                    task['next_retry_at'] = None
                    task['error'] = None
                    self.logger.info(f"手动重试任务: {task['filepath']}")
                    break
            self.save_queue()
    
    def clear_completed(self):
        """清除已完成任务"""
        with self.lock:
            self.queue = [t for t in self.queue if t['status'] != 'success']
            self.save_queue()
    
    def start_worker(self, forward_callback):
        """启动后台工作线程"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._worker, args=(forward_callback,), daemon=True)
        self.thread.start()
        self.logger.info("转发队列工作线程已启动")
    
    def stop_worker(self):
        """停止后台工作线程"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("转发队列工作线程已停止")
    
    def _worker(self, forward_callback):
        """后台工作线程"""
        while self.running:
            try:
                tasks = self.get_pending_tasks()
                for task in tasks:
                    if not self.running:
                        break
                    
                    try:
                        # 调用转发回调
                        success = forward_callback(task['filepath'], task['target_node'])
                        if success:
                            self.mark_success(task['id'])
                        else:
                            self.mark_failed(task['id'], "转发失败")
                    except Exception as e:
                        self.mark_failed(task['id'], str(e))
                
                # 每30秒检查一次
                time.sleep(30)
            except Exception as e:
                self.logger.error(f"转发队列工作线程错误: {e}")
                time.sleep(30)
