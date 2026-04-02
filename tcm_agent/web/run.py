# -*- coding: utf-8 -*-
"""
启动脚本 - 一键启动中医问诊系统 Web 服务
"""
import os
import sys

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

if __name__ == "__main__":
    from tcm_agent.web.api import main
    main()
