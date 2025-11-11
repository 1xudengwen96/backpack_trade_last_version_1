"""
配置文件
"""
import os
import sys  # 导入 sys 模块
from dotenv import load_dotenv

# --- 智能路径定位 ---
# 检查是否作为 PyInstaller 的 .exe 运行
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # 如果是 .exe, .env 文件应该在 .exe 旁边
    # sys.executable 是 .exe 文件的完整路径
    base_dir = os.path.dirname(sys.executable)
else:
    # 如果是作为 .py 脚本运行 (开发环境)
    # __file__ 是 config.py 文件的路径
    base_dir = os.path.dirname(os.path.abspath(__file__))

# 构建 .env 文件的绝对路径 (假设 .env 在项目根目录，即 config.py 的上一级)
# 如果你的 .env 和 config.py 在同一级，就用:
# dotenv_path = os.path.join(base_dir, '.env')

# 根据你的文件结构, run.py 和 .env 都在根目录, config.py 在根目录
# 所以这个路径是正确的:
dotenv_path = os.path.join(base_dir, '.env')
print(f"尝试从以下路径加载 .env: {dotenv_path}")

# 载入环境变数 (从指定路径)
load_dotenv(dotenv_path=dotenv_path)
# --- 智能路径定位结束 ---

# API配置
API_KEY = os.getenv('API_KEY')
SECRET_KEY = os.getenv('SECRET_KEY')
WS_PROXY = os.getenv('PROXY_WEBSOCKET')
API_URL = "https://api.backpack.exchange"
WS_URL = "wss://ws.backpack.exchange"
API_VERSION = "v1"
DEFAULT_WINDOW = "30000"

# 數據庫配置
DB_PATH = 'orders.db'
ENABLE_DATABASE = os.getenv('ENABLE_DATABASE', '0').strip().lower() in {"1", "true", "yes", "on"}

# 日誌配置
LOG_FILE = "market_maker.log"