#!/bin/bash
set -Eeuo pipefail
umask 077
if [[ $# -gt 0 && -n "$1" && "$1" != serve ]]; then
    exec "$@"
fi
startup_failed() {
    echo "TESTBOX STARTUP FAILED at line $1 (exit $2). Keeping container alive for authenticated RunPod gateway recovery; direct SSH may be unavailable." >&2
    exec sleep infinity
}
trap 'startup_failed "$LINENO" "$?"' ERR
echo 'Test box startup beginning.'
if [[ -z "${PUBLIC_KEY:-}" ]]; then
    echo 'PUBLIC_KEY is unset. Direct SSH is disabled; authenticated RunPod gateway access remains available. Set PUBLIC_KEY and restart to enable port 22.' >&2
    exec sleep infinity
fi
mkdir -p /root/.ssh /home/tester/.ssh /run/sshd
printf '%s\n' "$PUBLIC_KEY" | tr -d '\r' > /root/.ssh/authorized_keys
ssh-keygen -l -f /root/.ssh/authorized_keys >/dev/null
cp /root/.ssh/authorized_keys /home/tester/.ssh/authorized_keys
chmod 700 /root/.ssh /home/tester/.ssh
chmod 600 /root/.ssh/authorized_keys /home/tester/.ssh/authorized_keys
chown -R tester:tester /home/tester/.ssh
# /workspace is the persistent volume; never recursively chown an uploaded tree.
mkdir -p /workspace/game /workspace/runs /workspace/src /workspace/profiles
chown tester:tester /workspace/game /workspace/runs /workspace/src /workspace/profiles
# Do not chmod the volume mount itself; some network volumes prohibit it.
chmod 700 /workspace/runs /workspace/profiles
ssh-keygen -A
unset PUBLIC_KEY
echo 'Validating direct SSH configuration.'
/usr/sbin/sshd -t
echo 'Test box ready. SSH port 22; persistent files /workspace; run games as tester.'
exec /usr/sbin/sshd -D -e
