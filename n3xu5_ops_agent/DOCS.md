# HA OS installation
This release candidate supports amd64 and aarch64 HA OS installations. Home
Assistant Green uses aarch64; ordinary x86-64 Hyper-V/Proxmox HA OS guests use
amd64. Container-only HA installations use the standalone package instead.

## Before installation
1. Confirm a stable HA installation and obtain estate operator approval.
2. Confirm the dedicated estate Tailscale node and existing administrator-approved
   grants allow only the private Ops HTTPS endpoint. This add-on neither joins the
   tailnet nor edits policy; no public ingress or estate-to-estate access is required.
3. Obtain your operator-registered estate, tenant, connector ID, session reference,
   approved entity allowlist and verified private .ts.net HTTPS origin.
4. Arrange an approved protected-file delivery mechanism into this add-on's
   private /data/existing-connector-credential. It must hold the distinct machine
   session, with owner-only access. Do not reuse an operator/admin session.
   This file is not automatically provisioned by installing the repository.

## Install and configure
In Settings -> Apps/Add-ons -> Store -> repositories, add:
https://github.com/Darryl1987/ha-addons

Select N3xu5 Ops Agent 0.2.0-rc.2. Review and approve homeassistant_api before
installation. It exposes the HA REST proxy using Supervisor's runtime token;
Supervisor does not provide a native read-only scope. This client uses only
GET /core/api/config and GET /core/api/states/<allowlisted entity>.
Supervisor management API access, privileged capabilities, host networking,
published ports and host filesystem mounts are not requested.

Replace every generic option with the registered values. credential_ref is a
reference, not the session value. heartbeat_seconds defaults to 60 (15–300).
Keep credentials out of options, URLs, command arguments, logs and screenshots.
Deliver the machine session only through the approved private-file mechanism.
Do not copy or expose the Supervisor runtime token. Leave startup manual and
start only after all prerequisites are satisfied.

## Verify, maintain and stop
Verify a fresh authenticated heartbeat, expected HA version and only approved
entity samples in your private Ops dashboard. Missing telemetry is not successful
enrollment. A protected client cannot make its own backend registration.

Preserve /data/connector.sqlite3 when restarting/upgrading. Outbound messages are
persistent and deduplicated; outages use bounded backoff. Revoked/expired sessions
disable transmission durably. Stop on identity conflicts; do not delete state or
clear revocation flags to re-enroll. Renew or replace sessions only through the
operator's approved backend process.

One-click verification-code enrollment is not implemented. Actual HA OS secret
delivery, endpoint readiness and operator registration remain deployment gates.

Home Assistant format references:
https://developers.home-assistant.io/docs/apps/repository/
https://developers.home-assistant.io/docs/apps/configuration/
