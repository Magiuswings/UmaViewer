"""Quoted text resources; pattern_mask is a gfx-root-relative exception."""
import json,re
from paths_v10 import MOD,ROOT

EXTENSIONS=('.dds','.mesh','.anim','.shader','.fxh')
ASSIGNMENT=re.compile(r'(?P<prefix>\b(?P<key>[A-Za-z_][\w]*)\s*=\s*)(?P<value>"(?:\\.|[^"\\])*"|[^\s{}#]+)')

def format_resource_references(text,mod=MOD):
    def replace(match):
        raw=match['value'];value=json.loads(raw)if raw.startswith('"')else raw
        if not value.lower().endswith(EXTENSIONS):return match[0]
        if match['key']=='pattern_mask':
            if value.startswith('gfx/'):
                target=mod/value
                if not target.is_file():raise ValueError('Missing pattern_mask: '+str(target))
            else:
                matches=list((mod/'gfx').rglob(value))
                if len(matches)!=1:raise ValueError('Ambiguous pattern_mask: '+value)
                value=matches[0].relative_to(mod).as_posix()
        return match['prefix']+json.dumps(value,ensure_ascii=False)
    return ASSIGNMENT.sub(replace,text)

def main():
    changes=[];mask_count=0;resource_count=0
    for file in sorted([*(MOD/'gfx').rglob('*.asset'),*MOD.rglob('*.txt')]):
        original=file.read_text(encoding='utf-8-sig');updated=format_resource_references(original)
        if original!=updated:
            file.write_text(updated,encoding='utf-8-sig'if file.suffix=='.txt'else'utf8',newline='\n');changes.append(file.relative_to(MOD).as_posix())
        for m in ASSIGNMENT.finditer(updated):
            raw=m['value'];value=json.loads(raw)if raw.startswith('"')else raw
            if not value.lower().endswith(EXTENSIONS):continue
            assert raw.startswith('"')and raw.endswith('"'),(file,m[0]);resource_count+=1
            if m['key']=='pattern_mask':assert value.startswith('gfx/')and(MOD/value).is_file();mask_count+=1
    report=dict(passed=True,pattern_mask_gfx_relative_count=mask_count,quoted_resource_count=resource_count,changed_files=changes,binary_meshes_and_textures_modified=False,game_executed=False)
    (ROOT/'Reports/resource-reference-format.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print('V10_RESOURCE_FORMAT',mask_count,resource_count,len(changes),flush=True)
if __name__=='__main__':main()
