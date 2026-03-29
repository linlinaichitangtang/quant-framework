#!/bin/bash
# 启动API服务

cd "$(dirname "$0")"

# 安装依赖如果不存在
if [ ! -d "venv" ]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# 启动服务
python -m app.main
