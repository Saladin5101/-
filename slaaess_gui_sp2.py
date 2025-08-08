import os
import re
import subprocess
import platform
import configparser
import tkinter as tk
from tkinter import messagebox, ttk
import sys
import threading
import time

# 全局变量
global_process = None  # 存储日志监控进程，用于关闭时终止

# ------------------- 配置区 -------------------
LOG_PATH = os.path.expanduser("~/Library/Logs/System.log")  # 用户可访问的日志路径
TRIGGER_WORDS = ["error", "failed", "critical"]
ALERT_TITLE = "【日志紧急告警】"

# ------------------- 配置文件路径处理 -------------------
def get_config_path():
    if getattr(sys, 'frozen', False):
        # 应用支持目录（确保可写）
        app_support = os.path.expanduser("~/Library/Application Support/LogAlert")
        os.makedirs(app_support, exist_ok=True)
        return os.path.join(app_support, "log_alert_config.ini")
    else:
        return os.path.join(os.path.dirname(__file__), "log_alert_config.ini")

config_path = get_config_path()  # 初始化配置路径

# ------------------- 获取用户邮箱 -------------------
def get_recipient_email(root):
    if not os.path.exists(config_path):
        input_email_gui(root)  # 首次运行弹窗设置，传入主窗口
    
    config = configparser.ConfigParser()
    config.read(config_path)
    try:
        return config['alert']['recipient_email']
    except KeyError:
        show_error_in_main_thread("配置错误", "邮箱配置损坏，请重新设置", root)
        input_email_gui(root)
        return config['alert']['recipient_email']

# ------------------- 邮箱设置GUI（修复核心：使用Toplevel而非新Tk实例） -------------------
def input_email_gui(parent):
    # 关键修复：用Toplevel创建子窗口，而非新的Tk()，避免多主线程冲突
    root = tk.Toplevel(parent)
    root.title("设置告警邮箱")
    root.geometry("400x200")
    root.resizable(False, False)
    root.transient(parent)  # 设置为主窗口的子窗口
    root.grab_set()  # 模态窗口，阻止操作主窗口
    
    # 适配系统字体
    default_font = ("SF Pro Text", 10) if platform.system() == "Darwin" else ("Segoe UI", 10)

    ttk.Label(root, text="请设置接收告警的邮箱地址", font=(default_font[0], 12, "bold")).pack(pady=15)
    
    frame = ttk.Frame(root)
    frame.pack(pady=5, padx=20, fill=tk.X)
    ttk.Label(frame, text="邮箱地址：", font=default_font).pack(side=tk.LEFT, padx=5)
    email_var = tk.StringVar()
    email_entry = ttk.Entry(frame, textvariable=email_var, width=30, font=default_font)
    email_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    email_entry.focus()

    error_label = ttk.Label(root, text="", foreground="red", font=default_font)
    error_label.pack(pady=5)

    def save_email():
        email = email_var.get().strip()
        email_pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-.]+)+$"
        if not re.match(email_pattern, email):
            error_label.config(text="❌ 邮箱格式错误（例如：yourname@example.com）")
            return
        
        try:
            config = configparser.ConfigParser()
            config['alert'] = {'recipient_email': email}
            with open(config_path, 'w') as f:
                config.write(f)
            messagebox.showinfo("设置成功", f"告警邮箱已保存：\n{email}", parent=root)
            root.destroy()
        except Exception as e:
            messagebox.showerror("保存失败", f"无法写入配置文件：\n{str(e)}", parent=root)

    def on_close():
        if not messagebox.askokcancel("提示", "必须设置邮箱才能使用工具，是否继续设置？", parent=root):
            root.destroy()
            parent.destroy()  # 关闭主窗口
            sys.exit(1)

    root.protocol("WM_DELETE_WINDOW", on_close)

    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=15)
    ttk.Button(btn_frame, text="确认", command=save_email).pack(side=tk.LEFT, padx=10)
    ttk.Button(btn_frame, text="取消", command=on_close).pack(side=tk.LEFT)

    root.wait_window()  # 等待子窗口关闭

