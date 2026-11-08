#!/bin/bash
set -euo pipefail
umask 077
if [[ "${1:-}" != serve ]]; then
    exec "$@"
fi
if [[ -z "${PUBLIC_KEY:-}" ]]; then
    echo 'Set PUBLIC_KEY to your SSH public key in the RunPod template; refusing unauthenticated startup.' >&2
    exit 64
fi
mkdir -p /root/.ssh /home/tester/.ssh /run/sshd
printf '%s\n' "$PUBLIC_KEY" > /root/.ssh/authorized_keys
ssh-keygen -l -f /root/.ssh/authorized_keys >/dev/null
cp /root/.ssh/authorized_keys /home/tester/.ssh/authorized_keys
chmod 700 /root/.ssh /home/tester/.ssh
chmod 600 /root/.ssh/authorized_keys /home/tester/.ssh/authorized_keys
chown -R tester:tester /home/tester/.ssh
# /workspace is the persistent volume; never recursively chown an uploaded tree.
mkdir -p /workspace/game /workspace/runs /workspace/src /workspace/profiles
chown tester:tester /workspace/game /workspace/runs /workspace/src /workspace/profiles
chmod 755 /workspace
chmod 700 /workspace/runs /workspace/profiles
ssh-keygen -A
unset PUBLIC_KEY
echo 'Test box ready. SSH port 22; persistent files /workspace; run games as tester.'
exec /usr/sbin/sshd -D -e
