import os
import sys
from streamlit.web.cli import main

# Vercel 要求的处理函数
def handler(request):
    # 这里的 main.py 必须是你仓库里那个包含 st.title 的文件名
    # 如果你的文件名是 app.py，请把下面这行改为 "app.py"
    sys.argv = [
        "streamlit",
        "run",
        "main.py", 
        "--server.port", "8080",
        "--server.address", "0.0.0.0"
    ]
    main()
