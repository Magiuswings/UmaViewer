"""Register independent native attachments and the original 1001 head in supplied v5 layout."""
import argparse,copy,json,posixpath,re,shutil,sys
from pathlib import Path
import numpy as np
from PIL import Image

def spans(text,key):
    tokens=list(re.finditer(r'#[^\n]*|"(?:\\.|[^"\\])*"|[{}=]|[A-Za-z_][A-Za-z_0-9]*',text));out=[]
    for i,t in enumerate(tokens[:-2]):
        if t.group()!=key or tokens[i+1].group()!='='or tokens[i+2].group()!='{':continue
        depth=1;j=i+3
        while depth:
            depth+=(tokens[j].group()=='{')-(tokens[j].group()=='}');j+=1
        out.append((t.start(),tokens[j-1].end()))
    return out

def text(p,s):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s,encoding='utf-8-sig'if p.suffix=='.txt'else'utf8')
def main():
    p=argparse.ArgumentParser()
    for n in ['root','repo','plugin','game']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();r=a.root;mod=r/'UMA-V6-1001';models=mod/'gfx/models/portraits/uma';shared=models/'0001';char=models/'1001';sys.path[:0]=[str(a.repo/'Tools/PDXExporter'),str(a.repo/'Tools/HeadAccessory')]
    from build_ck3_mod import parser_only,clausewitz,one,values,script_block
    pdx=parser_only(a.plugin);head=json.loads((r/'head-export.json').read_text());motion=json.loads((r/'motion-parts/motion-delivery.json').read_text());rows=head['parts'];src=r/'v5'
    # All stock head BS keys remain declared, pointing to one actual no-op mesh.
    stock=(a.game/'gfx/models/portraits/female_head/female_head.asset').read_text(encoding='utf-8-sig');carrier=(src/'gfx/models/portraits/uma/0001/uma_0001_head_empty.asset').read_text(encoding='utf-8-sig')
    carrier=re.sub(r'^.*UMA FACE IDENTITY.*\n','',carrier,flags=re.M)
    for k in ['blend_shape','meshsettings']:
        for s,e in reversed(spans(carrier,k)):carrier=carrier[:s]+carrier[e:]
    for s,e in reversed(spans(carrier,'attribute')):
        if 'blend_shape'in carrier[s:e]:carrier=carrier[:s]+carrier[e:]
    bs=[];attrs=[]
    for s,e in spans(stock,'blend_shape'):
        line=stock[s:e];line=re.sub(r'(\btype\s*=\s*")[^"]+(\")',r'\1uma_0001_head_none.mesh\2',line);bs.append('\t\t'+line)
    for s,e in spans(stock,'attribute'):
        line=stock[s:e]
        if 'blend_shape'in line:attrs.append('\t'+line)
    prefix='uma_0001_head_empty';shape='uma_0001_head_carrierShape'
    settings='\tmeshsettings = {\n\t\tname = "'+shape+'"\n\t\tindex = 0\n'
    for k,end in [('texture_diffuse','diffuse'),('texture_normal','normal'),('texture_specular','properties')]:settings+='\t\t'+k+' = "'+prefix+'_'+end+'.dds"\n'
    settings+='\t\tshader = "portrait_attachment"\n\t\tshader_file = "gfx/FX/uma_portrait.shader"\n\t}\n'
    # Insert before each top-level closing brace without reformatting original
    # animation/attribute statements, preserving the user's comparison layout.
    blocks=spans(carrier,'pdxmesh');assert len(blocks)==1;s,e=blocks[0];carrier=carrier[:e-1]+settings+'\n'+'\n'.join(bs)+'\n'+carrier[e-1:]
    blocks=spans(carrier,'entity');assert len(blocks)==1;s,e=blocks[0];carrier=carrier[:e-1]+'\n'+'\n'.join(attrs)+'\n'+carrier[e-1:];carrier=re.sub(r'\n(?:[ \t]*\n){2,}','\n\n',carrier);text(shared/(prefix+'.asset'),carrier)
    def dds(p,arr):Image.fromarray(np.asarray(arr,np.uint8),'RGBA').save(p,pixel_format='DXT5')
    tail=json.loads((r/'parsed/tail.json').read_text());tprops=tail['materials'][0]['properties'];ttex=next(p for p in tprops if p['name']=='_MainTex');pix=np.array(Image.open(r/'parsed/resources'/ttex['texture']).convert('RGBA'));rgb=pix[:,:,:3]/255.;lum=rgb@np.array([.2126,.7152,.0722]);mask=pix[:,:,3]>0;ref=np.percentile(lum[mask],85);neutral=np.clip(lum/max(ref,1e-8)*.82,0,1);pix[:,:,:3]=np.rint(neutral[:,:,None]*255)
    tailprefix='uma_1001_tail_base';dds(char/(tailprefix+'_diffuse.dds'),pix);dds(char/(tailprefix+'_normal.dds'),np.tile([0,128,255,128],(*pix.shape[:2],1)))
    for k,c in [('properties',[0,38,0,180]),('ssao',[255,255,255,96])]:dds(char/(tailprefix+'_'+k+'.dds'),np.tile(c,(32,32,1)))
    motionrecords=[]
    for part in motion['parts']:
        kind=part['kind'];prefix='uma_1001_'+kind+'_base';dst=char/part['mesh'];shutil.copy2(r/'motion-parts'/part['mesh'],dst);data=pdx.read_meshfile(str(dst));obj=data.find('object')[0];m=obj.find('mesh');m.find('material').attrib={'shader':['portrait_hair'],'diff':[prefix+'_diffuse.dds'],'n':[prefix+'_normal.dds'],'spec':[prefix+'_properties.dds']};pdx.write_meshfile(str(dst),data)
        for anim in part['animations']:
            target=models/anim['file'];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(r/'motion-parts'/anim['file'],target)
        row=dict(element=kind,file=dst.relative_to(mod).as_posix(),vertices=part['mesh_vertices'],triangles=part['mesh_triangles'],shape=obj.tag,shader='portrait_hair',prefix=prefix,attachment_node=part['attachment_node'],animations=part['animations'],bones=part['bone_count']);rows.append(row);motionrecords.append(row)
    clothfile=r/'clothing-parts/clothing-delivery.json'
    if clothfile.exists():
        cloth=json.loads(clothfile.read_text());print('CLOTHING_DELIVERY_SCHEMA',list(cloth),flush=True)
        # Integration of the verified garment is a separate step because the
        # worker may still be refining sitting while head/materials are built.
    bodytree=clausewitz((shared/'uma_0001_body_base.asset').read_text(encoding='utf-8-sig'));bodyentity=one(bodytree,'entity');headtree=clausewitz(carrier);headentity=one(headtree,'entity');stockstates={one(state,'name')for entity in [bodyentity,headentity]for state in values(entity,'state')}
    accessorygenes=[];forced=[];accessories=[]
    for row in rows:
        prefix=row['prefix'];element=row['element'];entity=prefix+'_entity';meshname=prefix+'_mesh';s='pdxmesh = {\n\tname = "'+meshname+'"\n\tfile = "'+Path(row['file']).name+'"\n\tstreaming = Never\n\n\tmeshsettings = {\n\t\tname = "'+row['shape']+'"\n\t\tindex = 0\n'
        for k,end in [('texture_diffuse','diffuse'),('texture_normal','normal'),('texture_specular','properties')]:s+='\t\t'+k+' = "'+prefix+'_'+end+'.dds"\n'
        s+='\t\ttexture = { file = "'+prefix+'_ssao.dds" index = 3 }\n\t\tshader = "'+row['shader']+'"\n\t\tshader_file = "gfx/FX/uma_portrait.shader"\n\t}\n'
        if row.get('animations'):
            s+='\n';s+='\n'.join('\tanimation = { id = "'+anim['state']+'"\t\t\ttype = "../'+anim['file']+'" }'for anim in row['animations'])+'\n'
        s+='}\n\nentity = {\n\tname = "'+entity+'"\n\tpdxmesh = "'+meshname+'"\n\tgame_data = {\n\t\tportrait_entity_user_data = {\n\t\t\tcolor_mask_remap_interval = { interval = { 0.0 1.0 } }\n\t\t}\n\t}\n'
        if row.get('animations'):
            s+='\n\tdefault_state = "idle"\n'
            keys=stockstates|{'idle','idle_entry','frontEnd_middle_entry','frontEnd_middle'}
            for key in sorted(keys):
                clip='frontEnd_middle_entry'if key=='frontEnd_middle_entry'else'idle_entry'if key=='idle_entry'else'idle';entry=key.endswith('_entry');s+='\tstate = { name = "'+key+'"\t\tanimation = "'+clip+'" looping = '+('no next_state = "idle"'if entry else'yes')+' }\n'
            row['mapped_stock_state_keys']=sorted(keys)
        s+='}\n';text(char/(prefix+'.asset'),s)
        accessory='uma_1001_'+element;binding='node = "'+row['attachment_node']+'"'if row.get('attachment_node')else'shared_pose_entity = head';accessories.append(accessory+' = {\n\tportrait_group = uma\n\tentity = { entity = "'+entity+'" '+binding+' }\n}\n')
        gene='eye_accessory'if element=='eye'else'uma_'+element+'_accessory';template='normal_eyes'if element=='eye'else accessory;index='1'if element=='eye'else'0';choices=[('uma_'+kind,[('1',accessory)])for kind in ['male','female','boy','girl']];accessorygenes.append((gene,[(template,[('index',index),*choices])]))
        forced.append(('accessory',[('mode','add'),('gene',gene),('template',template),('value','1')]));row.update(entity=entity,accessory=accessory,gene=gene,template=template)
    text(mod/'common/genes/uma_accessories.txt',script_block([('special_genes',[('accessory_genes',[('portrait_group','uma'),*accessorygenes])])])+'\n')
    text(mod/'gfx/portraits/accessories/uma_1001_accessories.txt','\n'.join(accessories))
    mods=[('uma_single_character',[('portrait_group','uma'),('uma_1001',[('dna_modifiers',forced),('weight',[('base','256')])])]),('uma_custom_hair',[('portrait_group','uma'),('usage','customization'),('interface_position','0'),('priority','5'),('uma_1001',[('dna_modifiers',copy.deepcopy(forced)),('weight',[('base','256')])])])];text(mod/'gfx/portraits/portrait_modifiers/uma_1001_modifiers.txt',script_block(mods)+'\n')
    # Discard any remaining identity-related declaration across common/gfx TXT.
    def clean(node):
        result=[]
        for key,val in node:
            if key and ('gene_uma_face_identity'in key or'uma_bs_face_'in key):continue
            if isinstance(val,list):
                if any(k in ['gene','attribute']and isinstance(v,str)and('gene_uma_face_identity'in v or'uma_bs_face_'in v)for k,v in val):continue
                val=clean(val)
            result.append((key,val))
        return result
    for f in mod.rglob('*.txt'):text(f,script_block(clean(clausewitz(f.read_text(encoding='utf-8-sig'))))+'\n')
    descriptor='name="UMA V6 1001 Native Accessories"\nsupported_version="1.20.*"\n';text(mod/'descriptor.mod',descriptor);text(r/'UMA-V6-1001.mod',descriptor+'path="'+mod.as_posix()+'"\n')
    report=dict(passed=True,parts=rows,placeholder_bones=head['carrier_bones'],placeholder_vertices=3,placeholder_triangles=1,original_head_bs_declarations=len(bs),original_head_bs_attributes=len(attrs),original_head_morphs_used=False,all_identity_strategy_removed=True,head_material_strategy=json.loads((r/'material-policy.json').read_text()),stock_states_with_native_motion=sorted(stockstates),ear_tail_independent_pose=True,txt_encoding='UTF-8-BOM',runtime_verified=False)
    (r/'integration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print('V6_HEAD_MOTION_REGISTERED',len(rows),'parts',len(bs),'empty stock BS',flush=True)
if __name__=='__main__':main()
