"""Standalone Docker client; fixed read-only HA routes, file-only secrets."""
import http.client
import json
import os
from pathlib import Path
import ssl
import time
from urllib.parse import urlsplit
from controller.n3xu5_ops.connector import ConnectorConfig,ConnectorError,OutboundConnector,HttpsOpsTransport,tailnet_origin

class ContainerReadOnlyReader:
    def __init__(self,origin,credential_file,allowlist):
        parsed=urlsplit(origin)
        if (not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/')
                or parsed.query or parsed.fragment
                or not (parsed.scheme=='https' or (parsed.scheme=='http' and parsed.hostname=='homeassistant' and parsed.port==8123))):
            raise ConnectorError('verified HA HTTPS or local homeassistant:8123 required')
        self.origin=parsed;self.credential_file=Path(credential_file);self.allowlist=frozenset(allowlist)
    def __call__(self,kind,entity):
        if kind=='info': path='/api/config'
        elif kind=='state' and entity in self.allowlist: path='/api/states/'+entity
        else: raise ConnectorError('HA route denied')
        connection=None
        try:
            token=self.credential_file.read_text().strip()
            if not token or '\n' in token or '\r' in token: raise ConnectorError('protected HA session required')
            if self.origin.scheme=='https':
                connection=http.client.HTTPSConnection(self.origin.hostname,self.origin.port,timeout=5,context=ssl.create_default_context())
            else: connection=http.client.HTTPConnection(self.origin.hostname,self.origin.port,timeout=5)
            connection.request('GET',path,headers={'Authorization':'Bearer '+token})
            response=connection.getresponse();raw=response.read(65537)
            if response.status!=200 or len(raw)>65536: raise ConnectorError('HA response rejected')
            data=json.loads(raw)
            if kind=='info': return {'ha_version':str(data.get('version','unknown'))}
            result={'entity_id':data['entity_id'],'state':data['state']}
            battery=data.get('attributes',{}).get('battery_level')
            if type(battery) in (int,float) and 0<=battery<=100: result['battery']=battery
            return result
        except Exception: raise ConnectorError('read-only HA acquisition unavailable') from None
        finally:
            if connection is not None: connection.close()

def main():
    os.umask(0o077)
    options=json.loads(Path('/config/options.json').read_text())
    config=ConnectorConfig(**{**options['connector'],'entity_allowlist':tuple(options['connector']['entity_allowlist'])})
    tailnet_origin(config.server_origin)
    def resolver(ref):
        if ref!=config.credential_ref: raise ConnectorError('credential reference unavailable')
        return Path('/run/secrets/ops_session').read_text().strip()
    reader=ContainerReadOnlyReader(options['ha_origin'],'/run/secrets/ha_session',config.entity_allowlist)
    connector=OutboundConnector(config,'/data/connector.sqlite3',reader,HttpsOpsTransport(config,resolver),lambda:int(time.time()))
    last=-config.heartbeat_seconds
    while True:
        try:
            now=int(time.time())
            if now-last>=config.heartbeat_seconds:
                connector.heartbeat();connector.telemetry();last=now
            result=connector.flush_once()
            if result['state'] in ('REVOKED','REVOKED_OR_EXPIRED'): return
        except ConnectorError: print('Read-only acquisition unavailable; retained local diagnostics',flush=True)
        time.sleep(2)
if __name__=='__main__': main()
