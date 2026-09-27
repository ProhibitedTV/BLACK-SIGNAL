"""Record installed dependencies for the additive polish assets; never copy DLC."""
import argparse,re
from pathlib import Path

def collect(install,output):
    root=install/'Files';items=set()
    for asset in ('Basement Collection/Decals/Puddle','Max Collection/Misc/themysteryofzisland/truck'):
        fpe=root/'entitybank'/(asset+'.fpe');items.add(str(fpe.relative_to(root)).replace('/','\\'))
        for line in fpe.read_text().splitlines():
            if '=' not in line:continue
            key,value=(s.strip() for s in line.split('=',1));key=key.lower()
            # MAX resolves legacy APBR effect identifiers to built-in shaders;
            # these are not loose .fx files in current installations.
            if key=='effect':continue
            if not value or not (key in ('model','effect','textured') or key.startswith(('basecolormap','normalmap','surfacemap','emissivemap','textureref'))):continue
            local=Path(value.replace('\\','/'))
            options=[root/local,fpe.parent/local]
            found=next((p for p in options if p.is_file()),None)
            if found is None:raise FileNotFoundError(f'Missing {fpe.name}: {value}')
            items.add(str(found.relative_to(root)).replace('/','\\'))
    output.write_text('\n'.join(sorted(items,key=str.lower))+'\n')
    print(f'Checked {len(items)} installed polish dependencies')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--install',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();collect(a.install,a.output)
