FROM python:3.9-slim
# 設定使用者名稱、使用者ID、使用者群組ID
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
# 更新apt-get
RUN apt-get update && apt-get install -y git curl wget sudo vim procps lsb-release \
    && rm -rf /var/lib/apt/lists/*
# 新增使用者
RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

WORKDIR /workspace
# 安裝pylint、black、pytest、pytest-cov
RUN pip install --upgrade pip && pip install pylint black pytest pytest-cov
# 設定PYTHONPATH
ENV PYTHONPATH=/workspace
# 設定PATH
ENV PATH="/home/vscode/.local/bin:${PATH}"
# 設定使用者
USER $USERNAME
# 設定命令
CMD ["bash"]