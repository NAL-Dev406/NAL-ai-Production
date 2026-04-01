import os
import sys

# 这里的代码会调用你的 streamlit 应用
from streamlit.web.cli import main
if __name__ == "__main__":
    sys.argv = [
        "streamlit",
        "run",
        "your_app_name.py",  # 替换成你主程序的脚本名，比如 app.py
        "--server.port", "8080",
        "--server.address", "0.0.0.0"
    ]
    main()
