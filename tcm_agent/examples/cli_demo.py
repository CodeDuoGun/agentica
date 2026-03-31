# -*- coding: utf-8 -*-
"""
TCM Agent - CLI Demo
命令行界面演示
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tcm_agent.system import main

if __name__ == "__main__":
    main()
