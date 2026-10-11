import os
"""Decode and parse one bounded family at a time; never start Blender or bind to CK3."""
import json,sys,os,tempfile,gc,argparse,re
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(str(Path(os.environ.get('UMA_V7_ROOT','E:/UmaViewer-Exports/2026-10-11-UMA-V7')) / 'ClothingSources'));REPO=Path(str(Path(os.environ.get('UMA_V7_REPO','E:/UmaViewer-Workspace/UmaViewer-source'))));SCRATCH=ROOT/'.temp';SCRATCH.mkdir(parents=True,exist_ok=True);tempfile.tempdir=str(SCRATCH)
for k in ['TEMP','TMP','TMPDIR']:os.environ[k]=str(SCRATCH)
sys.path[:0]=[str(REPO/'Tools/RawAssets'),str(REPO/'Tools/HeadlessExporter')]
from raw_source import RawSource
from uma_raw import Catalog,decode_selected
from export_assets import Package,Extractor,key,bone_id,safe_name,write_json
class NativeMaterialExtractor(Extractor):
 def texture(self,obj):
  k=key(obj)
  if k not in self.textures:
   data=self.package.read(obj);relative='textures/'+safe_name(data.m_Name)+'.png';path=self.resources/relative;path.parent.mkdir(parents=True,exist_ok=True);data.image.save(path);self.textures[k]=dict(path=relative,name=data.m_Name,source=self.package.sources[k],id=obj.path_id)
  return self.textures[k]['path']
 def material(self,obj,character,source_kind,identifier):
  # Bypass old four-family generic material patch, then implement all native Builder routes.
  result=super().material(obj,'generic_source'if self.generic else character,source_kind,identifier)
  if not self.generic:return result
  f=identifier[3:].split('_');typeid=f[0];short='_'.join(f[:2]);long='_'.join(f[:3]);bust=f[-1];skin='1';socks=str(self.socks).zfill(2);slot=self.slots.get(key(obj),0)
  if typeid=='0001':
   if slot==0:prefix='tex_bdy'+short+'_00_waku0';baseprefix=prefix
   elif slot==2:prefix='tex_bdy'+short+'_zekken0_'+bust;baseprefix=prefix
   else:prefix='tex_bdy'+short+'_00_'+skin+'_'+bust+'_'+socks;baseprefix='tex_bdy'+short+'_00_0_'+bust+'_00'
  elif typeid=='0003':prefix='tex_bdy'+short+'_00_'+skin+'_'+bust;baseprefix='tex_bdy'+short+'_00_0_'+bust
  elif typeid in ('0006','0009','0015'):prefix='tex_bdy'+long+'_'+skin+'_'+bust+'_00';baseprefix='tex_bdy'+long+'_0_'+bust+'_00'
  else:prefix='tex_bdy'+long+'_'+skin+'_'+bust;baseprefix='tex_bdy'+long+'_0_'+bust
  expectations={'_MainTex':prefix+'_diff','_ToonMap':prefix+'_shad_c','_TripleMaskMap':baseprefix+'_base','_OptionMaskMap':baseprefix+'_ctrl'}
  textures={self.package.read(o).m_Name:o for o in self.package.objects if o.type.name=='Texture2D'}
  for prop in result['properties']:
   if prop['name']in expectations:
    wanted=expectations[prop['name']];chosen=textures.get(wanted)
    if chosen:prop['texture']=self.texture(chosen);prop['native_binding_source']='UmaContainerCharacter.LoadBody native texture selector'
    else:self.errors.append(dict(kind='missing_native_generic_texture',property=prop['name'],expected=wanted,material=result['name']))
  result['native_expected_textures']=expectations;return result
 def context(self,record,prefab):
  self.generic=record['generic'];profile=prefab.rsplit('_',3)[-3:];self.socks=6 if self.generic and profile in (['1','1','0'],['1','0','1'])else 3;self.slots={}
  for o in self.package.objects:
   if self.package.sources.get(key(o))==prefab and o.type.name in ('SkinnedMeshRenderer','MeshRenderer'):
    for i,ptr in enumerate(self.package.read(o).m_Materials):
     if ptr:self.slots.setdefault(key(ptr.deref()),i)
 def preserve_hierarchy(self,data,prefab):
  byid={b['id']:b for b in data['bones']}
  def add(obj):
   bid=bone_id(obj)
   if bid in byid:return bid
   t=self.package.read(obj);parent=add(t.m_Father.deref())if t.m_Father else None;byid[bid]=dict(id=bid,name=self.package.name(obj),parent=parent,matrix=self.package.world(obj),unity_transform_id=obj.path_id,source_hierarchy_only=True,deform=False);return bid
  for o in self.package.objects:
   if self.package.sources.get(key(o))==prefab and o.type.name=='Transform':add(o)
  data['bones']=list(byid.values());data['source_aux_policy']='Every source Transform retained; weighted bind matrices preserved; nonweighted helpers kept as nondeforming source hierarchy'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--family',action='append');ap.add_argument('--limit',type=int);ap.add_argument('--no-decode',action='store_true');a=ap.parse_args();index=json.loads((ROOT/'cloth-source-index.json').read_text(encoding='utf8'));records=[r for r in index['records']if not a.family or r['family']in a.family];records=records[:a.limit]if a.limit else records;raw=RawSource(Path('E:/uma'),ROOT/'raw-workspace');cat=Catalog(raw,REPO,'auto')
 try:
  for number,record in enumerate(records):
   named=Path(record['decoded_path']);out=Path(record['parsed_directory']);out.mkdir(parents=True,exist_ok=True)
   if not named.exists():
    if a.no_decode:raise FileNotFoundError(str(named))
    roots=[cat.get(n)for n in record['root_names']];assert all(roots);decode_selected(cat,roots,named,dependencies=True,validate=True,allow_missing=False)
   package=Package(named);ex=NativeMaterialExtractor(package,out,SimpleNamespace(names={'1001':'SpecialWeek','1002':'SilenceSuzuka'},generic_skin='1',generic_skin_reference='0',skin_mode='none',skin_tolerance=42.));parsed=[]
   for source in record['selected_prefabs']:
    prefab=source['prefab'];identifier=prefab.rsplit('/',1)[-1].removeprefix('pfb_');character='shared'if record['generic']else str(record['characters'][0]);ex.context(record,prefab);data=ex.prefab(prefab,'body',identifier,character,[]);ex.preserve_hierarchy(data,prefab);data['family_key']=record['key'];data['GenericBodyFamily']=record['GenericBodyFamily'];data['selected_profile']=source['profile'];data['characters']=record['characters'];data['material_variant_contract']=dict(shared_geometry_asset_once=record['generic'],skin_by_character={'1001':1,'1002':1},socks_by_character={'1001':3,'1002':6},variant_colors='Native generic area/color variants retained in decoded source; source-specific diffuse/toon/base/ctrl bindings recorded; no duplicate asset names')
    filename=out/(identifier+'.json');write_json(filename,data);source['parsed_path']=str(filename);source['source_meshes']=[dict(name=m['name'],vertices=len(m['vertices']),triangles=sum(len(f['triangles'])//3 for f in m['faces']),active=m['active'])for m in data['meshes']];source['source_bones']=len(data['bones']);parsed.append(dict(prefab=prefab,path=str(filename),meshes=source['source_meshes'],bones=len(data['bones'])))
   record['status']='parsed';record['material_errors']=ex.errors;record['texture_png_count']=len(ex.textures);write_json(out/'parse-manifest.json',dict(family=record['family'],parsed=parsed,material_errors=ex.errors,source_aux_retained=True,physics_only_prefabs_not_rendered=True));write_json(ROOT/'cloth-source-index.json',index);print('CLOTH_PARSED',number+1,'/',len(records),record['family'],'prefabs',len(parsed),'textures',len(ex.textures),'material_errors',len(ex.errors),flush=True);del package,ex;gc.collect()
 finally:cat.db.close()
if __name__=='__main__':main()

