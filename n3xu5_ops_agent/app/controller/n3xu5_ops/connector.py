from contextlib import closing
"""Outbound-only read-only HA connector, persistent outbox and bounded backoff."""
from dataclasses import dataclass
from pathlib import Path
import http.client
import json
import re
import sqlite3
import ssl
import socket
import ipaddress
from urllib.parse import urlsplit

class ConnectorError(ValueError): pass
VERSION='0.2.0-rc.3'

@dataclass(frozen=True)
class ConnectorConfig:
    server_origin: str
    estate: str
    tenant: str
    connector: str
    credential_ref: str
    entity_allowlist: tuple[str,...]
    heartbeat_seconds: int=60
    def __post_init__(self):
        parsed=urlsplit(self.server_origin)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.port not in (None,443,8443): raise ConnectorError('HTTPS origin required')
        for value in (self.estate,self.tenant,self.connector):
            if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}',value): raise ConnectorError('invalid identity')
        if not re.fullmatch(r'existing:[a-z0-9_-]{1,64}',self.credential_ref): raise ConnectorError('existing credential reference required')
        if type(self.heartbeat_seconds) is not int or not 15<=self.heartbeat_seconds<=300: raise ConnectorError('invalid heartbeat interval')
        if not self.entity_allowlist or len(self.entity_allowlist)>1000 or len(set(self.entity_allowlist))!=len(self.entity_allowlist): raise ConnectorError('bounded unique allowlist required')
        for entity in self.entity_allowlist:
            if not isinstance(entity,str) or not re.fullmatch(r'[a-z0-9_]+\.[a-z0-9_]+',entity) or len(entity)>128: raise ConnectorError('invalid entity')

def tailnet_origin(origin):
    parsed=urlsplit(origin)
    if (parsed.scheme!='https' or not parsed.hostname or not parsed.hostname.endswith('.ts.net')
            or parsed.username or parsed.password or parsed.path not in ('','/')
            or parsed.query or parsed.fragment or parsed.port not in (None,443,8443)):
        raise ConnectorError('private Tailscale HTTPS origin required')
    return parsed.hostname

class TailnetHTTPSConnection(http.client.HTTPSConnection):
    """Pin a verified tailnet address while preserving hostname TLS checks."""
    def connect(self):
        hostname=tailnet_origin('https://'+self.host+':'+str(self.port))
        answers=socket.getaddrinfo(hostname,self.port,type=socket.SOCK_STREAM)
        allowed=(ipaddress.ip_network('100.64.0.0/10'),ipaddress.ip_network('fd7a:115c:a1e0::/48'))
        if not answers: raise ConnectorError('private Tailscale address unavailable')
        for answer in answers:
            address=ipaddress.ip_address(answer[4][0])
            if not any(address.version==network.version and address in network for network in allowed):
                raise ConnectorError('non-Tailscale destination denied')
        raw=socket.create_connection((answers[0][4][0],self.port),self.timeout)
        try: self.sock=self._context.wrap_socket(raw,server_hostname=hostname)
        except Exception: raw.close();raise

