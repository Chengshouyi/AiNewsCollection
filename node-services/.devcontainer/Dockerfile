FROM node:lts

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    vim \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# 安裝 pnpm 和 NestJS CLI
RUN npm install -g pnpm @nestjs/cli typescript ts-node

# 檢查並創建用戶和群組
RUN if ! getent group $USER_GID > /dev/null 2>&1; then \
        groupadd --gid $USER_GID $USERNAME; \
    else \
        groupmod -n $USERNAME $(getent group $USER_GID | cut -d: -f1); \
    fi && \
    if ! getent passwd $USER_UID > /dev/null 2>&1; then \
        useradd --uid $USER_UID --gid $USER_GID -m $USERNAME; \
    else \
        usermod -l $USERNAME -g $USER_GID $(getent passwd $USER_UID | cut -d: -f1); \
    fi && \
    echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME && \
    chmod 0440 /etc/sudoers.d/$USERNAME

# 設定工作目錄
WORKDIR /workspace

# 設定目錄權限
RUN mkdir -p /workspace && \
    chown -R $USERNAME:$USERNAME /workspace

# 切換到 vscode 用戶
USER $USERNAME

# 複製 package.json 與 pnpm-lock.yaml
COPY --chown=$USERNAME:$USERNAME package.json pnpm-lock.yaml* ./

# 安裝 pnpm 套件
RUN pnpm install

# 複製其餘專案檔案（如有需要）
# COPY --chown=vscode:vscode . .
# 設定開發環境
ENV NODE_ENV=development