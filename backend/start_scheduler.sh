#!/bin/bash
# 启动数据采集定时任务

cd "$(dirname "$0")"

source venv/bin/activate

# 启动定时采集任务
python -m data_collection.scheduler
