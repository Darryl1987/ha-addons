# N3xu5 Ops — Home Assistant Agent

Public client-side distribution repository for **N3xu5 Ops Agent**.

> **Preparation in progress:** The app package and release images have not yet been published here. Do not install this repository on a live Home Assistant estate until a validated release is available.

## Intended installation

For supported **Home Assistant OS** installations (including Home Assistant Green, and HA OS virtual machines on Proxmox or Hyper-V), the agent will be distributed through the normal Home Assistant custom app/add-on repository flow.

Repository URL: `https://github.com/Darryl1987/ha-addons`

**Home Assistant Container** deployments do not have the Supervisor app store. They will use the separately supplied Docker/Compose packaging for the same N3xu5 agent.

## Connection and privacy

- Clients first join the approved N3xu5 Tailscale tailnet.
- Enrollment uses an operator-issued, short-lived verification code and a revocable per-estate identity.
- Estate access is restricted by Tailscale policy; estate-to-estate access is not required.
- Telemetry is collected through narrowly scoped read operations. The HA OS app requests `homeassistant_api`, which grants broader API authority than the agent's intended read-only behavior; verify and approve this before installing.
- No public backend, private server code, operator credentials, client estate details or Lisa Engineering Factory source belongs in this repository.

## Status

The public GitHub structure is being prepared. The actual validated client package, installation documentation and release images will be added following a disclosure review. Until then, this is **not an installable release**.
