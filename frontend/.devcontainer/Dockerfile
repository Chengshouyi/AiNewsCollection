FROM node:lts

# 設定使用者名稱、使用者ID、使用者群組ID
ARG USERNAME=vscode
ARG USER_UID=1001
ARG USER_GID=$USER_UID

# 系統環境設定
ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y \
    git \
    curl \
    vim \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# 建立 vscode 使用者（避免與 node:lts 內建的 node:1000 衝突，這裡用 1001）
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME  \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# 安裝全域 npm 工具
RUN npm install -g @vue/cli vite

# 複製 package.json 與 lock 檔
COPY --chown=vscode:vscode package.json package-lock.json* ./

# 安裝 npm 套件
RUN npm install

# 複製其餘專案檔案（如有需要）
# COPY --chown=vscode:vscode . .

USER $USERNAME
WORKDIR /workspace

# 設定開發環境
ENV NODE_ENV=development