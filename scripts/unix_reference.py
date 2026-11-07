#!/usr/bin/python3
"""Read JUPI's Linux/Windows operation references; never execute translations."""
import argparse
import json
from pathlib import Path

BOOK=Path('/etc/jupi/unix-reference.json')


def lookup(book,query):
    if query in book['entries']:return query,book['entries'][query],'intent'
    for key,value in book['entries'].items():
        if query in [value['linux'],*value.get('linux_aliases',[])]:return key,value,'reviewed exact command'
    return None,None,'unknown'


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('command',choices=('list','map','translate','search'))
    parser.add_argument('query',nargs='?');parser.add_argument('--to',choices=('linux','powershell','cmd','all'),default='all');parser.add_argument('--json',action='store_true');args=parser.parse_args()
    book=json.loads(BOOK.read_text())
    if book.get('schema')!='jupi.unix.reference.v1':raise ValueError('Reference schema differs')
    if args.command in ('list','search'):
        needle=(args.query or '').casefold()
        result={k:v for k,v in book['entries'].items() if args.command=='list' or needle in (k+' '+json.dumps(v)).casefold()}
    else:
        if not args.query:parser.error('An operation name or reviewed command is required')
        key,value,match=lookup(book,args.query.strip())
        if value is None:
            print(json.dumps({'status':'UNKNOWN','input':args.query,'executed':False,'next':'Use jupi-unix list or search; compound/unknown shell input needs explicit review.'},indent=2));return 2
        result={key:{**value,'match':match}}
    if args.json:print(json.dumps({'scope':book['scope'],'executed':False,'entries':result,'sources':book['sources']},indent=2));return 0
    print(book['scope']+'\n')
    columns={'linux':'linux','powershell':'powershell_windows','cmd':'windows_cmd'}
    for key,value in result.items():
        print(key+':')
        for label,field in columns.items():
            if args.to in ('all',label):print('  '+label+': '+(value[field] or 'No reviewed direct template; use the operation notes.'))
        print('  Notes: '+value['notes'])
        if value['changes_state']:print('  This template changes state when explicitly run.')
        print()
    return 0


if __name__=='__main__':raise SystemExit(main())
