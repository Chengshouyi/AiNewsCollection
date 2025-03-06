FROM python:3.9-slim
# 設定工作目錄
WORKDIR /app
# 複製 requirements.txt
COPY requirements.txt .
# 安裝 requirements.txt 中的套件
RUN pip install -r requirements.txt
# 複製其他程式碼
COPY . .
# 設定命令
CMD ["python", "run.py"]