import json,shutil,hashlib
from paths_v10 import ROOT,MOD
candidate=ROOT/'RegistrationDraft'
check=json.loads((candidate/'independent_verification.json').read_text());assert check['passed']
for rel in ['gfx/portraits/portrait_modifiers/uma_customization.txt','gfx/portraits/customization_rules/uma_portrait_customization.txt']:
    src=candidate/'UMA-V10'/rel;dst=MOD/rel;shutil.copy2(src,dst)
print('V10_GAME_CUSTOM_SPLIT_APPLIED',flush=True)
