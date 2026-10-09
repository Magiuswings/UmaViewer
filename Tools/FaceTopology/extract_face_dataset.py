"""Extract only M_Face from the selected neutral heads; preserve source data."""
import argparse,hashlib,json,sys
from pathlib import Path
from types import SimpleNamespace

def main():
    p=argparse.ArgumentParser()
    for name in ('repo','root'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();sys.path.insert(0,str(a.repo/'Tools/HeadlessExporter'))
    from export_assets import Package,Extractor,key,write_json
    selection=json.loads((a.root/'selection.json').read_text(encoding='utf8'));out=a.root/'face-inputs'
    if out.exists():raise FileExistsError(out)
    out.mkdir();package=Package(a.root/'named-assets')
    class FaceExtractor(Extractor):
        def texture(self,obj):
            # Graph research requires atlas coordinates and source provenance,
            # not hundreds of decoded hair/diffuse textures in RAM/on disk.
            data=self.package.read(obj);return self.package.sources.get(key(obj),'')+'/'+data.m_Name
    extractor=FaceExtractor(package,out,SimpleNamespace(names={},generic_skin='1',generic_skin_reference='0',skin_mode='auto',skin_tolerance=42.))
    original_objects=package.objects;face_renderers=[]
    for o in original_objects:
        if o.type.name not in ('SkinnedMeshRenderer','MeshRenderer')or package.read(package.read(o).m_GameObject.deref()).m_Name=='M_Face':face_renderers.append(o)
    package.objects=face_renderers;jobs=[];errors=[]
    for i,r in enumerate(selection['selection']):
        try:
            identifier=r['source'].rsplit('/',1)[-1][4:]
            data=extractor.prefab(r['source'],'head',identifier,r['id'],[])
            assert len(data['meshes'])==1 and data['meshes'][0]['name']=='M_Face'
            file=out/'snapshots'/('uma_'+r['id']+'_face_'+r['variant']+'.json');write_json(file,data)
            jobs.append(dict(r,snapshot=file.relative_to(out).as_posix(),snapshot_sha256=hashlib.sha256(file.read_bytes()).hexdigest(),vertices=len(data['meshes'][0]['vertices']),triangles=sum(len(f['triangles'])//3 for f in data['meshes'][0]['faces'])))
        except Exception as ex:
            errors.append(dict(id=r['id'],error=type(ex).__name__+': '+str(ex)));print('FACE_EXTRACTION_ERROR',r['id'],type(ex).__name__,str(ex),flush=True)
        if (i+1)%20==0:print('NEUTRAL_FACES_EXTRACTED',i+1,'/',len(selection['selection']),flush=True)
    write_json(out/'manifest.json',dict(jobs=jobs,errors=errors,selected=len(selection['selection']),renderers='M_Face only',texture_images_not_decoded=True,raw_meshes_unmodified=True))
    print('FACE_DATASET_EXTRACTED',len(jobs),'errors',len(errors),flush=True)
    if errors:raise RuntimeError('Face input extraction incomplete')

if __name__=='__main__':main()
