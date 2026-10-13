"""Read actual component geometry/material duplicates, independent of source object names."""
import sys,json,hashlib,collections
from pathlib import Path
from paths_v9 import ROOT,V8,MOD,REPO,PLUGIN
sys.path.insert(0,str(REPO/'Tools/PDXExporter'))
from build_ck3_mod import parser_only
P=parser_only(PLUGIN);rows=json.loads((V8/'Reports/head-registration.json').read_text());records=[]
for r in rows:
    file=Path(r['mesh']);tree=P.read_meshfile(str(file));parts=[];skels=[]
    for obj in tree.find('object'):
        for m in obj.findall('mesh'):
            attrs={k:v for k,v in m.attrib.items()if k in ['p','n','ta','u0','u1','tri']};mat=m.find('material');attrs['material']={k:[Path(a).name if isinstance(a,str)and a.endswith('.dds')else a for a in v]for k,v in mat.attrib.items()};parts.append(attrs)
        skels.append([dict(tag=b.tag,attributes=b.attrib)for b in obj.find('skeleton')])
    records.append(dict(actor=r['actor'],variant=r['variant'],element=r['element'],source=str(file),geometry_material_sha256=hashlib.sha256(json.dumps(parts,sort_keys=True).encode()).hexdigest(),skeleton_sha256=hashlib.sha256(json.dumps(skels,sort_keys=True).encode()).hexdigest(),vertices=r['vertices'],triangles=r['triangles'],optional=r.get('optional'),present=r['present']))
groups=collections.defaultdict(list)
for r in records:groups[(r['actor'],r['element'])].append(r)
summary=[dict(actor=a,element=e,variants=[r['variant']for r in v],geometry_material_groups=len({r['geometry_material_sha256']for r in v}),skeleton_groups=len({r['skeleton_sha256']for r in v}),vertices=[r['vertices']for r in v])for(a,e),v in groups.items()]
(ROOT/'Reports/head-duplicate-inventory.json').write_text(json.dumps(dict(components=records,groups=summary),indent=2),encoding='utf8');print(json.dumps(summary,indent=2),flush=True)
