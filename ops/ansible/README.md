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
- Clones/updates the Dirt repo on the edge host.
- Builds the OBSBOT camera daemon from the committed vendor SDK.
- Installs user systemd unit symlinks and enables linger.
- Does not enable or start `dirt-camera.service`.

## Secrets

Optional local secrets live in `ops/ansible/secrets.yml`. That file is
gitignored. Copy `ops/ansible/secrets.example.yml` and fill in local values when
you want Ansible to manage boot-time Wi-Fi config.

The same file can also point Ansible at local GitHub credential files. For a
private repo clone, prefer SSH and set `dirt_github_ssh_private_key_src`.
`gh` auth copying is supported, but optional; it gives the edge host the same
GitHub token stored in your local `~/.config/gh/hosts.yml`.
