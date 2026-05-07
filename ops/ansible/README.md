# Dirt Ansible

Minimal host bootstrap for Dirt controller machines.

## Run

```bash
uvx --from ansible-core ansible-playbook -i ops/ansible/inventory.yml ops/ansible/site.yml --limit dirt2
```

The playbook expects key-based SSH for `akcom` and passwordless sudo on the
target. It installs only the shared base packages plus hardware-edge tooling;
database, web-build, and hosted-deploy tools stay on the primary box unless a
host is explicitly assigned that role later.

## Scope

- Keeps the `akcom` SSH key authorized.
- Enforces Dirt's SSH lockdown drop-in.
- Keeps passwordless sudo for `akcom`.
- Installs Python/build/video/admin packages needed by edge services.
- Installs `uv` at `/home/akcom/.local/bin/uv`, matching the systemd units.
