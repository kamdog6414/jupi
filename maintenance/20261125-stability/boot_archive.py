#!/usr/bin/python3
"""Bounded newc archive inspection and private initramfs key supplement.

No archive is extracted and no member is executed. Key bytes are never returned
in a report. Every original archive member must remain byte-for-byte identical.
"""
import gzip
import hashlib
import io
from pathlib import PurePosixPath
import stat

MAX_COMPRESSED=32*1024**2
MAX_ARCHIVE=64*1024**2
KEY_NAME='key/eap_hdd_key.bin'


def digest(raw):return hashlib.sha256(raw).hexdigest()


def unpack(raw):
    if len(raw)>MAX_COMPRESSED:raise ValueError('Compressed archive bound')
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as f:data=f.read(MAX_ARCHIVE+1)
    if len(data)>MAX_ARCHIVE:raise ValueError('Expanded archive bound')
    return data


def entries(data):
    offset=0;seen=set();count=0
    while offset+110<=len(data):
        start=offset;header=data[offset:offset+110]
        if header[:6]!=b'070701':raise ValueError('Expected newc archive')
        if any(c not in b'0123456789abcdefABCDEF' for c in header[6:]):raise ValueError('Nonhexadecimal header')
        try:fields=[int(header[i:i+8],16) for i in range(6,110,8)]
        except ValueError as e:raise ValueError('Invalid newc header') from e
        size,namesize=fields[6],fields[11]
        if not 1<=namesize<=4096 or offset+110+namesize>len(data):raise ValueError('Invalid member name size')
        name_raw=data[offset+110:offset+110+namesize]
        if name_raw[-1:]!=b'\0' or b'\0' in name_raw[:-1]:raise ValueError('Invalid member name terminator')
        name=name_raw[:-1].decode('utf-8');normal=name
        while normal.startswith('./'):normal=normal[2:]
        if not normal:normal='.'
        if normal.startswith('/') or '..' in PurePosixPath(normal).parts:raise ValueError('Unsafe member name')
        if normal in seen:raise ValueError('Duplicate member name')
        seen.add(normal);count+=1
        if count>4096:raise ValueError('Member count bound')
        body=(offset+110+namesize+3)&~3;end=(body+size+3)&~3
        if end>len(data):raise ValueError('Truncated member')
        item={'name':normal,'raw_name':name,'offset':start,'body':body,'size':size,'end':end,'ino':fields[0],'mode':fields[1],'uid':fields[2],'gid':fields[3]}
        yield item;offset=end
        if normal=='TRAILER!!!':
            if size or any(data[end:]):raise ValueError('Unexpected trailing archive data')
            return
    raise ValueError('Missing archive trailer')


def member(name,body,mode,ino):
    raw_name=name.encode()+b'\0'
    fields=[ino,mode,0,0,2 if stat.S_ISDIR(mode) else 1,0,len(body),0,0,0,0,len(raw_name),0]
    if any(not 0<=v<=0xffffffff for v in fields):raise ValueError('newc field overflow')
    header=b'070701'+b''.join(f'{v:08x}'.encode() for v in fields)
    raw=header+raw_name;raw+=b'\0'*(-len(raw)%4);raw+=body;raw+=b'\0'*(-len(raw)%4)
    return raw


def supplement(raw,key):
    if not isinstance(key,bytes) or len(key)!=32:raise ValueError('Retained key must be exactly 32 bytes')
    before=unpack(raw);items=list(entries(before));lookup={x['name']:x for x in items}
    def body(x):return before[x['body']:x['body']+x['size']]
    if KEY_NAME in lookup:
        k=lookup[KEY_NAME]
        if body(k)!=key or k['mode']&0o777!=0o600 or k['uid'] or k['gid'] or not stat.S_ISREG(k['mode']):raise ValueError('Existing key member differs or has unsafe metadata')
    if 'key' in lookup:
        k=lookup['key']
        if not stat.S_ISDIR(k['mode']) or k['mode']&0o777!=0o700 or k['uid'] or k['gid']:raise ValueError('Existing key directory metadata differs')
    added=[];extra=b'';ino=max(x['ino'] for x in items)+1
    if 'key' not in lookup:extra+=member('key',b'',stat.S_IFDIR|0o700,ino);ino+=1;added.append('key')
    if KEY_NAME not in lookup:extra+=member(KEY_NAME,key,stat.S_IFREG|0o600,ino);added.append(KEY_NAME)
    cut=lookup['TRAILER!!!']['offset'];after=before[:cut]+extra+before[cut:]
    updated={x['name']:x for x in entries(after)}
    for name,x in lookup.items():
        y=updated[name]
        if before[x['offset']:x['end']]!=after[y['offset']:y['end']]:raise ValueError('Original member changed')
    k=updated[KEY_NAME]
    if after[k['body']:k['body']+k['size']]!=key:raise ValueError('Supplement readback differs')
    output=gzip.compress(after,mtime=0)
    return output,{'original_members_preserved':len(items),'added_members':added,'key_size':32,'key_mode':'0600','key_owner':'root:root','key_contents_reported':False,'source_sha256':digest(raw),'staged_sha256':digest(output)}
