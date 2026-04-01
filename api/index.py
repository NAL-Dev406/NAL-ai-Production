from http.server import BaseHTTPRequestHandler
import os
import sys

# 这是一个极其简化的包装器，试图在 Vercel 环境下触发 Streamlit
# 注意：Streamlit 官方并不正式支持在 Vercel Serverless 上运行
def handler(request):
    # 这里必须改成你真正的 Streamlit 文件名
    main_file = "app.py" 
    
    os.system(f"streamlit run {main_file} --server.port 8080 --server.address 0.0.0.0")
    return
