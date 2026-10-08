"""HA add-on entrypoint. Install/activation is a separate operator boundary."""
import json
import os
from pathlib import Path
import time
from controller.n3xu5_ops.connector import ConnectorConfig,OutboundConnector,HttpsOpsTransport,SupervisorReadOnlyReader,ConnectorError,tailnet_origin

def main():
    os.umask(0o077)
    options=json.loads(Path('/data/options.json').read_text())
    config=ConnectorConfig(**{**options,'entity_allowlist':tuple(options['entity_allowlist'])})
    tailnet_origin(config.server_origin)
    # File reference is pre-provisioned outside this package; no credential is
    # generated, mounted or created automatically by the connector.
    def resolver(ref):
        expected=config.credential_ref
        if ref!=expected: raise ConnectorError('credential reference unavailable')
        return Path('/data/existing-connector-credential').read_text().strip()
    reader=SupervisorReadOnlyReader(os.environ['SUPERVISOR_TOKEN'],config.entity_allowlist)
    connector=OutboundConnector(config,'/data/connector.sqlite3',reader,HttpsOpsTransport(config,resolver),lambda:int(time.time()))
    last=-config.heartbeat_seconds
    while True:
        now=int(time.time())
        try:
            if now-last>=config.heartbeat_seconds:
                connector.heartbeat(); connector.telemetry(); last=now
            result=connector.flush_once()
            if result['state'] in ('REVOKED','REVOKED_OR_EXPIRED'): return
        except ConnectorError: print('Read-only acquisition unavailable; retained local diagnostics',flush=True)
        time.sleep(2)

if __name__=='__main__': main()
