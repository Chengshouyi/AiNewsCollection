FROM python:3.9-slim

# 系統環境設定
ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 安裝必要工具
RUN apt-get update && apt-get install -y \
    bash \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 建立資料庫目錄
RUN mkdir -p /app/data

# 複製 requirements.txt
COPY requirements.txt .

# 安裝 requirements.txt 中的套件
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 複製其他程式碼
COPY . .

ENV DATABASE_PATH=/app/data/news.db

# 設定預設 shell
SHELL ["/bin/bash", "-c"]

# 設定入口點
ENTRYPOINT ["/bin/bash"]

# 設定命令
CMD ["python", "run.py"]