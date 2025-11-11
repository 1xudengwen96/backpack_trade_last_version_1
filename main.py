import uvicorn
import api_server
import webbrowser
import threading
import time
import os
import sys
import traceback
from datetime import datetime
import certifi

# --- 🎁 新增的许可证模块 🎁 ---
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidSignature

# --- 许可证模块结束 ---


# --- 🎁 关键步骤: 粘贴你的公钥 🎁 ---
#
# 请打开你生成的 "public_key.pem" 文件,
# 然后把它里面的所有内容, 完整地粘贴到下面这对三引号之间。
#
PUBLIC_KEY_PEM = """
-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAhkneq3GL9CtRLbpc5IE+
G8s1PDNSlKokgiQXEpsMI9+qg/YHc+XnSFUm4XOhYd6Hma8ki9m/OHQNmNApvWVg
B1qRqaeifds0wPsYeQ96BxrEiKQhtDD1VizjQ4YVw2HZwbqfuPhO73AbCUHQQFRv
D4SBcwUAjgYHAZkbxHr41yOnxDP6qD285gynDm806fr1RuUzU1Ai5zvhSoIFqSLW
ZNbUpP0GW6lAGNqiyFa244dWSMsEUJrfymhzo/4+Jaal3QFfb5wMAyQ91UD8iIac
c0VqZHmyM+X6/IjTIcL0zbhK74t0zxh8c2ZYOMiTkK5sjDD/733q6uPXPxeP5LG4
yQIDAQAB
-----END PUBLIC KEY-----
"""


# --- 公钥粘贴结束 ---


# --- 🎁 新增的许可证验证函数 🎁 ---
def validate_license(license_key: str) -> (bool, str):
    """
    验证许可证密钥。
    返回 (是否有效, 消息)
    """
    try:
        # 1. 加载公钥
        try:
            public_key = serialization.load_pem_public_key(
                PUBLIC_KEY_PEM.encode('utf-8')
            )
        except ValueError as e:
            if "Could not deserialize" in str(e):
                return False, "公钥无效。请检查 main.py 中的 PUBLIC_KEY_PEM 变量。"
            raise e

        # 2. 解析 Key (格式: [Payload_b64].[Signature_b64])
        try:
            payload_b64, signature_b64 = license_key.split('.')
        except Exception:
            return False, "密钥格式无效。正确的格式应为 [数据].[签名]"

        # 3. 解码 Payload 和 Signature
        try:
            payload_bytes = base64.urlsafe_b64decode(payload_b64.encode('utf-8'))
            signature_bytes = base64.urlsafe_b64decode(signature_b64.encode('utf-8'))
        except Exception:
            return False, "密钥编码无效 (非Base64)。"

        # 4. 验证签名 (最关键的一步)
        # 这能保证数据 payload_bytes 确实是用你的 private_key 签名的
        try:
            public_key.verify(
                signature_bytes,
                payload_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        except InvalidSignature:
            return False, "签名验证失败，密钥无效或已被篡改。"
        except Exception as e:
            return False, f"签名验证时发生意外错误: {e}"

        # 5. 签名有效，检查有效期
        payload_str = payload_bytes.decode('utf-8')
        try:
            customer_id, expiry_date_str = payload_str.split('|')
        except Exception:
            return False, "许可证数据格式错误。"

        try:
            expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d').date()
        except ValueError:
            return False, f"许可证有效期日期格式错误: {expiry_date_str}"

        today = datetime.now().date()

        if today > expiry_date:
            return False, f"许可证已于 {expiry_date_str} 过期。"

        # 验证通过
        return True, f"验证成功！欢迎您，{customer_id}。\n有效期至 {expiry_date_str}。"

    except Exception as e:
        return False, f"许可证解析时发生严重错误: {e}"


# --- 验证函数结束 ---


# --- 你原来的 main.py 代码 ---
os.environ['SSL_CERT_FILE'] = certifi.where()


def resource_path(relative_path):
    """ 获取资源的绝对路径，适用于开发环境和 PyInstaller 打包环境 """
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    except Exception:
        base_path = os.path.abspath(".")  # Fallback
    return os.path.join(base_path, relative_path)


def setup_logging_for_exe():
    """将 stdout 和 stderr 重定向到日志文件"""
    log_dir = os.path.expanduser("~/.my_trading_bot_logs")
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError:
            log_dir = "."

    log_file_path = os.path.join(log_dir, "app_run.log")

    try:
        sys.stdout = open(log_file_path, 'a', encoding='utf-8', buffering=1)
        sys.stderr = open(log_file_path, 'a', encoding='utf-8', buffering=1)

        print("\n" + "=" * 50)
        print(f"[{datetime.now()}] Application started.")
        print(f"Log file: {log_file_path}")
        print("=" * 50 + "\n")

    except Exception as e:
        print(f"Failed to setup logging to file: {e}")


HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def open_browser():
    """等待服务器启动，然后打开浏览器。"""
    time.sleep(3)
    print(f"正在浏览器中打开: {URL} ...")
    try:
        webbrowser.open(URL)
    except Exception as e:
        print(f"自动打开浏览器失败: {e}. 请手动访问 {URL}")


if __name__ == "__main__":
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        os.environ['SSL_CERT_FILE'] = resource_path('certifi/cacert.pem')
        setup_logging_for_exe()
    else:
        print("Running as .py script (Dev mode)...")

    # --- 🎁 这是新的“外壳”启动逻辑 🎁 ---
    print("\n" + "=" * 60)
    print(" 欢迎使用 Backpack 交易机器人")
    print(" (需要许可证密钥才能启动)")
    print("=" * 60)

    # 尝试从文件读取Key，如果失败，则要求输入
    KEY_FILE = "license.key"
    license_key = ""

    try:
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, 'r') as f:
                license_key = f.read().strip()
            print(f"已从 {KEY_FILE} 文件中读取密钥...")
        else:
            print("请输入您的许可证密钥 (License Key):")
            license_key = input()
            # 尝试保存Key
            try:
                with open(KEY_FILE, 'w') as f:
                    f.write(license_key)
                print(f"密钥已保存到 {KEY_FILE}，下次将自动读取。")
            except Exception as e:
                print(f"警告：保存密钥到 {KEY_FILE} 失败: {e}")

    except Exception:
        print("无法读取或输入密钥，程序将在10秒后退出...")
        time.sleep(10)
        sys.exit(1)

    # 验证Key
    is_valid, message = validate_license(license_key.strip())

    print("\n" + "-" * 60)
    print(f"验证结果: {message}")
    print("-" * 60)

    if not is_valid:
        print("启动失败。如果密钥错误，请删除 license.key 文件后重试。")
        print("程序将在10秒后退出...")
        time.sleep(10)
        sys.exit(1)  # 退出程序

    # --- 🔑 验证通过，才执行你原来的代码 🔑 ---

    print("\n许可证验证通过，正在启动服务器...")

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    print(f"正在 {HOST}:{PORT} 启动 FastAPI 服务器...")
    print("按 Ctrl+C 停止服务器。")

    try:
        uvicorn.run(
            api_server.app,
            host=HOST,
            port=PORT,
            log_level="info",
            reload=False
        )
    except Exception as e:
        print(f"启动 Uvicorn 服务器失败: {e}")
        print(f"Uvicorn 运行失败: {e}")
        traceback.print_exc()
        input("服务器启动失败，按 Enter 键退出...")