"""Keep authored character materials and animations; replace combat behavior only."""
import argparse,base64,hashlib,json,struct
from pathlib import Path
from fpm_inspect import BinaryReader,parse_ele_record,parse_map_ele,FpmError
from fpm_prepare_dressing_v11 import read
from fpm_city_extras import ASSETS,SCRIPT
import fpm_author_street_fabric as fabric

def rewrite(raw,name='BS_EXTRA_TEMPLATE'):
    r=BinaryReader(raw,0x24);edits=[]
    def string(label,new=None):
        start=r.offset;value=r.crlf_string(label)
        if new is not None:edits.append((start,r.offset,new.encode()+b'\r\n'))
        return value
    string('name',name);string('aiinit','');string('aimain',SCRIPT);string('aidestroy','')
    r.skip_i32(1,'objective')
    for label in ('usekey','ifused','ifusednear'):string(label,'')
    r.skip_i32(1,'unique')
    for label in ('texture','alttexture','effect'):string(label)
    r.skip_i32(2,'transparency/fixed')
    string('sound','');string('sound1','')
    r.skip_i32(7,'spawn/render/speed');string('aishoot','');weapon=string('weapon','')
    # Demo encounters may override the unarmed FPE with a weapon. Clear that
    # saved override as well as the attack script for civilian film extras.
    for a,b,new in reversed(edits):raw=raw[:a]+new+raw[b:]
    return raw

def prepare(demo,reference,output):
    bank,ele,p=read(demo);tb,te,tp=read(reference)
    if p['version']!=338 or tp['version']!=342:raise FpmError('Expected 338 -> 342')
    wall=next(e for e in tp['entities'] if (e.get('asset') or '').endswith('\\CS_Wall_01.fpe'))
    raw=te[wall['record_start_offset']:wall['record_end_offset']]
    reader=BinaryReader(raw);parse_ele_record(reader,338,2,tb);tail=raw[reader.offset:]
    result={}
    for e in p['entities']:
        name=Path((e.get('asset') or '').replace('\\','/')).stem.lower()
        if name not in ASSETS or name in result or not fabric.safe_template_entity(e,True)[0]:continue
        if e['staticflag']!=0 or e['profile_scale']!=100 or any(e['scale_xyz'].values()):raise FpmError('Unexpected civilian transform')
        donor=ele[e['record_start_offset']:e['record_end_offset']]
        new=rewrite(donor+tail)
        check=parse_map_ele(struct.pack('<ii',342,1)+new,bank)
        if check['entities'][0]['aimain']!=SCRIPT:raise FpmError('Script binding failed')
        result[name]=dict(asset=e['asset'],version=342,source_version=338,source_record=e['record_index'],source_sha256=hashlib.sha256(donor).hexdigest(),raw_base64=base64.b64encode(new).decode())
    if set(result)!=set(ASSETS):raise FpmError('Incomplete civilian cast')
    output.write_text(json.dumps(dict(demo_sha256=hashlib.sha256(demo.read_bytes()).hexdigest(),templates=result),indent=2)+'\n')
    print('Prepared six unarmed civilian templates with original materials')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('demo','reference','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();prepare(a.demo,a.reference,a.output)
