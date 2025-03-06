FROM python:3.9-slim
# 設定工作目錄
WORKDIR /app

# 建立資料庫目錄
RUN mkdir -p /app/data

# 複製 requirements.txt
COPY requirements.txt .
# 安裝 requirements.txt 中的套件
RUN pip install -r requirements.txt
# 複製其他程式碼
COPY . .

ENV DATABASE_PATH=/app/data/news.db

# 設定命令
CMD ["python", "run.py"]