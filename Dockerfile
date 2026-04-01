# OpenClaw量化框架 - 一体化构建（可选）
# 推荐使用 docker-compose 进行多服务部署: docker-compose up -d
#
# 如果需要单镜像部署，取消下方注释并修改对应配置

# FROM python:3.11-slim AS backend
# WORKDIR /app
# COPY backend/requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt
# COPY backend/ .
# EXPOSE 8000
# CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
