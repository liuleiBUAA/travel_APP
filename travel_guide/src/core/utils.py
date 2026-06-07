"""共享工具函数"""

import json
import os

REGIONS = ["Europe", "North_America", "Oceania", "Asia"]


def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def load_config(base_dir):
    """加载 config.json，不存在则返回默认值"""
    defaults = {
        "same_day_max_hours": 4.0,
        "check_low_freq_flights": False,
        "options_display_mode": "detailed",
        "force_gateway_departure": False,
        "transport_preference": "train",
    }
    cfg_path = os.path.join(base_dir, "config/config.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            user_cfg = json.load(f)
        defaults.update(user_cfg)
    return defaults
