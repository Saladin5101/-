from setuptools import setup

APP = ['slaaess_gui_sp2.py']  # 你的主程序文件名（替换成你实际的文件名）
DATA_FILES = []  # 不需要额外文件的话，空着就行
OPTIONS = {
    'argv_emulation': False,  # 适配 macOS 的窗口操作
    'packages': ['tkinter'],  # 确保 Tkinter 被打包进去
    'plist': {
        'CFBundleName': 'slaaess_gui_sp2.py',  # 应用显示名称
        'CFBundleVersion': '1.0.1 (Beta-2)',  # 版本号（对应你的 SP2）
        'CFBundleIdentifier': 'com.saladin5101.slaaess',  # 唯一标识（随便写，格式对就行）
    }
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)