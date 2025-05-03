FROM node:lts

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
RUN groupadd --gid 1001 vscode \
    && useradd --uid 1001 --gid 1001 -m vscode \
    && echo vscode ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode

# 安裝全域 npm 工具
RUN npm install -g @vue/cli vite

USER vscode
WORKDIR /app

# 設定開發環境
ENV NODE_ENV=development