# ------------------- 发送告警邮件 -------------------
def send_alert_email(subject, content):
    recipient = get_recipient_email(tk._default_root)  # 使用默认主窗口
    os_type = platform.system()

    try:
        if os_type == "Darwin":  # Mac
            script = f'''
            tell application "Mail"
                set newMessage to make new outgoing message
                tell newMessage
                    set subject to "{subject}"
                    set content to "{content}"
                    make new to recipient at end of to recipients with properties {{address:"{recipient}"}}
                    send
                end tell
            end tell
            '''
            # 添加超时避免卡住
            subprocess.run(["osascript", "-e", script], check=True, timeout=10, capture_output=True, text=True)
            print(f"✅ 邮件已发送 → {recipient}")
        elif os_type == "Windows":
            import urllib.parse
            encoded_subj = urllib.parse.quote(subject)
            encoded_cont = urllib.parse.quote(content)
            subprocess.run(f'start mailto:{recipient}?subject={encoded_subj}&body={encoded_cont}', shell=True, check=True, timeout=10)
            print(f"✅ 邮件客户端已打开 → {recipient}")
        else:  # Linux
            import urllib.parse
            encoded_subj = urllib.parse.quote(subject)
            encoded_cont = urllib.parse.quote(content)
            subprocess.run(f'xdg-open "mailto:{recipient}?subject={encoded_subj}&body={encoded_cont}"', shell=True, check=True, timeout=10)
            print(f"✅ 邮件客户端已打开 → {recipient}")
    except subprocess.TimeoutExpired:
        print(f"❌ 邮件发送超时（可能需要在系统设置中授权）")
    except Exception as e:
        print(f"❌ 邮件发送失败：{e}")

# ------------------- 主线程弹窗处理 -------------------
def show_error_in_main_thread(title, message, root):
    """确保弹窗在主线程执行，避免崩溃"""
    def _show():
        messagebox.showerror(title, message)
    root.after(0, _show)  # 利用tkinter的after机制切换到主线程

# ------------------- 纯Python日志监听（替代tail -f） -------------------
def follow_log(file_path):
    """实时监听日志文件新内容（不依赖系统tail命令）"""
    with open(file_path, 'r') as f:
        f.seek(0, os.SEEK_END)  # 移动到文件末尾
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)  # 无新内容时短暂等待
                continue
            yield line.strip()

# ------------------- 核心监控函数 -------------------
def monitor_logs(root):
    print(f"🔍 开始监控日志：{LOG_PATH}")
    print(f"📌 触发关键词：{TRIGGER_WORDS}")
    RECIPIENT_EMAIL = get_recipient_email(root)
    print(f"📧 告警将发送至：{RECIPIENT_EMAIL}\n")

    # 权限检查
    if not os.path.exists(LOG_PATH):
        show_error_in_main_thread("文件不存在", f"日志文件不存在：{LOG_PATH}", root)
        root.after(0, root.destroy)  # 主线程关闭窗口
        sys.exit(1)
    
    if not os.access(LOG_PATH, os.R_OK):
        show_error_in_main_thread("权限不足", f"无法访问日志文件：{LOG_PATH}\n请检查文件权限后重试", root)
        root.after(0, root.destroy)  # 主线程关闭窗口
        sys.exit(1)

    try:
        # 启动日志监听（纯Python实现）
        global global_process
        for line in follow_log(LOG_PATH):
            if any(word.lower() in line.lower() for word in TRIGGER_WORDS):
                print(f"🔴 发现异常日志：{line}")
                # 构建告警内容
                alert_subject = f"{ALERT_TITLE}[{[w for w in TRIGGER_WORDS if w.lower() in line.lower()][0].upper()}]"
                # 修复：用Python内置方法获取时间，避免subprocess依赖
                alert_content = f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}\n日志路径：{LOG_PATH}\n异常内容：{line}"
                send_alert_email(alert_subject, alert_content)

    except KeyboardInterrupt:
        print("\n👋 监控已手动停止")
    except Exception as e:
        print(f"❌ 监控过程出错：{e}")
        # 错误信息通过主线程弹窗显示
        show_error_in_main_thread("监控错误", f"监控过程中发生错误：\n{str(e)}", root)
    finally:
        global_process = None  # 重置进程状态

# ------------------- 程序入口 -------------------
if __name__ == "__main__":
    # 创建主窗口（唯一主线程）
    root = tk.Tk()
    root.title("日志监控中")
    root.geometry("300x150")
    ttk.Label(root, text="正在监控日志...\n按窗口关闭按钮停止").pack(pady=30)
    
    # 启动监控线程（传递主窗口对象用于弹窗）
    monitor_thread = threading.Thread(target=monitor_logs, args=(root,), daemon=True)
    monitor_thread.start()
    
    # 窗口关闭处理
    def on_close():
        if messagebox.askokcancel("确认", "确定要停止监控吗？"):
            root.destroy()
            # 终止监控进程（纯Python实现无需强制终止）
            global global_process
            global_process = None

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
