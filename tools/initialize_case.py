"""Initialize an isolated case using generic workflow files and only the supplied new inputs."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOOL_FILES=['initialize_case.py','workbench.py','paper_quality.py','paper_pages.py','paper_plan.py','paper_style.py','workflow_checks.py','README.md']

def initialize_case(source, name, workspace=None):
    workspace=Path(ROOT if workspace is None else workspace).resolve();source=Path(source).resolve()
    if not isinstance(name,str) or not name.strip() or name in ['.','..'] or '/' in name or '\\' in name or ':' in name:
        raise ValueError('Case name must be a single directory name')
    case_root=(workspace/'cases').resolve();dest=(case_root/name).resolve()
    if not dest.is_relative_to(workspace) or not dest.is_relative_to(case_root) or dest==case_root:
        raise ValueError('Case destination outside workspace/cases')
    if not source.is_dir() or dest.exists():
        raise ValueError('Source missing or case already exists; nothing overwritten')
    if dest.is_relative_to(source):
        raise ValueError('Source cannot contain destination')
    source_items=list(source.rglob('*'))
    if not any(item.is_file() for item in source_items):
        raise ValueError('Source contains no problem materials')
    required=['AGENTS.md','WORKFLOW.md','paper_requirements.json','templates/results_guide.md']+['tools/'+n for n in TOOL_FILES]
    if any(not (workspace/n).is_file() for n in required):
        raise ValueError('Generic framework is incomplete; no case created')
    for item in source_items:
        if item.is_symlink() or (hasattr(item,'is_junction') and item.is_junction()):
            raise ValueError('Input links require explicit source review; refusing implicit traversal')
    for folder in ['00_inputs','01_problem/source_extract','01_problem/handoffs','02_models','03_code','04_experiments','05_figures','06_paper/latex','06_paper/checks','07_delivery','tools']:
        (dest/folder).mkdir(parents=True,exist_ok=True)
    for name in ['AGENTS.md','WORKFLOW.md','paper_requirements.json']:
        shutil.copy2(workspace/name,dest/name)
    shutil.copytree(workspace/'templates',dest/'templates')
    for name in TOOL_FILES:shutil.copy2(workspace/'tools'/name,dest/'tools'/name)
    (dest/'README.md').write_text('# 新题工作区\n\n先读AGENTS、competition、STATUS、WORKFLOW及00_inputs。逐问同步研究与LaTeX写作，完整初稿后表述检查、独立审稿及修改后复查；未达完整性门槛称阶段研究稿。未知赛事信息待核，不继承旧题模型、结果或引用。\n',encoding='utf-8')
    (dest/'competition.md').write_text('# 比赛配置\n\n比赛全名、年份、题号、语言、截止时间及时区：待核实。规则、版式、页数与AI要求：待核实。原始资料见00_inputs；固定质量要求见AGENTS.md。\n',encoding='utf-8')
    (dest/'STATUS.md').write_text('# 当前状态\n\n新题资料已导入，尚未完成读题或研究。下一步核对全部资料、赛事和规则、逐问拆解、数据审计及文献/GitHub调研；随后逐问同步研究与写作。不含旧题结果，无活动论文。\n',encoding='utf-8')
    shutil.copy2(workspace/'templates/results_guide.md',dest/'04_experiments/RESULTS_GUIDE.md')
    for name,obj in [('results_manifest.json',dict(schema_version=1,runs=[])),('adopted_results.json',dict(schema_version=1,results_manifest='04_experiments/results_manifest.json',selections={},products={}))]:
        (dest/'04_experiments'/name).write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
    shutil.copytree(source,dest/'00_inputs'/source.name)
    inventory=[]
    for f in sorted(source.rglob('*')):
        if f.is_file():
            copy=dest/'00_inputs'/source.name/f.relative_to(source)
            digest=hashlib.sha256(f.read_bytes()).hexdigest()
            if digest!=hashlib.sha256(copy.read_bytes()).hexdigest():raise ValueError('Copied input hash differs')
            inventory.append(dict(source=str(f),copy=copy.relative_to(dest).as_posix(),bytes=f.stat().st_size,sha256=digest))
    (dest/'01_problem/input_inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return dest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True);parser.add_argument('--name',required=True)
    args=parser.parse_args()
    try:print(initialize_case(args.source,args.name))
    except (OSError,ValueError) as exc:parser.exit(2,f'ERROR: {exc}\n')
if __name__=='__main__':main()
