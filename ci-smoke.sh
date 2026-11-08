#!/bin/bash
set -euo pipefail
image=${1:?image required}
tmp=$(mktemp -d)
name=testbox-ci-${RANDOM}-$$
cleanup() { docker rm -f "$name" >/dev/null 2>&1 || true; rm -rf "$tmp"; }
trap cleanup EXIT
docker run --rm "$image" bash -c 'test ! -f /etc/ssh/ssh_host_ed25519_key; bash -n /usr/local/bin/testbox-entrypoint /usr/local/bin/run-game'
docker run --rm --user tester --workdir /tmp "$image" python3 -B -m unittest discover -s /opt/vibecopter/tests -v
if docker run --rm "$image"; then
    echo 'ERROR: startup without PUBLIC_KEY must fail' >&2
    exit 1
fi
ssh-keygen -q -t ed25519 -N '' -f "$tmp/key"
docker run -d --name "$name" -e "PUBLIC_KEY=$(cat "$tmp/key.pub")" -p 127.0.0.1::22 "$image"
port=$(docker port "$name" 22/tcp | cut -d: -f2)
opts=(-i "$tmp/key" -o BatchMode=yes -o ConnectTimeout=2 -o StrictHostKeyChecking=accept-new -o "UserKnownHostsFile=$tmp/known_hosts" -p "$port")
ready=false
for attempt in $(seq 1 20); do
    if ssh "${opts[@]}" tester@127.0.0.1 'test "$(id -u)" = 1000'; then ready=true; break; fi
    sleep 1
done
if [[ "$ready" != true ]]; then docker logs "$name"; exit 1; fi
ssh "${opts[@]}" root@127.0.0.1 '/usr/sbin/sshd -T | grep -Fx "passwordauthentication no"; test -w /workspace/game; run-game --lane smoke --timeout 10 /bin/true'
ssh "${opts[@]}" tester@127.0.0.1 'test -w /workspace/game; test -w /workspace/runs; run-game --lane smoke --timeout 10 /bin/true; ! run-game --lane gpu --timeout 10 /bin/true'
docker logs "$name"
