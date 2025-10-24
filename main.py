import uvicorn
import api_server
import webbrowser
import threading
import time
import os
import sys  # 导入 sys
import traceback
from datetime import datetime


# --- (新) 资源路径函数 ---
# 这是一个关键函数，它帮助 .exe 文件找到被打包进去的资源
def resource_path(relative_path):
    """ 获取资源的绝对路径，适用于开发环境和 PyInstaller 打包环境 """
    try:
        # PyInstaller 创建一个临时文件夹并将路径存储在 _MEIPASS
        # (修正) 使用 getattr(sys, '_MEIPASS', ...) 来安全地检查
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        # 如果 _MEIPASS 不存在，则使用常规的 Python 路径
        base_path = os.path.abspath(".")  # Fallback

    return os.path.join(base_path, relative_path)


# --- (新) 重定向 stdout/stderr 到日志文件 ---
# 这在 --windowed 模式下尤其重要，因为它没有控制台显示 print 和错误
def setup_logging_for_exe():
    """将 stdout 和 stderr 重定向到日志文件"""
    # (修正) 确保日志目录存在
    log_dir = os.path.expanduser("~/.my_trading_bot_logs")  # 存储日志到用户目录
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError:
            # 如果无法创建，退回到当前目录
            log_dir = "."

    log_file_path = os.path.join(log_dir, "app_run.log")

    # (修正) 确保 try-except 覆盖文件操作
    try:
        # 使用 'a' 模式追加日志
        sys.stdout = open(log_file_path, 'a', encoding='utf-8', buffering=1)  # 1 = line buffering
        sys.stderr = open(log_file_path, 'a', encoding='utf-8', buffering=1)

        print("\n" + "=" * 50)
        print(f"[{datetime.now()}] Application started.")
        print(f"Log file: {log_file_path}")
        print("=" * 50 + "\n")

    except Exception as e:
        # 如果日志文件都无法创建，那就没办法了
        print(f"Failed to setup logging to file: {e}")
        # 此时 print 可能无法显示在 --windowed 模式下


# --- 服务器和浏览器启动逻辑 ---
HOST = "127.0.0.1"  # 绑定到 localhost
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def open_browser():
    """等待服务器启动，然后打开浏览器。"""
    # 增加延迟，确保 uvicorn 有足够时间绑定端口
    time.sleep(3)
    print(f"正在浏览器中打开: {URL} ...")
    try:
        webbrowser.open(URL)
    except Exception as e:
        print(f"自动打开浏览器失败: {e}. 请手动访问 {URL}")


if __name__ == "__main__":
    # (新) 检查是否作为 PyInstaller 打包的 .exe 运行
    # (修正) 使用 'frozen' 属性检查
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # 如果是 .exe，设置资源路径并重定向日志
        print("Running as EXE, setting up resource paths and logging...")
        # (新) PyInstaller 需要设置这个，以便 SSL 证书能被找到
        os.environ['SSL_CERT_FILE'] = resource_path('certifi/cacert.pem')
        setup_logging_for_exe()
    else:
        print("Running as .py script (Dev mode)...")

    # 启动浏览器线程（设置为 daemon，以便主进程退出时它也退出）
    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    print(f"正在 {HOST}:{PORT} 启动 FastAPI 服务器...")
    print("按 Ctrl+C 停止服务器。")

    # 在主线程中运行 FastAPI/Uvicorn 服务器
    # (修正) 确保 uvicorn.run 传入的是 app 对象
    # (修正) reload=False 是打包发布的关键！
    try:
        uvicorn.run(
            api_server.app,  # 确保 api_server.py 中有 app = FastAPI(...)
            host=HOST,
            port=PORT,
            log_level="info",
            reload=False  # 打包时必须为 False
        )
    except Exception as e:
        print(f"启动 Uvicorn 服务器失败: {e}")
        print(f"Uvicorn 运行失败: {e}")
        traceback.print_exc()
        # (新) 在退出前给用户看错误信息
        input("服务器启动失败，按 Enter 键退出...")
