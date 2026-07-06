import socket,base64,os,json,struct
def connect(host="10.10.0.5",port=8123):
    s=socket.create_connection((host,port),timeout=15)
    key=base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET /api/websocket HTTP/1.1\r\nHost:{host}:{port}\r\nUpgrade:websocket\r\n"
        f"Connection:Upgrade\r\nSec-WebSocket-Key:{key}\r\nSec-WebSocket-Version:13\r\n\r\n").encode())
    b=b""
    while b"\r\n\r\n" not in b: b+=s.recv(4096)
    return s
def _send(s,obj):
    d=json.dumps(obj).encode(); m=os.urandom(4); h=bytearray([0x81]); n=len(d)
    if n<126: h.append(0x80|n)
    elif n<65536: h.append(0x80|126); h+=struct.pack(">H",n)
    else: h.append(0x80|127); h+=struct.pack(">Q",n)
    h+=m; s.sendall(bytes(h)+bytes(b^m[i%4] for i,b in enumerate(d)))
def _recv(s):
    def rd(n):
        b=b""
        while len(b)<n: b+=s.recv(n-len(b))
        return b
    b0,b1=rd(2); ln=b1&0x7f
    if ln==126: ln=struct.unpack(">H",rd(2))[0]
    elif ln==127: ln=struct.unpack(">Q",rd(8))[0]
    return json.loads(rd(ln).decode())
class HA:
    def __init__(self,tok):
        self.s=connect(); self.id=0
        assert _recv(self.s)["type"]=="auth_required"
        _send(self.s,{"type":"auth","access_token":tok})
        assert _recv(self.s)["type"]=="auth_ok","auth failed"
    def cmd(self,**kw):
        self.id+=1; kw["id"]=self.id; _send(self.s,kw)
        while True:
            m=_recv(self.s)
            if m.get("id")==self.id and m.get("type")=="result": return m
