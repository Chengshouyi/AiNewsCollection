FROM node:lts

ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# Update and install base tools and Docker CLI dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    vim \
    sudo \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release \
    && rm -rf /var/lib/apt/lists/*

# Add Docker's official GPG key
RUN mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up Docker's apt repository
RUN echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker CLI (docker-ce-cli)
RUN apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Install pnpm and NestJS CLI
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

# Create a group with the same GID as the host's Docker socket group (1001)
# and add the vscode user to it, to allow access to the Docker socket.
ARG DOCKER_HOST_GID_ARG=1001 
RUN sudo groupadd -g ${DOCKER_HOST_GID_ARG} docker_host_socket_access_group || true && \
    sudo usermod -aG docker_host_socket_access_group ${USERNAME}

# Also add vscode user to the root group (GID 0)
# because the docker.sock inside the container appears as root:root
RUN sudo usermod -aG root ${USERNAME} # or sudo usermod -aG 0 ${USERNAME}

# 設定工作目錄
WORKDIR /workspace

# 設定目錄權限
RUN mkdir -p /workspace && \
    chown -R $USERNAME:$USERNAME /workspace

# 切換到 vscode 用戶
USER $USERNAME

# # 複製 package.json 與 pnpm-lock.yaml
# COPY --chown=$USERNAME:$USERNAME package.json pnpm-lock.yaml* ./

# # 安裝 pnpm 套件
# RUN pnpm install

# 複製其餘專案檔案（如有需要）
# COPY --chown=vscode:vscode . .
# 設定開發環境
ENV NODE_ENV=development