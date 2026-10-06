"""Four portrait slots must preserve the stock sex/age routing contract."""
from pathlib import Path
import tempfile
import unittest

from build_ck3_mod import clausewitz, complete_portrait_types, one


class FourPortraitTypesChecks(unittest.TestCase):
    def test_preserve_reference_age_bounds_and_uma_models(self):
        sample = '''uma = {
            uma_male = { sex = male head = male_head torso = male_body }
            uma_female = { sex = female head = uma_head torso = uma_body }
            attach = { what = head where = torso }
        }'''
        reference = '''human = {
            male = { sex = male minimum_age = 18 head = male_head torso = male_body }
            female = { sex = female minimum_age = 18 head = female_head torso = female_body }
            boy = { sex = male maximum_age = 18 head = male_head torso = boy_body }
            girl = { sex = female maximum_age = 18 head = female_head torso = girl_body }
        }'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / '00_human_types.txt'
            path.write_text(reference, encoding='utf8')
            text, contract = complete_portrait_types(sample, path)
            group = one(clausewitz(text), 'uma')
            for name in ('male', 'female'):
                self.assertEqual(one(one(group, 'uma_' + name), 'minimum_age'), '18')
            for name in ('boy', 'girl'):
                self.assertEqual(one(one(group, 'uma_' + name), 'maximum_age'), '18')
            self.assertEqual(one(one(group, 'uma_boy'), 'torso'), 'boy_body')
            self.assertEqual(one(one(group, 'uma_girl'), 'head'), 'uma_head')
            self.assertEqual(one(one(group, 'uma_girl'), 'torso'), 'uma_body')
            self.assertEqual(one(one(group, 'attach'), 'what'), 'head')
            self.assertEqual(len(contract['types']), 4)
            # Read the actual boundary instead of forcing a local constant.
            path.write_text(reference.replace('18', '21'), encoding='utf8')
            updated, _ = complete_portrait_types(sample, path)
            self.assertEqual(one(one(one(clausewitz(updated), 'uma'), 'uma_girl'), 'maximum_age'), '21')


if __name__ == '__main__':
    unittest.main()
