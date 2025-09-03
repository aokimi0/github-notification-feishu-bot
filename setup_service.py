import os
import sys
import subprocess
import logging

# 配置基本的日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_service():
    """创建、安装并启动 systemd 服务"""
    
    # 1. 检查 root 权限
    if os.geteuid() != 0:
        logging.error("此脚本必须以 root 权限运行。请使用 'sudo python setup_service.py'")
        sys.exit(1)

    # 2. 定义配置变量
    service_name = "github_webhook"
    service_description = "GitHub Webhook to Feishu Service"
    
    # 获取绝对路径
    working_directory = os.path.dirname(os.path.abspath(__file__))
    python_executable = "/opt/venvs/base/bin/python" # 根据项目要求指定
    script_path = os.path.join(working_directory, "main.py")
    
    service_file_path = f"/etc/systemd/system/{service_name}.service"

    logging.info(f"服务名称: {service_name}")
    logging.info(f"工作目录: {working_directory}")
    logging.info(f"Python解释器: {python_executable}")
    logging.info(f"运行脚本: {script_path}")
    logging.info(f"服务文件路径: {service_file_path}")

    # 3. 创建服务文件内容
    service_content = f"""[Unit]
Description={service_description}
After=network.target

[Service]
User=root
WorkingDirectory={working_directory}
ExecStart={python_executable} {script_path}
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""

    # 4. 写入服务文件并运行 systemctl 命令
    try:
        logging.info(f"正在向 {service_file_path} 写入 systemd 服务文件...")
        with open(service_file_path, "w") as f:
            f.write(service_content)
        logging.info("服务文件创建成功。")

        commands = [
            ["systemctl", "daemon-reload"],
            ["systemctl", "enable", service_name],
            ["systemctl", "restart", service_name]
        ]

        for cmd in commands:
            logging.info(f"正在执行命令: {' '.join(cmd)}")
            # check=True 会在命令失败时抛出 CalledProcessError 异常
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)

        logging.info("--- 服务配置成功 ---")
        logging.info(f"服务 '{service_name}' 已安装并启动。")
        logging.info(f"请使用 'systemctl status {service_name}' 查看服务状态。")

    except PermissionError:
        logging.error(f"写入 {service_file_path} 时权限不足。请确保使用 'sudo' 运行。")
        sys.exit(1)
    except FileNotFoundError:
        logging.error("'systemctl' 命令未找到。此脚本适用于使用 systemd 的系统。")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        logging.error(f"执行 systemd 命令时出错: {' '.join(e.cmd)}")
        logging.error(f"返回码: {e.returncode}")
        logging.error(f"标准输出:\n{e.output.decode() if hasattr(e, 'output') else 'N/A'}")
        logging.error(f"标准错误:\n{e.stderr.decode() if hasattr(e, 'stderr') else 'N/A'}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"发生未知错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    setup_service() 