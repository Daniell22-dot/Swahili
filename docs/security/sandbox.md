# Running Kiswahili Safely

Kiswahili programs are code. This page shows practical ways to run a `.kisw`
file you do not fully trust. None of these are enforced by the interpreter
yet; they are operating-system controls around it.

Always combine controls: an **unprivileged user**, a **sandbox or container**,
**resource limits**, and a **minimal environment**.

## The `--sandbox` flag

The interpreter has a first in-process safety switch:

```powershell
python -m swahili --sandbox program.kisw
```

It refuses to load the host-access modules `faili` (filesystem) and `mfumo`
(environment and directory listings). This is **defence in depth, not
isolation**: it does not stop resource exhaustion, and it does not replace an
OS sandbox. Pair it with the controls below.

To allow filesystem access inside one directory while keeping the rest of the
sandbox:

```powershell
python -m swahili --sandbox --allow-fs ./data program.kisw
```

`--allow-fs` is repeatable and resolves `..` and symlinks before checking, so
paths cannot escape the granted roots. With this flag `faili` is available,
but `mfumo` remains blocked. Note that module resolution only searches the
program's directory and explicit `--path DIR` entries; the current working
directory is never searched implicitly.

## General checklist

- [ ] Create/use a separate unprivileged account.
- [ ] Do not pass real secrets in the environment.
- [ ] Grant only the directory the program needs; mount it read-only if the
      program should not write.
- [ ] Cap CPU time, memory, and output.
- [ ] Do not run as administrator/root.
- [ ] Inspect the source first when you can.

## Linux

### `firejail` (quick, per-process)

```bash
firejail --private --net=none --rlimit-cpu=10 --rlimit-as=512M \
  python -m swahili program.kisw
```

`--private` gives a temporary home, `--net=none` removes network access, and
the rlimits bound CPU and memory.

### `systemd-run` (transient unit with limits)

```bash
systemd-run --user --scope -p MemoryMax=512M -p CPUQuota=50% \
  -p RuntimeMaxSec=30 python -m swahili program.kisw
```

### Container (recommended for repeatable isolation)

```bash
docker run --rm -it \
  --network none \
  --read-only \
  --tmpfs /tmp:size=64m \
  --memory 512m --cpus 0.5 --pids-limit 64 \
  -v "$PWD/program.kisw:/work/program.kisw:ro" \
  -w /work python:3.13-slim \
  sh -c "pip install --no-cache-dir /src && python -m swahili program.kisw"
```

Mount your package or copy the `swahili/` directory into the image. Keep the
program mount read-only and provide a writable scratch directory only if
needed.

### `ulimit` + `timeout` (minimal, no container)

```bash
( ulimit -t 10 -v 524288 -f 10240; timeout 15s python -m swahili program.kisw )
```

- `-t 10` CPU seconds
- `-v 524288` virtual memory in KB
- `-f 10240` max file size in blocks
- `timeout 15s` wall clock

### `unshare` (namespaces without Docker)

```bash
unshare --user --map-root-user --net --pid --fork \
  python -m swahili program.kisw
```

This is weaker than a container and easy to misconfigure; prefer a container.

## Windows

### Windows Sandbox

For one-off inspection, copy the program and the interpreter into Windows
Sandbox (a disposable desktop). Nothing persists after closing.

### Low-integrity / restricted token

Run the interpreter from a low-integrity process or a separate local account
with no access to your profile. Avoid running from an elevated terminal.

### WSL + container

The Linux container recipe above works well under WSL2 and is usually the
easiest way to get strong isolation on Windows.

### PowerShell resource bounds

PowerShell has no reliable per-process CPU/memory cap by itself. Use a
container, a virtual machine, or Windows Job Objects via a wrapper. At minimum
use `Start-Process -Wait` with a timeout and a dedicated low-privilege
account.

## macOS

### Container

Use the same Docker recipe; Docker Desktop on macOS runs a Linux VM, which
provides real isolation.

### `sandbox-exec` (legacy, profiling is deprecated)

`sandbox-exec` still exists but its profile language is deprecated and easy to
get wrong. Prefer a container or a separate user account.

## Reducing what the program can see

Even without a code sandbox, you can limit exposure:

- Start the interpreter with a scrubbed environment:

  ```bash
  env -i PATH="$PATH" HOME=/tmp python -m swahili program.kisw
  ```

- Run in an empty working directory. The current working directory is not on
  the module search path, but relative paths passed to `faili` still resolve
  against it.
- Remember that `mfumo.mazingira` can read any variable you leave in the
  environment.
- Remember that `faili` can read and write any path the user can reach unless
  you pass `--allow-fs`.

## What the interpreter does not do (yet)

- No environment allow-list (`mfumo` is blocked wholesale with `--sandbox`;
  per-variable grants are not implemented).
- No wall-clock timeout (the step budget bounds CPU work but not
  `wakati.sekunde` sleeps).
- No memory (RSS) limit; collection/repetition/range/exponent sizes and printed
  output are capped via `--max-collection` and `--max-output`.
- No signature or provenance check for local modules (built-ins now win over
  local files and the current directory is no longer searched, which closes
  the shadowing path).

Until those exist, the operating-system controls above are the security
boundary. See [`threat-model.md`](threat-model.md) for the hardening roadmap.
