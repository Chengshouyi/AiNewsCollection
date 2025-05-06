FROM python:3.9-slim

# 設定使用者名稱、使用者ID、使用者群組ID
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# 系統環境設定
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 更新 apt-get 並安裝基本工具 + PostgreSQL 客戶端 + libpq-dev
# libpq-dev 在使用 psycopg2-binary 時通常不是必需的，但如果遇到編譯問題可以加上
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
    bash \
    git \
    curl \
    wget \
    sudo \
    vim \
    procps \
    lsb-release \
    apt-transport-https \
    software-properties-common \
    gnupg \
    postgresql-client \
    # libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*


# 新增使用者
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# 設定使用者
USER $USERNAME

WORKDIR /workspace

# 若需要dockerfile能獨立完成環境安裝而不需要在 devcontainer.json 中安裝，則需要以下步驟
# --- 不需要 COPY requirements.txt，因為會被 volume mount 覆蓋 ---
# COPY --chown=vscode:vscode requirements.txt requirements-dev.txt ./

# 安裝 Python 套件--> 在 devcontainer.json 中安裝
# RUN pip install --upgrade pip \
#     && pip install --user -r /workspace/requirements.txt -r /workspace/requirements-dev.txt --no-warn-script-location

# 建立必要資料夾並設定權限
# RUN mkdir -p /workspace/logs \
#     && chown vscode:vscode /workspace/logs \
#     && mkdir -p /workspace/data/web_site_configs \
#     && chown vscode:vscode /workspace/data /workspace/data/web_site_configs

# 複製 config 檔案（確認來源路徑正確，config 檔案在 src/crawlers/configs 下）
# COPY --chown=vscode:vscode src/crawlers/configs/bnext_crawler_config.json /workspace/data/web_site_configs/

USER $USERNAME

# --- 可以保留一個預設的 CMD 讓容器保持運行 ---
CMD ["sleep", "infinity"]
