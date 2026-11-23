# Copyright (c) 2026 Marwan Megahy
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License version 3 or (at your option) any later
# version. See LICENSE.txt.
"""Read-only Android content-provider archives. No grants, installs or device writes.
Exports are archival only: there is no tested Android import/restore mechanism.
"""
import csv
import hashlib
import json
from pathlib import Path
import re
import shlex
from urllib.parse import quote

class ProviderError(Exception):
    pass


def query(engine, uri, projection, where=None):
    args=['content','query','--uri',uri,'--projection',projection]
    if where is not None: args += ['--where',where]
    code,out,err=engine.shell(' '.join(shlex.quote(x) for x in args),timeout=900)
    if code or err.strip():
        raise ProviderError(err.decode('utf-8','replace')[:1500] or 'Provider command failed')
    text=out.decode('utf-8')
    if text.strip()=='No result found.': return None
    if not text.startswith('Row: 0 '):
        raise ProviderError('Unrecognized provider response: '+text[:500])
    # Remove exactly one command-added line ending, not data whitespace.
    return text[:-2] if text.endswith('\r\n') else text[:-1] if text.endswith('\n') else text


def ids(engine, uri):
    text=query(engine,uri,'_id')
    if text is None:return []
    result=[]
    for index,line in enumerate(text.splitlines()):
        m=re.fullmatch(r'Row: (\d+) _id=(\d+)',line)
        if not m or int(m[1])!=index:raise ProviderError('Unsafe or unexpected ID listing; export refused')
        result.append(int(m[2]))
    if len(set(result))!=len(result):raise ProviderError('Duplicate IDs in provider result')
    return result


def field(engine,uri,rowid,name):
    text=query(engine,uri,name,'_id='+str(rowid))
    if text is None:raise ProviderError('Record disappeared during export')
    prefix='Row: 0 '+name+'='
    if not text.startswith(prefix):raise ProviderError('Unrecognized single-field response')
    value=text[len(prefix):]
    if value=='NULL':
        # The command prints SQL NULL and the literal string NULL identically.
        check=query(engine,uri,'_id','_id='+str(rowid)+' AND '+name+' IS NULL')
        if check is not None:return None
    return value


def bulk(engine,uri,columns):
    # Fixed column names only. SQL expressions serialize each value as hex so
    # commas, embedded newlines and literal NULL cannot corrupt row boundaries.
    for c in columns:
        if not re.fullmatch('[a-z_][a-z_0-9]*',c):raise ProviderError('Invalid fixed column name')
    projection=':'.join(['_id']+["CASE WHEN "+c+" IS NULL THEN 'N' ELSE 'V' || hex(CAST("+c+" AS BLOB)) END AS cv_"+c for c in columns])
    text=query(engine,uri,projection)
    if text is None:return []
    pattern=r'Row: (\d+) _id=(\d+)'+''.join(r', cv_'+c+r'=(N|V[0-9A-Fa-f]*)' for c in columns)
    rows=[]
    for n,line in enumerate(text.splitlines()):
        m=re.fullmatch(pattern,line)
        if not m or int(m[1])!=n:raise ProviderError('Provider did not return unambiguous encoded columns')
        row={'_id':int(m[2])}
        for c,value in zip(columns,m.groups()[2:]):
            row[c]=None if value=='N' else bytes.fromhex(value[1:]).decode('utf-8')
        rows.append(row)
    return rows


