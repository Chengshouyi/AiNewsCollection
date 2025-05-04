FROM node:lts

ARG USERNAME=vscode
ARG USER_UID=1001
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

# 安裝 pnpm
RUN npm install -g pnpm

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# 複製 package.json 與 pnpm-lock.yaml
COPY --chown=vscode:vscode package.json pnpm-lock.yaml* ./

# 安裝 pnpm 套件
RUN pnpm install

# 複製其餘專案檔案（如有需要）
# COPY --chown=vscode:vscode . .

USER $USERNAME
WORKDIR /app