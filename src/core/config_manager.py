# -*- coding: utf-8 -*-
"""配置管理模块"""
import json
import os
from datetime import datetime

class ConfigManager:
    """配置管理器"""
    
    DEFAULT_CONFIG = {
        "remote_nodes": [
            {"name": "默认PACS", "ae": "PACS_SCP", "host": "127.0.0.1", "port": 104}
        ],
        "local_scp": {
            "ae": "DICOM_TOOL",
            "port": 11112,
            "storage_path": "./storage"
        },
        "forward_rules": [],
        "worklist_scp": {
            "port": 11113,
            "ae": "WORKLIST_SCP"
        },
        "ui_settings": {
            "theme": "cosmo",
            "last_folder": "",
            "window_size": [1100, 750],
            "window_presets": {
                "lung": {"center": -600, "width": 1500},
                "mediastinum": {"center": 40, "width": 400},
                "bone": {"center": 400, "width": 1800},
                "soft_tissue": {"center": 50, "width": 350}
            }
        },
        "export_fields": [
            "filepath", "filename", "PatientName", "PatientID", 
            "PatientSex", "PatientAge", "PatientBirthDate",
            "StudyDate", "StudyTime", "Modality", "SeriesDescription"
        ],
        "anonymize": {
            "keep_last_digits": 4,
            "prefix": "ANON"
        },
        "uid_strategy": {
            "method": "append_timestamp",  # append_timestamp, regenerate, custom_suffix
            "custom_suffix": ""
        }
    }
    
    def __init__(self, config_file="config/app_config.json"):
        self.config_file = config_file
        self.config = self.load_config()
    
    def load_config(self):
        """加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                # 合并默认配置（处理新增字段）
                return self._merge_config(self.DEFAULT_CONFIG, config)
            except Exception as e:
                print(f"加载配置失败: {e}，使用默认配置")
                return self.DEFAULT_CONFIG.copy()
        else:
            # 首次运行，创建默认配置
            self.save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
    
    def _merge_config(self, default, loaded):
        """合并配置，保留用户配置，补充默认值"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result
    
    def save_config(self, config=None):
        """保存配置"""
        if config is None:
            config = self.config
        
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def get(self, key, default=None):
        """获取配置项"""
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def set(self, key, value):
        """设置配置项"""
        keys = key.split('.')
        config = self.config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        self.save_config()
    
    def get_remote_nodes(self):
        """获取远程节点列表"""
        return self.config.get('remote_nodes', [])
    
    def add_remote_node(self, node):
        """添加远程节点"""
        if 'remote_nodes' not in self.config:
            self.config['remote_nodes'] = []
        self.config['remote_nodes'].append(node)
        self.save_config()
    
    def update_remote_node(self, index, node):
        """更新远程节点"""
        if 0 <= index < len(self.config['remote_nodes']):
            self.config['remote_nodes'][index] = node
            self.save_config()
    
    def delete_remote_node(self, index):
        """删除远程节点"""
        if 0 <= index < len(self.config['remote_nodes']):
            del self.config['remote_nodes'][index]
            self.save_config()