def table(engine,uri,columns,folder,label):
    folder.mkdir(parents=True,exist_ok=True)
    errors=[];rows=[];method='encoded bulk query'
    initial=ids(engine,uri)
    try:
        rows=bulk(engine,uri,columns)
        if {r['_id'] for r in rows}!=set(initial):
            raise ProviderError('Provider IDs changed or bulk result was incomplete')
    except Exception as bulk_error:
        from megahy_backup import Cancelled, DeviceDisconnected
        if isinstance(bulk_error,(Cancelled,DeviceDisconnected)):raise
        # Projection whitelists may prohibit computed columns. Read one field
        # per record instead, preserving newlines and checking ambiguous NULL.
        method='single-field fallback (may be slow)'
        engine.update(detail='Reading '+label+' with slower single-field fallback...')
        rows=[]
        for n,rowid in enumerate(initial,1):
            if engine.stop.is_set():
                from megahy_backup import Cancelled, DeviceDisconnected
                raise Cancelled('Stopped by user')
            engine.update(detail=label+': record '+str(n)+' of '+str(len(initial)))
            row={'_id':rowid}
            for column in columns:
                try:row[column]=field(engine,uri,rowid,column)
                except Exception as e:
                    from megahy_backup import Cancelled, DeviceDisconnected
                    if isinstance(e,(Cancelled,DeviceDisconnected)):raise
                    errors.append({'id':rowid,'field':column,'error':str(e)})
            rows.append(row)
    final=ids(engine,uri)
    if set(initial)!=set(final):errors.append({'error':'Provider record IDs changed during export; not a snapshot'})
    data={'format':'megahy-backup provider archive v1','uri':uri,'method':method,
          'restoration':'Archival export only. No automatic or tested Android restore.',
          'scope':'Records visible to the authorized ADB shell in the current provider/user only. Deleted, private or provider-filtered records may be absent.',
          'rows':rows,'errors':errors}
    (folder/'records.json').write_text(json.dumps(data,ensure_ascii=True,indent=2),encoding='utf-8')
    # CSV is a convenience view. JSON is authoritative and distinguishes NULL.
    with open(folder/'records.csv','w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['_id']+columns,extrasaction='ignore')
        writer.writeheader()
        for row in rows:
            # NUL cannot be represented reliably in spreadsheet CSV readers and
            # some Python CSV runtimes reject it. JSON remains lossless.
            display={k:(v.replace('\x00', r'\u0000') if isinstance(v,str) else v) for k,v in row.items()}
            # Prevent opening phone-controlled text as spreadsheet formulas.
            safe={k:("'"+v if isinstance(v,str) and (v.lstrip(' \t\r\n\ufeff').startswith(('=','+','-','@')) or v.startswith(('\t','\r','\n'))) else v) for k,v in display.items()}
            writer.writerow(safe)
    result={'status':'partial' if errors else 'exported (not restore-tested)',
            'records':len(rows),'errors':errors,'method':method,
            'json_sha256':hashlib.sha256((folder/'records.json').read_bytes()).hexdigest(),
            'note':'CSV text beginning with formula characters is apostrophe-prefixed for safety; NUL is displayed as \\u0000. JSON preserves original values. Provider reads are not snapshot/checksum proof of complete phone data.'}
    return result,rows


def read_uri(engine,uri):
    code,out,err=engine.run(['exec-out','content read --uri '+shlex.quote(uri)],timeout=900)
    if code or err.strip():raise ProviderError(err.decode('utf-8','replace')[:1500] or 'Provider stream read failed')
    return out


def contacts(engine,folder):
    uri='content://com.android.contacts/contacts'
    initial=ids(engine,uri);folder.mkdir(parents=True,exist_ok=True)
    errors=[];done=0
    with open(folder/'contacts.vcf','wb') as f:
        for index,rowid in enumerate(initial,1):
            engine.update(detail='Contacts: '+str(index)+' of '+str(len(initial)))
            try:
                lookup=field(engine,uri,rowid,'lookup')
                if not lookup or '\n' in lookup or '\r' in lookup:
                    raise ProviderError('Invalid contact lookup key')
                # LOOKUP_KEY is already URI-encoded. Preserve valid percent escapes.
                data=read_uri(engine,uri+'/as_vcard/'+re.sub(r'%(?![0-9A-Fa-f]{2})', '%25', quote(lookup,safe='%')))
                if not data.strip().upper().startswith(b'BEGIN:VCARD') or not data.strip().upper().endswith(b'END:VCARD'):
                    raise ProviderError('Provider did not return a complete vCard')
                f.write(data)
                if not data.endswith(b'\n'):f.write(b'\r\n')
                done+=1
            except Exception as e:
                from megahy_backup import Cancelled, DeviceDisconnected
                if isinstance(e,(Cancelled,DeviceDisconnected)):raise
                errors.append({'id':rowid,'error':str(e)})
    if set(initial)!=set(ids(engine,uri)):errors.append({'error':'Contact IDs changed during export; not a snapshot'})
    result={'status':'partial' if errors else 'exported (not restore-tested)',
            'visible_contacts':len(initial),'exported_vcards':done,'errors':errors,
            'sha256':hashlib.sha256((folder/'contacts.vcf').read_bytes()).hexdigest(),
            'note':'Provider-visible contacts only; SIM, work-profile, other-user, filtered or cloud-only contacts may be absent. Import/restore has not been tested.'}
    (folder/'details.json').write_text(json.dumps(result,ensure_ascii=True,indent=2),encoding='utf-8')
    return result


def mms(engine,folder):
    result,messages=table(engine,'content://mms',['thread_id','date','msg_box','read','m_type','sub','sub_cs'],folder/'messages','MMS messages')
    try:
        parts_result,parts=table(engine,'content://mms/part',['mid','ct','name','chset','cid','cl','_data','text'],folder/'parts','MMS parts')
    except Exception as e:
        from megahy_backup import Cancelled, DeviceDisconnected
        if isinstance(e,(Cancelled,DeviceDisconnected)):raise
        parts_result,parts={'status':'unavailable','error':str(e)},[]
    result['parts']=parts_result;attachment_errors=[];copied=0;addresses=[]
    for msg in messages:
        mid=msg['_id']
        try:
            r,_=table(engine,'content://mms/'+str(mid)+'/addr',['address','type','charset'],folder/'addresses'/str(mid),'MMS addresses')
            addresses.append({'message_id':mid,**r})
        except Exception as e:
            from megahy_backup import Cancelled, DeviceDisconnected
            if isinstance(e,(Cancelled,DeviceDisconnected)):raise
            addresses.append({'message_id':mid,'status':'unavailable','error':str(e)})
    (folder/'attachments').mkdir(exist_ok=True)
    for p in parts:
        if p.get('_data') is None:
            if '_data' not in p:attachment_errors.append({'part_id':p['_id'],'error':'Part storage metadata unavailable; attachment presence is unknown'})
            continue
        pid=p['_id']
        try:
            data=read_uri(engine,'content://mms/part/'+str(pid))
            target=folder/'attachments'/('part-'+str(pid)+'.bin')
            target.write_bytes(data)
            p['archive_file']=str(target.relative_to(folder))
            p['archive_sha256']=hashlib.sha256(data).hexdigest()
            copied+=1
        except Exception as e:
            from megahy_backup import Cancelled, DeviceDisconnected
            if isinstance(e,(Cancelled,DeviceDisconnected)):raise
            attachment_errors.append({'part_id':pid,'error':str(e)})
    result.update(addresses=addresses,attachment_errors=attachment_errors,attachments_saved=copied,
                  note='MMS JSON metadata, address tables and binary part files form an archival set, not an importable or tested restore backup. Text parts are in parts/records.json. RCS and app-specific chat systems are not covered.')
    if parts_result['status'] in ('partial','unavailable') or attachment_errors or any(r.get('status') in ('unavailable','partial') for r in addresses):result['status']='partial'
    (folder/'attachment-index.json').write_text(json.dumps(parts,ensure_ascii=True,indent=2),encoding='utf-8')
    (folder/'details.json').write_text(json.dumps(result,ensure_ascii=True,indent=2),encoding='utf-8')
    return result


def export_all(engine,backup_folder,selected=None):
    root=Path(backup_folder)/'automatic-exports';root.mkdir()
    from selection import PROVIDERS
    selected = set(PROVIDERS if selected is None else selected)
    results={name:({'status':'pending','note':'Selected; not attempted yet.'} if name in selected else {'status':'not selected','note':'Not requested in this run; no provider query attempted.'}) for name in PROVIDERS}
    jobs=[('contacts',lambda:contacts(engine,root/'contacts')),
          ('sms',lambda:table(engine,'content://sms',['address','date','type','read','body','status','thread_id'],root/'sms','SMS')[0]),
          ('call_log',lambda:table(engine,'content://call_log/calls',['number','date','duration','type','new','name'],root/'call-log','Call log')[0]),
          ('mms',lambda:mms(engine,root/'mms'))]
    engine.update(categories=dict(results))
    (root/'category-report.json').write_text(json.dumps(results,ensure_ascii=True,indent=2),encoding='utf-8')
    for name,job in jobs:
        if name not in selected:
            continue
        results[name]={'status':'reading','note':'Selected provider is being read.'}
        engine.update(phase='Trying automatic exports',detail='Checking '+name+' provider access...',categories=dict(results))
        try:results[name]=job()
        except Exception as e:
            from megahy_backup import Cancelled, DeviceDisconnected
            if isinstance(e,(Cancelled,DeviceDisconnected)):raise
            results[name]={'status':'unavailable','error':str(e),'note':'No permission workaround attempted. No phone files were created. This category is not confirmed backed up.'}
            engine.warn(name+': automatic export unavailable. '+str(e)[:350])
        engine.update(categories=dict(results))
        (root/'category-report.json').write_text(json.dumps(results,ensure_ascii=True,indent=2),encoding='utf-8')
    return results
