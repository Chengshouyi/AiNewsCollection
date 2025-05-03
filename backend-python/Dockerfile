FROM python:3.9-slim

# 系統環境設定 (保持不變)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 創建非 root 用戶和組 (保持不變)
ARG USERNAME=appuser
ARG USER_UID=1001
ARG USER_GID=$USER_UID
RUN groupadd --gid $USER_GID $USERNAME && \
    useradd --uid $USER_UID --gid $USER_GID -m $USERNAME

# 更新 apt-get 並安裝基礎工具
# 如果生產環境需要 psql，請取消註解下一行
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    bash \
    # postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 設定工作目錄 (保持不變)
WORKDIR /app

# 假設您的應用程式是以 'appuser' 使用者和群組執行的
# 如果使用者不存在，您可能需要先創建 user/group
# RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN mkdir -p /app/logs && chown ${USERNAME}:${USERNAME} /app/logs
RUN mkdir -p /app/data && chown ${USERNAME}:${USERNAME} /app/data
RUN mkdir -p /app/data/web_site_configs && chown ${USERNAME}:${USERNAME} /app/data/web_site_configs

# 如果您是以 root 執行 (不推薦)
# RUN mkdir -p /app/logs

# 複製依賴文件 (確保 requirements.txt 包含 psycopg2-binary)
COPY --chown=${USERNAME}:${USERNAME} requirements.txt .


# 切換到非 root 用戶安裝依賴
USER $USERNAME
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 將 appuser 的 local bin 加入 PATH
ENV PATH="/home/${USERNAME}/.local/bin:${PATH}"
# 切換回 root 以複製程式碼並設定正確的擁有者
# (或者保持 appuser 並確保所有複製的檔案擁有者正確)
# USER root
# COPY --chown=${USERNAME}:${USERNAME} . /app
# USER $USERNAME

# 複製應用程式碼 (建議在安裝依賴後複製，以更好利用快取)
# 確保複製的檔案擁有者是 appuser
COPY --chown=${USERNAME}:${USERNAME} . /app
# copy 預設爬蟲config檔案
COPY --chown=${USERNAME}:${USERNAME} src/crawlers/configs/bnext_crawler_config.json /app/data/web_site_configs

# 複製並設定 entrypoint 腳本
COPY --chown=${USERNAME}:${USERNAME} entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 設定 Entrypoint
ENTRYPOINT ["/entrypoint.sh"]

# 設定最終用戶 (保持不變)
USER $USERNAME

# 設定預設指令 (web 服務會在 docker-compose.yml 中覆蓋此指令)
# 這個 CMD 會被 entrypoint.sh 的 exec "$@" 執行
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", "src.web.app:app"]

# ENTRYPOINT 或 CMD 指令 (舊的 CMD 移到上面)
# CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:8000", "src.web.app:app"]