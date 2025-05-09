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

# 安裝 Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*


# 新增使用者
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME && \
    chmod 0440 /etc/sudoers.d/$USERNAME

# Create a group with the same GID as the host's Docker socket group (1001)
# and add the vscode user to it, to allow access to the Docker socket.
ARG DOCKER_HOST_GID_ARG=1001 
RUN sudo groupadd -g ${DOCKER_HOST_GID_ARG} docker_host_socket_access_group || true && \
    sudo usermod -aG docker_host_socket_access_group ${USERNAME}
    
# Also add vscode user to the root group (GID 0)
# because the docker.sock inside the container appears as root:root
RUN sudo usermod -aG root ${USERNAME} # or sudo usermod -aG 0 ${USERNAME}

# 設定使用者
USER $USERNAME

WORKDIR /workspace


USER $USERNAME

# --- 可以保留一個預設的 CMD 讓容器保持運行 ---
CMD ["sleep", "infinity"]
