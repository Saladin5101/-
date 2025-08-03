import os
import re
import subprocess
import platform
import configparser
import tkinter as tk
from tkinter import messagebox, ttk

# ------------------- 配置区（用户修改这里） -------------------
LOG_PATH = "/var/log/system.log"  # Mac 系统日志（确保存在）
TRIGGER_WORDS = ["error", "failed", "critical"]  # 触发告警的关键词
ALERT_TITLE = "【日志紧急告警】"  # 邮件主题前缀

# ------------------- 配置文件路径处理 -------------------
def get_config_path():
    import sys
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), "log_alert_config.ini")
    else:
        return os.path.join(os.path.dirname(__file__), "log_alert_config.ini")

config_path = get_config_path()

# ------------------- 获取用户邮箱（图形界面） -------------------
def get_recipient_email():
    if not os.path.exists(config_path):
        input_email_gui()  # 首次运行：弹出邮箱设置窗口
    
    config = configparser.ConfigParser()
    config.read(config_path)
    try:
        return config['alert']['recipient_email']
    except KeyError:
        messagebox.showerror("配置错误", "邮箱配置损坏，请重新设置")
        input_email_gui()
        return config['alert']['recipient_email']

# ------------------- 图形界面输入邮箱 -------------------
def input_email_gui():
    root = tk.Tk()
    root.title("设置告警邮箱")
    root.geometry("400x200")
    root.resizable(False, False)
    
    if platform.system() == "Darwin":
        default_font = ("SF Pro Text", 10)
    else:
        default_font = ("Segoe UI", 10)

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
            error_label.config(text="❌ 邮箱格式错误（例如：your.name@example.com）")
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
        if messagebox.askokcancel("提示", "必须设置邮箱才能使用工具，是否继续设置？", parent=root):
            return
        else:
            root.destroy()
            import sys
            sys.exit(1)

    root.protocol("WM_DELETE_WINDOW", on_close)

    btn_frame = ttk.Frame(root)
    btn_frame.pack(pady=15)
    ttk.Button(btn_frame, text="确认", command=save_email).pack(side=tk.LEFT, padx=10)
    ttk.Button(btn_frame, text="取消", command=on_close).pack(side=tk.LEFT)

    root.mainloop()

# ------------------- 发送告警邮件（调用系统客户端） -------------------
def send_alert_email(subject, content):
    recipient = get_recipient_email()
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
            subprocess.run(["osascript", "-e", script], check=True)
            print(f"✅ Mac Mail.app 已发送邮件 → {recipient}")
        elif os_type == "Windows":  # Windows
            import urllib.parse
            encoded_subj = urllib.parse.quote(subject)
            encoded_cont = urllib.parse.quote(content)
            subprocess.run(f'start mailto:{recipient}?subject={encoded_subj}&body={encoded_cont}', shell=True, check=True)
            print(f"✅ Windows 邮件客户端已打开 → {recipient}")
        else:  # Linux
            import urllib.parse
            encoded_subj = urllib.parse.quote(subject)
            encoded_cont = urllib.parse.quote(content)
            subprocess.run(f'xdg-open "mailto:{recipient}?subject={encoded_subj}&body={encoded_cont}"', shell=True, check=True)
            print(f"✅ Linux 邮件客户端已打开 → {recipient}")
    except Exception as e:
        print(f"❌ 邮件发送失败：{e}")

# ------------------- 核心：日志监控函数（必须定义！） -------------------
def monitor_logs():  # 这里就是关键的函数定义
    print(f"🔍 开始监控日志：{LOG_PATH}（按 Ctrl+C 停止）")
    print(f"📌 触发关键词：{TRIGGER_WORDS}")
    RECIPIENT_EMAIL = get_recipient_email()
    print(f"📧 告警将发送至：{RECIPIENT_EMAIL}\n")

    try:
        # 启动 tail -f 实时监控日志
        process = subprocess.Popen(
            ["tail", "-f", LOG_PATH],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # 逐行读取日志
        for line in iter(process.stdout.readline, ''):
            line = line.strip()
            if not line:
                continue
            # 检查是否包含关键词
            if any(word.lower() in line.lower() for word in TRIGGER_WORDS):
                print(f"🔴 发现异常日志：{line}")
                # 构建告警内容
                alert_subject = f"{ALERT_TITLE}[{[w for w in TRIGGER_WORDS if w.lower() in line.lower()][0].upper()}]"
                alert_content = f"时间：{subprocess.check_output('date', shell=True, text=True).strip()}\n日志路径：{LOG_PATH}\n异常内容：{line}"
                # 发送邮件
                send_alert_email(alert_subject, alert_content)

    except KeyboardInterrupt:
        print("\n👋 监控已手动停止")
    except Exception as e:
        print(f"❌ 监控过程出错：{e}")
    finally:
        if 'process' in locals():
            process.terminate()

# ------------------- 调用监控函数（必须放在函数定义之后！） -------------------
if __name__ == "__main__":
    monitor_logs()  # 现在这个函数已经定义了，可以正常调用了