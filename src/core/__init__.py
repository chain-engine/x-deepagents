#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Core 模块
提供配置管理和日志功能
"""

from .config import settings, Settings
from .logger import logger, get_logger

__all__ = ['settings', 'Settings', 'logger', 'get_logger']

