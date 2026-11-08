# Vibecopter RunPod Linux test box

Standalone **public infrastructure**, independently built from the private game.
Ubuntu 22.04 / x86-64, SSH, native C++/Python tooling, Vulkan diagnostics, FFmpeg
and a non-root Unreal process runner. No game, assets, Unreal Engine, Epic SDK,
Windows build, Proton, credentials or NVIDIA kernel driver is baked in.

## Start a box

1. Create a **RunPod GPU Pod** using a custom template, not Serverless.
2. Image: `ghcr.io/brennan-vanderlaan/vibecopter-runpod:latest`.
   Prefer the immutable `image@sha256:...` from the successful GitHub Actions
   run's summary / `image-reference` artifact for reproducibility.
3. Expose **TCP 22**. No HTTP ports or public desktop services are needed.
   Leave the Docker command/entrypoint override empty.
4. Environment: `PUBLIC_KEY` = your SSH **public** key (RunPod's SSH key injection
   can supply this); `NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,video,display`.
   If the key is absent, the container stays alive for RunPod's authenticated
   SSH gateway, but its own port 22 server remains disabled. Startup failures
   also enter a logged recovery mode rather than crash-looping.
   Optionally set `TESTBOX_IMAGE_REFERENCE` to the exact image digest for receipts.
5. Mount a persistent volume at `/workspace`. Suggested first bring-up box:
   NVIDIA RTX 3060/3090/4090-class GPU with Vulkan graphics support, at least
   8 vCPU, 32 GB RAM, 30 GB container disk and 100 GB persistent storage for
   packages, source and evidence. A full Unreal source/toolchain build needs
   substantially more storage/RAM; size that separately before downloading it.
   These are provisioning suggestions, not tested game minimum specifications.
6. Start the pod and use its Connect panel's **direct TCP SSH** host/port.
   `root` is available for provisioning; `tester` uses the same public key and is
   the non-root game user. Password authentication is disabled. No private key
   belongs in the image, template, repository or environment.

```sh
ssh -i /path/to/key -p PORT root@HOST
python3 /opt/vibecopter/probe.py
```

`nvidia-smi` and `vulkaninfo --summary` must both work, with physical NVIDIA GPU0.
Driver injection requires NVIDIA's graphics capability, not just CUDA/compute.
This image provides an offscreen Vulkan path, not an interactive remote desktop.
Xvfb/Mesa are available for diagnostics; software Vulkan never passes the GPU gate.
If host driver injection lacks graphics, select a graphics-capable pod/host;
do not install a kernel driver inside the container to disguise the failure.

## Transfer private inputs at runtime

Upload source/packages using SCP/rsync over SSH, or download through a private,
authorized artifact channel. Do not put signed download URLs or tokens in the
runner arguments (they are recorded). Keep secrets in session-only tooling.

```sh
# Run locally; replace the placeholder path and RunPod host/port.
rsync -a -e 'ssh -i /path/to/key -p PORT' /local/LinuxPackage/ tester@HOST:/workspace/game/
# Or upload private source to /workspace/src/ for the existing portable test runner.
```

Native Linux package availability is a separate gate. This image does not turn a
Windows EXE into a Linux binary, supply Epic access or include the UE 5.4 Linux
toolchain. Install privately licensed build tools on the volume only through
their authorized acquisition flow. Generic distro clang is for portable tests,
not a substitute for the engine's required toolchain.

## Run and collect evidence

Use the real ELF Shipping/Development executable, not a root-only wrapper.
Ensure its execute bit is set and the whole package is readable by `tester`.
Start with process smoke; then require real Vulkan:

```sh
run-game --lane smoke --timeout 180 /workspace/game/ExtractionFlyer/Binaries/Linux/ExtractionFlyer -- -SmokeTest
run-game --lane gpu --timeout 180 /workspace/game/ExtractionFlyer/Binaries/Linux/ExtractionFlyer -- -ResX=1280 -ResY=800
```

The game must exit within the timeout; a normal interactive session reaching the
timeout is recorded as failure, not acceptance. Use an actual finite game scenario
when available. NullRHI may not support menu-driven game smoke; keep that failure.
GPU lane adds `-vulkan -RenderOffscreen -graphicsadapter=0`; actual Unreal support
for this path remains to be tested. No display or audio device is promised.

Every invocation creates a unique `/workspace/runs/<32-hex-id>/` containing
`receipt.json`, `hardware.json`, `console.log`, a separate profile and `Unreal.log`
when produced. Record the full package manifest/hash and scenario with these
receipts; the runner hashes the invoked executable only. `PROCESS_EXIT_ZERO`
means process health, **not** gameplay success or proof the game used Vulkan.
Inspect the real RHI log and scenario evidence before accepting GPU rendering.
Screenshots/video/performance captures must come from the game/explicit capture
commands; the runner does not fabricate them. No automated FPS, visual, co-op,
SteamOS, Steam Deck, GTX 1080 or controller acceptance is claimed.

Download `/workspace/runs/` before destroying storage. Stop the pod in RunPod to
end compute billing; a stopped pod's retained volume may still incur storage
cost. Terminate/delete storage only after retrieving the evidence you need.

## Build and maintenance

Push to `main` or dispatch **Test and publish RunPod image**. GitHub Actions builds
`linux/amd64`, tests SSH/key handling, non-root execution, failure/timeout receipts
and refusal of CPU Vulkan as GPU, then publishes `latest` and `sha-<full commit>`
to GHCR. Tags `v*` also publish the matching version. PRs test without publishing.
An independent fresh-runner job pulls the exact published digest without registry
credentials and repeats the container/SSH tests, catching visibility regressions.
First publication defaults private on GHCR: change the **container package**
visibility to Public once, then verify an anonymous pull. Repository visibility
alone is insufficient. No registry secret is needed: publishing uses the scoped
workflow `GITHUB_TOKEN`.

Base image and Actions are commit/digest pinned. Ubuntu packages resolve at build
time to receive security updates; this is not byte-for-byte apt reproducibility.
Each build exports the installed dependency inventory, SBOM and provenance.
Rebuild periodically and after security fixes; update the base digest and action
pins deliberately. Use a digest when repeating an experiment.

```sh
docker build -t testbox:local .
bash ci-smoke.sh testbox:local
```

## References

- [RunPod's official minimal pod image contract](https://github.com/runpod/runpod-plugins-official/tree/main/plugins/runpod/skills/runpod/golden-paths/22-minimal-pod-image)
- [NVIDIA driver capabilities](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/docker-specialized.html)
- [GHCR publishing, visibility and digest pulls](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
