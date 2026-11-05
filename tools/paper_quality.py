"""Conservative static checks of explicitly configured manuscript requirements."""
from pathlib import Path
import re


def argument(text, start, opening='{', closing='}'):
    if start >= len(text) or text[start] != opening:
        return None
    depth, pos = 1, start + 1
    while pos < len(text):
        if text[pos] == '\\':
            pos += 2
            continue
        if text[pos] == opening:
            depth += 1
        elif text[pos] == closing:
            depth -= 1
            if not depth:
                return start + 1, pos, pos + 1
        pos += 1
    return None


def calls(text, names):
    pattern = re.compile(r'\\(' + '|'.join(map(re.escape, names)) + r')(?![A-Za-z])\*?')
    for match in pattern.finditer(text):
        preceding = text[:match.start()]
        if (len(preceding) - len(preceding.rstrip('\\'))) % 2:
            continue
        pos = match.end()
        while pos < len(text) and text[pos].isspace():
            pos += 1
        while pos < len(text) and text[pos] == '[':
            group = argument(text, pos, '[', ']')
            if group is None:
                break
            pos = group[2]
            while pos < len(text) and text[pos].isspace():
                pos += 1
        group = argument(text, pos)
        if group:
            yield match.group(1), match.start(), group, text[group[0]:group[1]]


def expanded_source(main, texts):
    base = main.parent
    def expand(path, seen):
        path = path.resolve()
        if path in seen:
            return ''
        text = texts.get(path, '')
        for _, start, group, value in reversed(list(calls(text, ['input', 'include']))):
            if any(c in value for c in '\\#{}$'):
                continue
            target = base / value
            if not target.suffix:
                target = target.with_suffix('.tex')
            text = text[:start] + '\n' + expand(target, seen | {path}) + '\n' + text[group[2]:]
        return text
    return expand(main, set())


def remove_definitions(text):
    spans = []
    for _, start, group, _ in calls(text, ['newcommand', 'renewcommand', 'providecommand', 'DeclareRobustCommand', 'newenvironment', 'renewenvironment']):
        pos = group[2]
        while pos < len(text) and text[pos].isspace():
            pos += 1
        while pos < len(text) and text[pos] == '[':
            optional = argument(text, pos, '[', ']')
            if optional is None:
                break
            pos = optional[2]
            while pos < len(text) and text[pos].isspace():
                pos += 1
        body = argument(text, pos)
        if body:
            spans.append((start, body[2]))
    for start, end in reversed(spans):
        text = text[:start] + ' ' * (end - start) + text[end:]
    return text


