FROM python:3.9-slim

# 設定使用者名稱、使用者ID、使用者群組ID
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

# 系統環境設定
ENV DEBIAN_FRONTEND=noninteractive
ENV SHELL=/bin/bash
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# 更新apt-get
RUN apt-get update && apt-get install -y \
    bash \
    git \
    curl \
    wget \
    sudo \
    vim \
    procps \
    lsb-release \
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

WORKDIR /workspace

RUN mkdir -p /workspace/data && \
    chmod 777 /workspace/data

# 設定PYTHONPATH
ENV PYTHONPATH=/workspace
# 設定PATH
ENV PATH="/home/vscode/.local/bin:${PATH}"

# 設定資料庫路徑
ENV DATABASE_PATH=/workspace/data/news.db

# 設定預設 shell
SHELL ["/bin/bash", "-c"]

# 設定入口點
ENTRYPOINT ["/bin/bash"]

# 設定使用者
USER $USERNAME

# 設定命令
CMD ["bash"]