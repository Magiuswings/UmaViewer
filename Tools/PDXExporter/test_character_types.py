"""Database selection and the restricted whole-body type morph exception."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from character_types import read_database,resolve_characters,make_body_type_groups
from morphs import index_manifest

class CharacterTypeChecks(unittest.TestCase):
    def test_table_selection_and_geometry_guard(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);database=root/'master.mdb'
            c=sqlite3.connect(database)
            c.execute('CREATE TABLE chara_data(id INTEGER,bust INTEGER,skin INTEGER,height INTEGER,shape INTEGER,scale INTEGER)')
            c.executemany('INSERT INTO chara_data VALUES(?,?,?,?,?,?)',[(1001,2,1,1,0,158),(1003,1,1,1,0,150)])
            c.commit();c.close()
            jobs=[];snapshots={}
            for bust in ('1','2'):
                source='3d/chara/body/bdy0004_00/pfb_bdy0004_00_00_1_0_'+bust
                matrix=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
                mesh=dict(name='M_Body',active=True,vertices=[dict(x=0,y=0,z=0),dict(x=1,y=0,z=0),dict(x=0,y=1,z=.1 if bust=='2' else 0)],
                          faces=[dict(material=0,part='body',category='body_skin',triangles=[0,1,2])],
                          uvs=[dict(channel=0,values=[dict(x=0,y=0),dict(x=1,y=0),dict(x=0,y=1)])],
                          weights=[dict(vertex=i,bone='hip',weight=1.) for i in range(3)])
                data=dict(source=source,source_kind='body',variant='00_00_1_0_'+bust,
                          bones=[dict(id='hip',name='Hip',parent=None,matrix=matrix)],meshes=[mesh],
                          materials=[dict(name='body',properties=[dict(name='_MainTex',texture='textures/tex_bdy0004_00_00_1_'+bust+'_diff.png')])])
                name='bust'+bust;snapshots[name]=data
                (root/(name+'.json')).write_text(json.dumps(data),encoding='utf8')
                jobs.append(dict(name=name,kind='body',character_id='shared',source=source,snapshot=name+'.json',categories=['body_skin']))
            path=root/'manifest.json';path.write_text(json.dumps(dict(jobs=jobs,resources='resources',characters=['1001','1003'])),encoding='utf8')
            metadata=read_database(database,['1001','1003']);resolution=resolve_characters(path,metadata)
            self.assertTrue(resolution['all_requested_parameters_matched'])
            self.assertEqual([r['selected_job'] for r in resolution['characters']],['bust2','bust1'])
            self.assertTrue(all(not r['runtime_scale_applied'] for r in resolution['characters']))
            index=index_manifest(path)
            self.assertFalse(index['compatible_groups'])
            types=make_body_type_groups(path,index,resolution)
            self.assertEqual(len(types['groups']),1);self.assertTrue(types['checks'][0]['passed'])
            bad=copy.deepcopy(snapshots['bust2']);bad['meshes'][0]['weights'][0]['weight']=.9
            (root/'bust2.json').write_text(json.dumps(bad),encoding='utf8')
            self.assertFalse(make_body_type_groups(path,index,resolution)['groups'])
            (root/'bust2.json').write_text(json.dumps(snapshots['bust2']),encoding='utf8')
            bad=copy.deepcopy(snapshots['bust2']);bad['materials'][0]['properties'][0]['texture']='textures/tex_bdy0004_00_00_0_2_diff.png'
            (root/'bust2.json').write_text(json.dumps(bad),encoding='utf8')
            unresolved=resolve_characters(path,metadata)
            self.assertFalse(unresolved['all_requested_parameters_matched'])
            with self.assertRaises(ValueError):make_body_type_groups(path,index,unresolved)

if __name__=='__main__':unittest.main()
