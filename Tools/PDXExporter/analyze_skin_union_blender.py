"""Measure same-profile exposed-skin coverage on the fixed 0004 topology (Blender)."""
import argparse
import json
from pathlib import Path
import sys
from collections import Counter
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SAMPLES=((1,0,0),(0,1,0),(0,0,1),(.5,.5,0),(0,.5,.5),(.5,0,.5),(1/3,1/3,1/3))

def v(point):return Vector(tuple(point[a] for a in 'xyz'))

def triangles(mesh,skin_only=False):
    for section in mesh['faces']:
        if skin_only and section['category']!='body_skin':continue
        ids=section['triangles']
        for i in range(0,len(ids),3):yield section,ids[i:i+3]

def barycentric(p,a,b,c):
    ab,ac,ap=b-a,c-a,p-a
    d00,d01,d11,d20,d21=ab.dot(ab),ab.dot(ac),ac.dot(ac),ap.dot(ab),ap.dot(ac)
    den=d00*d11-d01*d01
    if abs(den)<1e-16:return (1,0,0)
    b=(d11*d20-d01*d21)/den;c=(d00*d21-d01*d20)/den
    return (1-b-c,b,c)

def make_reference(entry):
    data=json.loads(Path(entry['snapshot_path']).read_text(encoding='utf8'))
    points=[];faces=[];uv_faces=[];materials=[]
    for mesh in data['meshes']:
        if not mesh['active']:continue
        offset=len(points);points.extend(v(p) for p in mesh['vertices'])
        uv=next(u['values'] for u in mesh['uvs'] if u['channel']==0)
        for section,tri in triangles(mesh,True):
            faces.append([offset+i for i in tri])
            uv_faces.append([uv[i] for i in tri]);materials.append(section['material'])
    if not faces:return None
    return dict(bvh=BVHTree.FromPolygons(points,faces,all_triangles=True),points=points,faces=faces,
                uv=uv_faces,materials=materials,data=data,entry=entry)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config',type=Path)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    config=json.loads(args.config.read_text(encoding='utf8'));records=[]
    for body in config['bodies']:
        data=json.loads(Path(body['snapshot_path']).read_text(encoding='utf8'))
        refs=[r for entry in body['references'] if (r:=make_reference(entry))]
        # Both costumes must already share the source bind frame. Never translate to force a match.
        joints={b['name']:b['matrix'] for b in data['bones'] if b['name'] in ('Hip','Neck','Spine','Spine1','Spine2')}
        for ref in refs:
            rj={b['name']:b['matrix'] for b in ref['data']['bones']}
            error=max((abs(x-y) for name,m in joints.items() for x,y in zip(m,rj[name])),default=0)
            if error>1e-5:raise ValueError('Costume bind frame differs: '+ref['entry']['name'])
            ref['bind_error']=error
        for mesh_index,mesh in enumerate(data['meshes']):
            points=[v(p) for p in mesh['vertices']]
            labels=[];transfers=[];counts=Counter();areas=Counter();votes_hist=Counter()
            for section,tri in triangles(mesh):
                coords=[points[i] for i in tri]
                cross=(coords[1]-coords[0]).cross(coords[2]-coords[0]);area=cross.length/2
                normal=cross.normalized() if cross.length else Vector((0,1,0))
                if section['category']=='body_skin':
                    labels.append('0004_skin');transfers.append([]);counts['0004_skin']+=1;areas['0004_skin']+=area
                    continue
                choices=[]
                for ref in refs:
                    hits=[]
                    for weights in SAMPLES:
                        p=sum((co*w for co,w in zip(coords,weights)),Vector((0,0,0)))
                        q,n,index,distance=ref['bvh'].find_nearest(p,config['distance'])
                        if index is None or normal.dot(n)<config['normal_dot']:continue
                        face=ref['faces'][index];bc=barycentric(q,*(ref['points'][i] for i in face))
                        tex=next(p for p in ref['data']['materials'][ref['materials'][index]]['properties'] if p['name']=='_MainTex' and p.get('texture'))
                        uv=ref['uv'][index]
                        tu=sum(b*u['x'] for b,u in zip(bc,uv));tv=sum(b*u['y'] for b,u in zip(bc,uv))
                        hits.append(dict(texture=str(Path(ref['entry']['resources_path'])/tex['texture']),
                                         uv=[tu,tv],scale=tex.get('scale',[1,1]),offset=tex.get('offset',[0,0]),distance=distance))
                    choices.append((len(hits),-sum(h['distance'] for h in hits),ref,hits))
                best=max(choices,key=lambda x:x[:2]) if choices else (0,0,None,[])
                votes_hist[str(best[0])]+=1
                label='0009_skin' if best[0]>=config['minimum_votes'] else '0004_fill'
                labels.append(label);transfers.append(best[3] if label=='0009_skin' else [])
                counts[label]+=1;areas[label]+=area
            record=dict(job=body['name'],profile=body['profile'],mesh_index=mesh_index,mesh=mesh['name'],
                        source_vertices=len(points),source_triangles=len(labels),counts=dict(counts),areas_m2=dict(areas),
                        union_skin_triangles=counts['0004_skin']+counts['0009_skin'],remaining_fill_triangles=counts['0004_fill'],
                        references=[dict(name=r['entry']['name'],source=r['data']['source'],bind_matrix_max_error=r['bind_error']) for r in refs],
                        non_skin_nearest_votes=dict(votes_hist),labels=labels,transfers=transfers)
            records.append(record)
            print('SKIN_UNION',body['name'],dict(counts),flush=True)
    output=Path(config['coverage_output']);output.write_text(json.dumps(dict(records=records,parameters=dict(distance_source_m=config['distance'],normal_dot=config['normal_dot'],minimum_of_7_samples=config['minimum_votes']),
        method='Union of 0004 and same-height/shape/bust 0009 skin coverage, projected onto unchanged complete 0004 topology; all remaining triangles use 0004 mesh as skin fill'),ensure_ascii=False),encoding='utf8')

if __name__=='__main__':main()
