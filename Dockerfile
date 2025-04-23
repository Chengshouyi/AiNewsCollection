FROM python:3.9-slim

# 系統環境設定
ENV DEBIAN_FRONTEND=noninteractive
# 確保 Python 輸出立即顯示
ENV PYTHONUNBUFFERED=1           
# 避免生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1    
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 創建非 root 用戶和組
ARG USERNAME=appuser
ARG USER_UID=1001
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME && \
    useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

# 安裝應用運行所需的最少工具 (移除 git, curl)
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    bash \
    && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 創建資料庫目錄並賦予權限給新用戶
# 注意: /app 目錄本身由 WORKDIR 創建，所有權默認為 root
# 我們需要確保非 root 用戶可以寫入掛載點 /app/data
# 創建目錄並更改所有權
RUN mkdir -p /app/data && chown ${USERNAME}:${USERNAME} /app/data

# 複製依賴文件
COPY --chown=${USERNAME}:${USERNAME} requirements.txt .

# 切換到非 root 用戶安裝依賴
USER $USERNAME

# 安裝 requirements.txt 中的套件
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# 切換回 root 用戶複製程式碼 (避免後續 chown 整個 /app 的開銷)
# 或者，如果不需要其他 root 操作，可以保持 USER $USERNAME
# USER root

# 將程式碼複製到工作目錄，並設定所有權
# 如果保持 USER $USERNAME，則不需要 --chown
COPY --chown=${USERNAME}:${USERNAME} . .

# 切換回非 root 用戶作為容器運行的默認用戶
USER $USERNAME

# 暴露 Gunicorn 將使用的端口 (將在 compose 中實際映射)
EXPOSE 8000

# 不設置 ENTRYPOINT 或 CMD，由 docker-compose.yml 指定