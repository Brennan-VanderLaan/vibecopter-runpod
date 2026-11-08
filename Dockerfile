FROM ubuntu:22.04@sha256:076e7bf82319619f28dd0aa9c02ab34b055ad37100395b4f49a2ffba04fb5e11

ARG DEBIAN_FRONTEND=noninteractive
ARG SOURCE_REVISION=local
LABEL org.opencontainers.image.source="https://github.com/Brennan-VanderLaan/vibecopter-runpod" \
      org.opencontainers.image.title="Vibecopter Linux test box" \
      org.opencontainers.image.description="RunPod SSH development and native Vulkan test environment; no game or Unreal Engine included" \
      org.opencontainers.image.revision="${SOURCE_REVISION}"

# NVIDIA's host driver is injected by the container runtime, never installed here.
ENV NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,video,display \
    LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git git-lfs openssh-server rsync unzip zip zstd xz-utils \
      build-essential clang lld cmake ninja-build ccache pkg-config gdb strace \
      python3 python3-pip python3-venv python3-numpy python3-pil python3-cryptography \
      libvulkan1 vulkan-tools mesa-vulkan-drivers libgl1 libegl1 libglx0 \
      libsdl2-2.0-0 libasound2 libpulse0 libnss3 libnspr4 libgbm1 \
      libx11-6 libxext6 libxrandr2 libxi6 libxcursor1 libxinerama1 libxss1 libxtst6 \
      libgtk-3-0 libatk-bridge2.0-0 libdrm2 libxkbcommon0 libglu1-mesa \
      ffmpeg fonts-dejavu-core xvfb xauth x11-utils procps util-linux \
    && dpkg-query -W > /opt-image-packages.txt \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /bin/bash tester \
    && passwd -d tester \
    && mkdir -p /run/sshd /opt/vibecopter /workspace \
    && rm -f /etc/ssh/ssh_host_* \
    && printf '%s\n' \
      'Port 22' 'ListenAddress 0.0.0.0' 'HostKey /etc/ssh/ssh_host_ed25519_key' \
      'PermitRootLogin prohibit-password' 'PasswordAuthentication no' \
      'KbdInteractiveAuthentication no' 'PubkeyAuthentication yes' \
      'PermitEmptyPasswords no' 'UsePAM yes' 'AllowUsers root tester' \
      'Subsystem sftp internal-sftp' > /etc/ssh/sshd_config

COPY --chmod=755 entrypoint.sh /usr/local/bin/testbox-entrypoint
RUN ln -s /usr/local/bin/testbox-entrypoint /start.sh
COPY --chmod=755 run-game /usr/local/bin/run-game
COPY --chmod=755 probe.py runner.py /opt/vibecopter/
COPY tests /opt/vibecopter/tests
RUN printf '%s\n' "${SOURCE_REVISION}" > /opt/vibecopter/image-revision
EXPOSE 22
WORKDIR /workspace
ENTRYPOINT ["testbox-entrypoint"]
CMD ["serve"]
