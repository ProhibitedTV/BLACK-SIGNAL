"""Upgrade exact static demo records to the captured editor schema, retaining materials.

Only the known 334 -> 342 append-only extension is supported. The extension comes
from a plain editor-saved static wall; no old material/texture fields are replaced.
Stored output contains placement records and asset paths, never meshes or textures.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct

import fpm_author_street_fabric as fabric
from fpm_inspect import BinaryReader, FpmArchive, FpmError, parse_ele_record, parse_map_ele, parse_map_ent


def read(path):
    with FpmArchive(path) as f:
        bank=parse_map_ent(f.read('map.ent'))['entries'];ele=f.read('map.ele')
        return bank,ele,parse_map_ele(ele,bank)


def upgrade(raw,tail,bank):
    upgraded=raw+tail
    check=parse_map_ele(struct.pack('<ii',342,1)+upgraded,bank)
    if check['trailing_bytes'] or check['entities'][0]['record_bytes']!=len(upgraded):
        raise FpmError('Static schema upgrade failed exact traversal')
    return upgraded


def prepare(demo,reference,measurements,output):
    bank,ele,parsed=read(demo);target_bank,target_ele,target=read(reference)
    if parsed['version']!=334 or target['version']!=342:raise FpmError('Unsupported upgrade; expected 334 -> 342')
    wall=next(e for e in target['entities'] if (e.get('asset') or '').endswith('\\CS_Wall_01.fpe'))
    raw=target_ele[wall['record_start_offset']:wall['record_end_offset']]
    reader=BinaryReader(raw);parse_ele_record(reader,334,2,target_bank);tail=raw[reader.offset:]
    # The known default extension: no group association, custom shader, custom effect,
    # sound override or authored FPE override. Pin its bytes rather than inherit edits.
    default_tail=bytes.fromhex('ffffffff00000000000000000000000000000000000000000000000000000000ffffffff0000803f0000803f0000803f0000803f0000803f0000803f0000803f0d0a0d0a0000803f000000000000000000000000000000000000000000000000000000000d0a0d0a0d0a000000000d0a')
    if tail!=default_tail:raise FpmError('Reference static extension differs from calibrated defaults')
    wanted=set(json.loads(measurements.read_text()));out={}
    for e in parsed['entities']:
        name=Path((e.get('asset') or '').replace('\\','/')).stem
        # Emissive overlays are authored as dynamic by the pack. Keep that flag
        # and their animation/material data, while still rejecting grouped records.
        luminous=name.startswith('CS_Neon_') or name in ('CS_ATM_Screen','CS_Bus_Stop_Neon_Sign','CS_Wall_01_NeonDecor_01_Sign_02_Computers')
        safe,_=fabric.safe_template_entity(e,luminous)
        if name not in wanted or name in out or not safe:continue
        if abs(e['profile_scale']-100)>.01 or any(abs(v)>.001 for v in e.get('scale_xyz',{}).values()):continue
        source=ele[e['record_start_offset']:e['record_end_offset']]
        converted=upgrade(source,tail,bank)
        out[name]=dict(asset=e['asset'],source_record=e['record_index'],source_record_sha256=hashlib.sha256(source).hexdigest(),
                       source_version=334,version=342,raw_base64=base64.b64encode(converted).decode())
    output.write_text(json.dumps(dict(demo_sha256=hashlib.sha256(demo.read_bytes()).hexdigest(),
                        extension_sha256=hashlib.sha256(tail).hexdigest(),templates=out),indent=2)+'\n')
    print(f'Prepared {len(out)} exact material-preserving static templates')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('demo','reference','measurements','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();prepare(a.demo,a.reference,a.measurements,a.output)
