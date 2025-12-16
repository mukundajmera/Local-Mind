# Scripts Handbook

> Submodule of Local Mind. Review `../AGENTS.md` at the repo root for global standards and deployment orchestration.

## Directory Purpose
- Contains automation scripts used for bootstrapping, runtime supervision, and environment setup:
  - `init.sh` – brings up core stack, validates prerequisites, creates volume directories.
  - `start_backend.sh` / `start_frontend.sh` – convenience wrappers for service-specific dev runs.
  - `setup/` – OS-specific installers (WSL2, macOS).
  - `watchdog.sh` – monitors compose services and restarts unhealthy containers.

## Editing Guidelines
- Preserve strict mode (`set -e`) and existing colorized logging helpers.
- Maintain cross-shell compatibility (bash and zsh). Test scripts on macOS and Linux where feasible.
- Document non-idempotent behavior inline if deviations from README/SETUP instructions are required.
- Avoid hardcoding secrets or environment-specific paths; source values from `.env` or script arguments.

## Validation
- Run `shellcheck` before submitting significant changes.
- For bootstrap scripts, perform dry runs in clean environments (fresh WSL2/VM) when practical.
- Update `README.md`, `SETUP.md`, and root `AGENTS.md` when script behavior changes user onboarding steps.

## Integration Notes
- `init.sh` auto-detects container runtime (podman, nerdctl, docker). Ensure logic remains in sync with infrastructure handbook.
- Scripts creating directories under `../data` must keep volume expectations consistent with compose definitions.
- When introducing new scripts, add usage instructions to the README and consider extending this handbook.

## Git Practices
- Keep scripts executable (`chmod +x`).
- Do not add platform-specific binaries. If compiling utilities is necessary, store them outside this repo or document build steps.

## Escalation
- For changes affecting GPU detection or compose orchestration, coordinate with infrastructure owners identified in `../REPAIR_LOG.md`.
- Report regressions in onboarding flow to documentation maintainers and update SETUP/README promptly.

Use this handbook to ensure automation scripts remain dependable and consistent with repository standards.
