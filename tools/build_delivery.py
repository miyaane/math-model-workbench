"""Build explicit, hash-listed case archives without following directory links."""
import argparse,hashlib,json,os,shutil,zipfile
from pathlib import Path
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);ap.add_argument('--config',required=True);ap.add_argument('--output',required=True);args=ap.parse_args()
    root=Path(args.case).resolve();out=Path(args.output).resolve()
    assert out.is_relative_to(root/'07_delivery') and out!=root/'07_delivery'
    out.mkdir(exist_ok=False)
    cfg=json.loads(Path(args.config).read_text(encoding='utf8'))
    reports={}
    for name,patterns in cfg['packages'].items():
        assert name.replace('_','').isalnum()
        files={}
        for pattern in patterns:
            for p in root.glob(pattern):
                if not p.is_file() or p.is_symlink() or not p.resolve().is_relative_to(root):continue
                if any(x in p.parts for x in ['node_modules','__pycache__','.mplconfig']):continue
                if any(getattr(parent,'is_junction',lambda:False)() or parent.is_symlink() for parent in p.parents if parent!=root and parent.is_relative_to(root)):continue
                if p.resolve().is_relative_to(out):continue
                files[p.relative_to(root).as_posix()]=p
        assert files
        manifest={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in sorted(files.items())}
        archive=out/(name+'.zip')
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for k,p in sorted(files.items()):z.write(p,k)
            z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        with zipfile.ZipFile(archive) as z:
            assert z.testzip() is None
            assert all(hashlib.sha256(z.read(k)).hexdigest()==h for k,h in manifest.items())
        reports[name]=dict(files=len(files),bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    (out/'archives.json').write_text(json.dumps(reports,indent=2),encoding='utf8');print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
