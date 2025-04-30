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

WORKDIR /app

# 複製 requirements 檔案 (dev container 會掛載整個目錄，但先複製可以利用快取)
# 注意：這裡假設 requirements*.txt 在專案根目錄，而不是 .devcontainer 裡
COPY --chown=vscode:vscode requirements.txt requirements-dev.txt ./
