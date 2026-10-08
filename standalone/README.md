# Home Assistant Container deployment
This package runs only the read-only N3xu5 client. It does not install or manage HA,
the Ops backend, Tailscale, credentials or access policy.

## Prepare
1. Use a dedicated estate Docker host with its existing approved Tailscale node
   and grants to the private .ts.net HTTPS Ops origin. Verify Docker bridge egress
   follows the host's tailnet route. Do not add host networking or public ingress
   to work around missing access.
2. Copy .env.example to .env and config/options.example.json to
   config/options.json. Set your existing estate HA Docker network, UID/GID and
   BUILD_ARCH (amd64 or aarch64). Replace all generic client IDs/reference,
   HTTPS Ops hostname and allowlisted entities with operator-approved values.
3. HA may be reached by verified HTTPS, or as http://homeassistant:8123 on that
   existing dedicated Docker network. Plain HTTP is accepted only for that local
   Docker name/port, never for Ops.
4. Create state/ and secrets/ with mode 0700 owned by the configured UID/GID.
   Supply the distinct approved machine session to secrets/ops-session and the
   dedicated HA session to secrets/ha-session with mode 0600. Use your approved
   secret-delivery mechanism; do not enter values in arguments/environment/options.
   Compose file secrets are read-only bind mounts: actual host file ownership
   controls readability by the configured container user.

## Build and start
Review docker compose config, then docker compose build. For ARM64 cross-builds
set the Docker target platform using your approved build environment; BUILD_ARCH
is metadata and does not select the runtime platform by itself.
After explicit estate activation approval:
docker compose up -d n3xu5-ops-agent

The client has no published ports, host/Docker socket mounts or capabilities.
It runs as the configured non-root UID/GID with a read-only root filesystem and
state confined to ./state. Automatic restart is disabled.

Only GET /api/config and GET /api/states/<allowlisted entity> are available.
HA session authority can be broader; client code enforces the fixed read-only
routes. No secret-issuing or verification-code enrollment endpoint is implemented.

## Verify and stop
Check heartbeat, HA version, allowlisted telemetry and tenant assignment in the
private dashboard. Use docker compose stop to stop; preserve state and protected
files. Revocation/expiry disables transmission. Never clear that state to bypass
revocation or relax TLS/network checks.
