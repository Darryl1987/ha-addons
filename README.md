# N3xu5 Ops Agent
Client-only release candidate **0.2.0-rc.3** for Home Assistant OS and Home Assistant
Container. This repository contains the outbound agent, add-on metadata,
Dockerfiles and Compose package. It contains no backend or operator sessions.

Repository URL: https://github.com/Darryl1987/ha-addons

## Packages
- **n3xu5_ops_agent/**: HA OS custom add-on for amd64 and aarch64, including
  Green and supported HA OS virtual machines on Hyper-V or Proxmox.
- **standalone/**: Docker/Compose client for Home Assistant Container.

HA OS builds locally from the provided Dockerfile; no prebuilt registry image is
advertised. Client metadata, Docker labels and heartbeat version are 0.2.0-rc.3.
Each package includes SHA-256 hashes for its shipped client modules.

## Enrollment prerequisites
A dedicated estate Tailscale node, administrator-approved access to only the
private Ops HTTPS origin, an operator-registered estate/connector identity, and
a distinct protected connector session are required before client start.

**Protected-file provisioning is required. One-click verification-code enrollment
is not implemented.** No code-based pairing, token-creation endpoint, tailnet
join key or automatic policy update is supplied by this client.

Ops origins must be verified HTTPS .ts.net names. The agent rejects public or
loopback destinations, checks Tailscale address ranges, pins the checked address,
validates hostname/TLS certificates and rejects redirects. Public ingress and
Funnel are not supported. Generic sample settings must be replaced with the
operator-approved values; sample hosts/entities are not operational endpoints.

The agent's HA operations are fixed GET requests for config/version and the
explicit entity allowlist. No services, websocket actions, configuration writes
or backup operations are available. HA OS homeassistant_api permission and HA
Container credentials can have broader authority than read-only; the restriction
is enforced in this client code, not a claim of a native read-only token scope.

See [HA OS instructions](n3xu5_ops_agent/DOCS.md) and
[Container instructions](standalone/README.md). Installing a release candidate
requires your estate operator's approval and a stable HA installation.

Private HTTPS ports 443 and 8443 are supported. Port 8443 allows an isolated
client endpoint when 443 is already used. Other ports remain denied; TLS,
Tailscale address checks and estate authentication are unchanged. Use only your
operator-approved origin, including its port. Code-based enrollment is not implemented.
