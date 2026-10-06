"""Regression checks: identical topology must not erase distinct bust profiles."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from morphs import index_manifest
from body_profiles import body_profile,profiles_compatible,select_body_bases
from partitions import normalize_manifest

class BodyProfileChecks(unittest.TestCase):
    def test_parameter_order_and_unknown(self):
        p=body_profile('3d/chara/body/bdy0004_00/pfb_bdy0004_00_00_1_0_2')
        self.assertEqual((p['height'],p['shape'],p['bust']),('1','0','2'))
        self.assertIsNone(body_profile('pfb_bdy1001_30'))
        self.assertIsNone(body_profile('pfb_bdy0004_00_00_1_0_2','head'))
        for suffix in ('0003_00_00_1_0_2','0004_01_00_1_0_2','0004_00_01_1_0_2','0004_00_00_2_0_2','0004_00_00_1_1_2','0004_00_00_1_0_1'):
            self.assertFalse(profiles_compatible(p,body_profile('pfb_bdy'+suffix)))

    def test_cross_bust_topology_and_cached_partition(self):
        with tempfile.TemporaryDirectory() as scratch:
            root=Path(scratch);(root/'resources').mkdir();jobs=[];snapshots={}
            for bust,category in (('1','body_skin'),('2','clothing')):
                source='3d/chara/body/bdy0004_00/pfb_bdy0004_00_00_1_0_'+bust
                mesh=dict(name='M_Body',vertices=[dict(x=0,y=0,z=0),dict(x=1,y=0,z=0),dict(x=0,y=1,z=0)],
                          faces=[dict(material=0,part='body',category=category,triangles=[0,1,2])],
                          uvs=[dict(channel=0,values=[dict(x=0,y=0),dict(x=1,y=0),dict(x=0,y=1)])],weights=[],active=True)
                data=dict(source=source,source_kind='body',variant='00_00_1_0_'+bust,bones=[],materials=[],meshes=[mesh])
                path='bust'+bust+'.json';(root/path).write_text(json.dumps(data),encoding='utf8')
                job=dict(name='bust'+bust,kind='body',character_id='shared',source=source,snapshot=path,categories=[category])
                jobs.append(job);snapshots[job['name']]=data
            manifest=dict(jobs=jobs,resources='resources',characters=[],body_bases=[])
            path=root/'manifest.json';path.write_text(json.dumps(manifest),encoding='utf8')
            index=index_manifest(path,{'bust1':'same_costume','bust2':'same_costume'})
            pair=next(p for p in index['topology_pairs'] if p['category']=='whole_mesh')
            self.assertTrue(pair['topology_compatible']);self.assertTrue(pair['same_confirmed_family'])
            self.assertFalse(pair['shape_key_eligible']);self.assertFalse(index['compatible_groups'])
            cached=copy.deepcopy(index);cached['compatible_groups']=[dict(base=pair['base'],targets=[pair['target']])]
            new=normalize_manifest(path,root/'normalized',cached)
            result=json.loads(new.read_text(encoding='utf8'))
            self.assertEqual(result['partition_changes'],[]);self.assertEqual(len(result['blocked_partition_transfers']),1)
            for job in result['jobs']:
                self.assertEqual(json.loads((new.parent/job['snapshot']).read_text(encoding='utf8')),snapshots[job['name']])
            # Both profiles have a skin candidate: a small template must not
            # win a single shared-owner selection and hide the other bust base.
            for data in snapshots.values():data['meshes'][0]['faces'][0]['category']='body_skin'
            bases=select_body_bases(jobs,lambda job:snapshots[job['name']])
            self.assertEqual(sorted(b['bust'] for b in bases),['1','2'])

if __name__=='__main__':unittest.main()
