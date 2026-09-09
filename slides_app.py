"""
slides_app.py

新版 16:9 幻灯片式 Streamlit 应用
- 每页 16:9 比例 (338.7mm x 190.5mm)
- 使用改进的 slide_16x9 模块替换 slide_16_9
- 支持所有页面包括分品类页面
"""

import sys
import os

# 获取项目目录
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if not _BASE_DIR:
    _BASE_DIR = os.getcwd()

# 将项目目录加入 Python 路径
if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

# 用新的 slide_16x9 替换旧的 slide_16_9 模块
import slide_16x9
sys.modules['slide_16_9'] = slide_16x9

# 执行 dashboard.py（会自动使用新的 slide_16x9 模块）
_dash_path = os.path.join(_BASE_DIR, 'dashboard.py')
with open(_dash_path, 'r', encoding='utf-8') as f:
    _code = f.read()

exec(compile(_code, _dash_path, 'exec'))
