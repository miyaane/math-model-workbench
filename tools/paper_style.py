"""Locate possible defensive prose; semantic decisions always require contextual review."""
import hashlib
import re
from collections import Counter
from pathlib import Path

PATTERNS = [
    ('contrastive_defense', r'(?:并非|不是)[^。！？.!?]{0,100}?(?:而是|只是)'),
    ('generic_disclaimer', r'仅供参考|不能保证|不保证|尽管存在局限|虽然数据有限|数据有限但|不影响(?:本文|本研究|模型)的(?:有效性|可靠性)'),
    ('self_justification', r'为了避免(?:质疑|误解)|需要特别说明的是|必须强调的是|值得强调的是|需要指出的是'),
    ('unsupported_self_praise', r'充分证明了?(?:本文|本研究|模型)|具有很高的(?:可靠性|准确性|可信度)|结果是可靠的'),
    ('english_disclaimer', r'\b(?:for reference only|cannot guarantee|does not undermine|despite (?:these|the) limitations|it (?:must|should) be (?:noted|emphasized))\b'),
    ('english_defensive_contrast', r'\bnot\s+(?:merely|simply|just)\b[^.!?]{0,100}?\bbut\b'),
]

def check_style(root, main):
    from workbench import commands, tex_text
    root, main = root.resolve(), main.resolve()
    if not main.is_relative_to(root):
        raise ValueError('manuscript must stay inside project')
    texts, hashes, warnings = {}, {}, []
    def visit(path):
        path = path.resolve()
        if not path.is_relative_to(root):
            raise ValueError('style input outside project')
        if path in texts:
            warnings.append(dict(code='repeated_or_cyclic_input', file=path.relative_to(root).as_posix()))
            return
        raw = path.read_text(encoding='utf-8-sig')
        text = tex_text(raw)
        texts[path] = text
        hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        for name in ['input','include']:
            for value in commands(text, name):
                if any(c in value for c in '\\#{}$'):
                    warnings.append(dict(code='dynamic_input_not_expanded', file=path.relative_to(root).as_posix(), value=value))
                    continue
                target = main.parent / value
                visit(target if target.suffix else target.with_suffix('.tex'))
    visit(main)
    findings, phrases = [], Counter()
    characters = 0
    def add(path, text, start, end, category):
        phrase = re.sub(r'\s+', ' ', text[start:end]).strip()
        phrases[phrase] += 1
        findings.append(dict(id=f'S{len(findings)+1:03d}',category=category,
            file=path.relative_to(root).as_posix(),line=text.count('\n',0,start)+1,
            end_line=text.count('\n',0,end)+1,phrase=phrase,
            context=re.sub(r'\s+',' ',text[max(0,start-110):min(len(text),end+140)]).strip(),
            decision='pending_context_review',preserve='Necessary assumptions, evidence limits, failures and uncertainty must remain visible.'))
    for path, source in texts.items():
        text = source
        begin = re.search(r'\\begin\{document\}', text)
        if begin:
            text = re.sub(r'[^\n]', ' ', text[:begin.end()]) + text[begin.end():]
        # Do not treat bibliography entries as manuscript prose.
        for block in reversed(list(re.finditer(r'\\begin\{thebibliography\}.*?\\end\{thebibliography\}',text,re.S))):
            text=text[:block.start()]+re.sub(r'[^\n]',' ',block.group())+text[block.end():]
        lexical=re.sub(r'\\[A-Za-z]+\*?', '', text)
        characters += len(re.sub(r'[\s{}]', '', lexical))
        for category, pattern in PATTERNS:
            for match in re.finditer(pattern, text, re.I):
                add(path,text,match.start(),match.end(),category)
        for para in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)',text):
            qualifiers=list(re.finditer(r'可能|或许|一定程度上|某种程度上|\b(?:may|might|could|perhaps|possibly)\b',para.group(),re.I))
            if len(qualifiers)>=3:
                add(path,text,para.start()+qualifiers[0].start(),para.start()+qualifiers[-1].end(),'clustered_qualifiers')
    return dict(workflow_check_type='paper_style',schema_version=1,status='review_required',quality_accepted=False,
        main=main.relative_to(root).as_posix(),files_sha256=hashes,candidate_count=len(findings),
        approximate_lexical_characters=characters,candidates_per_1000_characters=round(1000*len(findings)/max(1,characters),3),
        repeated_phrases={k:v for k,v in phrases.items() if v>1},findings=findings,warnings=warnings,
        scope='Source-level candidate locator, not semantic review or automatic editing. Counts are not acceptance thresholds; zero candidates is not a pass. Review prose not captured by phrases, retain necessary scientific boundaries, repeat after revision.')
