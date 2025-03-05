FROM python:3.9-slim
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID
RUN apt-get update && apt-get install -y git curl wget sudo vim procps lsb-release \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME
    
WORKDIR /workspace
RUN pip install --upgrade pip && pip install pylint black pytest pytest-cov
ENV PYTHONPATH=/workspace
USER $USERNAME
CMD ["bash"]