def check_quality(main, texts, policy, final=False):
    if not isinstance(policy, dict):
        raise ValueError('paper requirements must be a JSON object')
    if type(policy.get('schema_version')) is not int or policy['schema_version'] != 1:
        raise ValueError('paper requirements schema_version must be integer 1')
    target = policy.get('reference_target', 20)
    tolerance = policy.get('reference_tolerance', 2)
    if type(target) is not int or target < 1 or type(tolerance) is not int or tolerance < 0:
        raise ValueError('reference target/tolerance must be nonnegative integers with target >=1')
    for key in ['require_background', 'require_restatement', 'require_bold_abstract_numbers']:
        if type(policy.get(key, True)) is not bool:
            raise ValueError(f'{key} must be boolean')
    issues = []
    def issue(code, detail, warning=False):
        issues.append(dict(level='warning' if warning or not final else 'error', code=code, file=str(main), detail=detail))
    raw = expanded_source(main, texts)
    document = re.search(r'\\begin\s*\{document\}(.*)\\end\s*\{document\}', raw, re.S)
    source = remove_definitions(document[1] if document else raw)
    if policy.get('require_appendix', False) and not re.search(r'\\appendix\b', source):
        issue('appendix_missing', '缺少LaTeX附录入口；内容充分性另按附录审查表核验。')
    if re.search(r'\\(?:if[a-zA-Z]*|def|let)\b', source):
        issue('quality_dynamic_tex', '存在条件/动态定义，源码检查不解释执行分支，须实际编译与人工核对。', True)
    abstract_matches = list(re.finditer(r'\\begin\s*\{abstract\}(.*?)\\end\s*\{abstract\}', source, re.S))
    body = re.sub(r'\\begin\s*\{abstract\}.*?\\end\s*\{abstract\}', '', source, flags=re.S)
    body = re.split(r'\\appendix\b', body, maxsplit=1)[0]
    body = re.sub(r'\\begin\s*\{thebibliography\}.*?\\end\s*\{thebibliography\}', '', body, flags=re.S)
    headings = [re.sub(r'\s+', ' ', title).strip().casefold() for _, _, _, title in calls(body, ['section', 'subsection', 'subsubsection', 'chapter'])]
    aliases = {
        'background': ['问题背景', '研究背景', '背景', 'background', 'problem background', 'research background', 'introduction'],
        'restatement': ['问题重述', '问题提出', '问题要求', 'problem restatement', 'restatement of the problem', 'problem statement']}
    for name in aliases:
        if policy.get('require_' + name, True) and not any(title in aliases[name] for title in headings):
            issue('missing_' + name, f'未找到明确{name}章节/小节标题。检查范围为主文，不把附录或宏定义作为章节。')
    cite_names = ['cite', 'citep', 'citet', 'parencite', 'textcite', 'autocite', 'footcite', 'supercite']
    cited = {key.strip() for _, _, _, value in calls(body, cite_names) for key in value.split(',') if key.strip()}
    inline = [key.strip() for _, _, _, key in calls(source, ['bibitem'])]
    available = set(inline)
    bib_files = []
    for _, _, _, value in calls(raw, ['bibliography', 'addbibresource']):
        for name in value.split(','):
            if any(c in name for c in '\\#{}$'):
                issue('quality_dynamic_bibliography', '动态文献路径需人工核对。', True)
                continue
            path = main.parent / name.strip()
            if not path.suffix:
                path = path.with_suffix('.bib')
            if path.is_file():
                bib_files.append(str(path))
                available.update(re.findall(r'@(?!(?:comment|string|preamble)\b)\w+\s*\{\s*([^\s,]+)\s*,', path.read_text(encoding='utf-8-sig'), re.I))
    nocited = {key.strip() for _, _, _, value in calls(source, ['nocite']) for key in value.split(',')}
    if '*' in nocited:
        issue('nocite_all', 'nocite{*}不能用来满足正文引用要求；全部文末条目须有主文实际引用。')
    printed = set(inline) | (available if '*' in nocited else (cited | nocited) & available)
    count = len(printed)
    if not target - tolerance <= count <= target + tolerance:
        issue('reference_count', f'预期文末条目{count}，项目目标约{target}（配置容差±{tolerance}）。这是用户质量目标，不是官方赛事规则。')
    if len(inline) != len(set(inline)):
        issue('duplicate_bibitem', '存在重复bibitem键。')
    for key in sorted(printed - cited):
        issue('reference_not_cited_in_body', f'条目{key}未在主文找到引用；摘要/附录/nocite不充作实质主文引用。')
    for key in sorted(cited - available):
        issue('quality_unresolved_cite', f'主文引用{key}无可解析的参考条目。')
    if policy.get('require_bold_abstract_numbers', True):
        if not abstract_matches:
            issue('missing_abstract', '未找到abstract环境；自定义摘要需人工核对并适配检查。')
        for am in abstract_matches:
            abstract = am[1]
            bold_ranges = [group[:2] for _, _, group, _ in calls(abstract, ['textbf', 'mathbf', 'boldsymbol', 'bm', 'symbf', 'symbfup'])]
            for group in re.finditer(r'\{\s*\\bfseries\b', abstract):
                span = argument(abstract, group.start())
                if span:
                    bold_ranges.append(span[:2])
            def bold(start, end):
                return any(lo <= start and end <= hi for lo, hi in bold_ranges)
            number_pattern = r'[+\-−]?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?(?:\\%)?|[零〇一二两三四五六七八九十百千万亿]+(?=[项名条例组折周天次个篇岁问])'
            # Do not interpret digits in macro names or citation keys as abstract values.
            masked = list(abstract)
            for _, start, group, _ in calls(abstract, cite_names + ['ref', 'eqref', 'label']):
                masked[start:group[2]] = ' ' * (group[2] - start)
            for m in re.finditer(number_pattern, ''.join(masked)):
                if not bold(m.start(), m.end()):
                    issue('abstract_number_not_bold', f'摘要数值未识别为显式粗体：{m[0]}（摘要字符偏移{m.start()}）。自定义宏须人工核对。')
            for _, start, group, _ in calls(abstract, ['textbf', 'mathbf', 'boldsymbol', 'bm', 'symbf', 'symbfup']):
                after = abstract[group[2]:]
                if re.match(r'\s*\\%', after):
                    issue('abstract_percent_outside_bold', '摘要百分号位于数值粗体组之外，应与数值一并加粗。')
                content = abstract[group[0]:group[1]]
                if (not abstract[:start].strip() and not abstract[group[2]:].strip()) or len(content.strip()) > .9 * len(abstract.strip()):
                    issue('abstract_whole_bold', '摘要几乎整段加粗，未实现逐项强调数值。')
            if re.fullmatch(r'\s*\{\s*\\bfseries\b.*\}\s*', abstract, re.S):
                issue('abstract_whole_bold', '摘要几乎整段bfseries加粗，应逐项强调数值。')
    return dict(issues=issues, reference_count=count, reference_target=target, reference_tolerance=tolerance,
                body_citations=sorted(cited), expected_printed_references=sorted(printed), bibliography_files=bib_files,
                headings=headings, abstract_count=len(abstract_matches),
                manual_checks=['文献元数据真实性与实际支持内容', '正文引用是否实质支持论断', '科研图像美观、丰富且不冗余', 'PDF字体/字重、实际编译与逐页检查', '科学有效性与nature-reviewer审稿修订'],
                scope='静态LaTeX子集。Bib数据库未引用条目不等于最终文末条目；不展开自定义宏，不证明引用语义、来源真实、图像美观或PDF合格。')
