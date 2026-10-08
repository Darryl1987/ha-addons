# 0.2.0-rc.3
- Support private Tailscale HTTPS port 8443 alongside 443, without relaxing TLS or address verification.
- Match the connector destination to the approved origin port.
- No changes to read-only HA routes or protected-file provisioning.

# 0.2.0-rc.2
- HA OS and standalone client distributions.
- Private Tailscale destination pinning with TLS verification.
- Fixed read-only HA routes, persistent outbox, expiry/revocation handling.
- Consistent internal agent version and regenerated client source hashes.
- Manual protected-file provisioning; verification-code enrollment is not implemented.