class HttpsOpsTransport:
    def __init__(self,config,resolver): self.config=config; self.resolver=resolver
    def __call__(self,kind,payload):
        if kind not in ('heartbeat','telemetry'): raise ConnectorError('outbound route denied')
        hostname=tailnet_origin(self.config.server_origin); connection=None
        try:
            token=self.resolver(self.config.credential_ref)
            if not isinstance(token,str) or not token or '\r' in token or '\n' in token: raise ConnectorError('existing credential unavailable')
            raw=json.dumps(payload,allow_nan=False).encode()
            if len(raw)>262144: raise ConnectorError('payload too large')
            connection=TailnetHTTPSConnection(hostname,port=urlsplit(self.config.server_origin).port or 443,timeout=5,context=ssl.create_default_context())
            connection.request('POST','/v1/connector/'+kind,body=raw,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
            response=connection.getresponse(); body=response.read(65537)
            if len(body)>65536: raise ConnectorError('oversized server response')
            if 300<=response.status<400: raise ConnectorError('redirect denied')
            value=json.loads(body)
            return response.status,value
        except ConnectorError: raise
        except Exception: raise ConnectorError('secure server transport unavailable') from None
        finally:
            if connection is not None: connection.close()

class OutboundConnector:
    def __init__(self,config,path,ha_reader,transport,clock):
        self.config=config; self.path=Path(path); self.reader=ha_reader; self.transport=transport; self.clock=clock
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript('''CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE IF NOT EXISTS outbox(id INTEGER PRIMARY KEY,kind TEXT,payload TEXT,attempts INTEGER DEFAULT 0,due INTEGER,state TEXT DEFAULT 'PENDING');
                CREATE TABLE IF NOT EXISTS diagnostics(id INTEGER PRIMARY KEY,at INTEGER,kind TEXT,detail TEXT);''')
            binding=json.dumps({'estate':config.estate,'tenant':config.tenant,'connector':config.connector},sort_keys=True)
            contract=json.dumps({'server_origin':config.server_origin,'credential_ref':config.credential_ref,'entity_allowlist':config.entity_allowlist},sort_keys=True)
            prior=db.execute("SELECT value FROM meta WHERE key='identity'").fetchone()
            if prior and prior[0]!=binding: raise ConnectorError('persistent estate identity conflicts')
            db.execute("INSERT OR IGNORE INTO meta VALUES ('identity',?)",(binding,))
            existing_contract=db.execute("SELECT value FROM meta WHERE key='configuration'").fetchone()
            if existing_contract and existing_contract[0]!=contract: raise ConnectorError('persistent connector configuration conflicts')
            db.execute("INSERT OR IGNORE INTO meta VALUES ('configuration',?)",(contract,))
            db.execute("INSERT OR IGNORE INTO meta VALUES ('revoked','false')")
    def _disabled(self,db): return db.execute("SELECT value FROM meta WHERE key='revoked'").fetchone()[0]=='true'
    def _queue(self,kind,data):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            if self._disabled(db): raise ConnectorError('connector offboarded')
            if db.execute("SELECT COUNT(*) FROM outbox WHERE state='PENDING'").fetchone()[0]>=1000: raise ConnectorError('outbox full; preserve unsent history')
            key='sequence-'+kind; row=db.execute('SELECT value FROM meta WHERE key=?',(key,)).fetchone(); seq=int(row[0])+1 if row else 0
            db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',(key,str(seq)))
            payload={'estate':self.config.estate,'tenant':self.config.tenant,'connector':self.config.connector,'sequence':seq,'message_id':kind+'-'+str(seq),'observed_at':self.clock(),**data}
            raw=json.dumps(payload,allow_nan=False)
            if len(raw.encode())>262144: raise ConnectorError('payload too large')
            db.execute('INSERT INTO outbox(kind,payload,due) VALUES (?,?,?)',(kind,raw,self.clock()))
        return payload
    def heartbeat(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            if self._disabled(db): raise ConnectorError('connector offboarded')
            if db.execute("SELECT COUNT(*) FROM outbox WHERE state='PENDING'").fetchone()[0]>=1000: raise ConnectorError('outbox full')
        info=self.reader('info',None)
        allowed={key:info[key] for key in ('ha_version','uptime','host_health','backup_state') if key in info}
        return self._queue('heartbeat',{'version':VERSION,**allowed})
    def telemetry(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            if self._disabled(db): raise ConnectorError('connector offboarded')
            if db.execute("SELECT COUNT(*) FROM outbox WHERE state='PENDING'").fetchone()[0]>=1000: raise ConnectorError('outbox full')
        entities=[]
        for entity in self.config.entity_allowlist:
            row=self.reader('state',entity)
            if not isinstance(row,dict) or row.get('entity_id')!=entity or not isinstance(row.get('state'),str) or len(row['state'])>256: raise ConnectorError('HA entity response denied')
            sample={'entity_id':entity,'state':row['state']}
            for key in ('battery','last_changed'):
                if key in row: sample[key]=row[key]
            entities.append(sample)
        return self._queue('telemetry',{'entities':entities,'issues':[]})
    def flush_once(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            if self._disabled(db): return {'state':'REVOKED','calls':0}
            row=db.execute("SELECT id,kind,payload,attempts FROM outbox WHERE state='PENDING' AND due<=? ORDER BY id LIMIT 1",(self.clock(),)).fetchone()
        if row is None: return {'state':'IDLE','calls':0}
        try: status,response=self.transport(row[1],json.loads(row[2]))
        except Exception: status=503; response={}
        with closing(sqlite3.connect(self.path)) as db, db:
            if status==200 and isinstance(response,dict) and response.get('accepted') is True:
                db.execute("UPDATE outbox SET state='DELIVERED' WHERE id=?",(row[0],)); result='DELIVERED'
            elif status in (401,403):
                db.execute("UPDATE meta SET value='true' WHERE key='revoked'")
                db.execute("UPDATE outbox SET state='HELD' WHERE state='PENDING'"); result='REVOKED_OR_EXPIRED'
            elif status in (400,409,413,415):
                db.execute("UPDATE outbox SET state='REJECTED' WHERE id=?",(row[0],)); result='REJECTED'
            else:
                delay=min(300,2**min(row[3]+1,9))
                db.execute('UPDATE outbox SET attempts=attempts+1,due=? WHERE id=?',(self.clock()+delay,row[0])); result='BACKOFF'
            db.execute('INSERT INTO diagnostics(at,kind,detail) VALUES (?,?,?)',(self.clock(),result,'message '+str(row[0])))
        return {'state':result,'calls':1}
    def offboard(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("UPDATE meta SET value='true' WHERE key='revoked'")
            db.execute("UPDATE outbox SET state='HELD' WHERE state='PENDING'")
            db.execute('INSERT INTO diagnostics(at,kind,detail) VALUES (?,?,?)',(self.clock(),'OFFBOARDED','local transmission disabled; history retained'))

class SupervisorReadOnlyReader:
    """Fixed local Supervisor API paths, using its existing runtime token.

    No commands, websocket actions, config writes, backup creation or services.
    Local supervisor HTTP is internal to the add-on network; outbound Ops uses
    HTTPS. Do not expose this reader as a network endpoint.
    """
    def __init__(self,token,allowlist): self.token=token; self.allowlist=frozenset(allowlist)
    def __call__(self,kind,entity):
        if kind=='info': path='/core/api/config'
        elif kind=='state' and entity in self.allowlist: path='/core/api/states/'+entity
        else: raise ConnectorError('HA route denied')
        connection=http.client.HTTPConnection('supervisor',timeout=5)
        try:
            connection.request('GET',path,headers={'Authorization':'Bearer '+self.token})
            response=connection.getresponse(); raw=response.read(65537)
            if response.status!=200 or len(raw)>65536: raise ConnectorError('HA response rejected')
            data=json.loads(raw)
            if kind=='info': return {'ha_version':str(data.get('version','unknown'))}
            result={'entity_id':data['entity_id'],'state':data['state']}
            attributes=data.get('attributes',{})
            battery=attributes.get('battery_level')
            if type(battery) in (int,float) and 0<=battery<=100: result['battery']=battery
            return result
        except Exception: raise ConnectorError('read-only HA acquisition unavailable') from None
        finally: connection.close()
