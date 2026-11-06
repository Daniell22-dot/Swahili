# Security Policy

Kiswahili is an interpreter: **running a `.kisw` file executes code with the
privileges of the Python process that hosts it.** Treat `.kisw` programs and
modules exactly like executables you did not compile yourself.

The full analysis is in [`docs/security/threat-model.md`](docs/security/threat-model.md).

## Supported versions

| Version | Security fixes |
|---------|----------------|
| 0.1.x   | yes            |

## Reporting a vulnerability

Please do **not** open a public issue for a security problem.

- Email the maintainers with a description, a minimal reproducing `.kisw`
  program (or Python snippet), the affected version, and the impact you
  believe it has.
- Give us a reasonable window to investigate and ship a fix before public
  disclosure.
- We will credit reporters who want to be credited.

If you are unsure whether something is a security issue, report it privately
and let us triage it.

## Running untrusted code safely

The current release does **not** sandbox programs. Before running code you do
not trust:

1. Use a throwaway machine, container, or OS sandbox.
2. Run as a **low-privileged user**, not as an administrator/root.
3. Do not expose real environment variables (cloud keys, tokens).
4. Mount only the directory that is needed, read-only if possible.
5. Apply CPU, memory, and wall-clock limits.

See [`docs/security/sandbox.md`](docs/security/sandbox.md) for recipes.

As a first line of defence, pass `--sandbox` to block the host-access modules
`faili` and `mfumo`:

```powershell
python -m swahili --sandbox program.kisw
```

This is defence in depth, not OS isolation. It does not stop CPU/memory
exhaustion and does not replace a container or low-privileged account.

## Known risk areas (summary)

| Area | Risk |
|------|------|
| `faili` module | full read/write/delete on the host filesystem unless `--allow-fs DIR` confines it |
| `mfumo` module | exposes environment variables and directory listings |
| `wakati.sekunde` | arbitrary sleeps; used for denial of service |
| `kansa` module | **not** cryptographically secure; use `siri` for tokens and keys |
| `tumia` resolution | built-ins win and the current directory is not searched; explicit `--path DIR` directories are trusted |
| loops / big integers / repetition | no resource budget; memory and CPU exhaustion |
| diagnostics | errors can echo source lines into logs |

## Security design rules for contributors

- Never use Python `eval`/`exec` on Kiswahili source or user data.
- Do not add shell/`subprocess` execution without an explicit capability and a
  threat-model update.
- New host capabilities must be opt-in and denied by default.
- Every unbounded primitive needs a limit or a budget.
- Do not make module or file resolution depend on an attacker-controlled
  working directory.
- Keep runtime dependencies at zero unless there is a strong, reviewed reason.

## Hardening roadmap

The threat model lists the path from the current "vulnerable by design for
untrusted input" posture to a capability-based, secure-by-design interpreter.
Highlights: capability flags for filesystem/environment, path confinement,
deterministic module resolution, resource budgets, a sandbox profile, and a
cryptographic randomness module.
