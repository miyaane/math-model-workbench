"""Early editorial checks. Records and citation links do not certify source truth."""
import hashlib
import math
from pathlib import Path


def active_main(root, explicit=None):
    from workbench import load_json, project_file
    if explicit is not None:
        return project_file(root, explicit)
    pointer = root / '06_paper/active.json'
    if pointer.exists():
        data = load_json(pointer)
        if data.get('schema_version') != 1:
            raise ValueError('invalid active manuscript schema')
        return project_file(root, data.get('main'))
    return project_file(root, '06_paper/latex/main.tex')


def check_plan(root, plan_path):
    from workbench import load_json, project_file, preflight
    root = root.resolve()
    plan = load_json(plan_path)
    if plan.get('schema_version') != 1:
        raise ValueError('invalid paper plan schema')
    policy = load_json(root/'paper_requirements.json')
    # Reuse the policy's public quality report; do not duplicate its citation parser.
    main = project_file(root, plan.get('main'))
    scan = preflight(main, quality_policy=policy)
    actual = scan['paper_quality']
    ledger_path = project_file(root, plan.get('references'))
    ledger = load_json(ledger_path)
    if ledger.get('schema_version') != 1 or not isinstance(ledger.get('references'), list):
        raise ValueError('invalid reference ledger')
    issues = []
    def issue(code, detail):
        issues.append(dict(level='error', code=code, detail=detail))
    refs, dois = {}, set()
    for ref in ledger['references']:
        key = ref.get('key')
        if not isinstance(key, str) or not key.strip() or key in refs:
            raise ValueError('reference keys must be nonempty and unique')
        refs[key] = ref
        doi = ref.get('doi', '').strip().casefold()
        if doi:
            if doi in dois:
                issue('duplicate_doi', key)
            dois.add(doi)
        if ref.get('status') != 'verified_for_claim':
            issue('reference_not_verified', key)
        if not all(ref.get(k) for k in ['title', 'authors', 'year', 'source_urls', 'checked_on', 'read_depth', 'supports']):
            issue('reference_record_incomplete', key)
        if any(not isinstance(u,str) or not u.startswith('https://') for u in ref.get('source_urls', [])):
            issue('invalid_source_url', key)
    sections = plan.get('sections')
    if not isinstance(sections, list) or not sections:
        raise ValueError('plan requires sections')
    ids, total = set(), 0
    fingerprint = {plan_path: hashlib.sha256(plan_path.read_bytes()).hexdigest(),
                   ledger_path: hashlib.sha256(ledger_path.read_bytes()).hexdigest()}
    for value in scan['files_scanned']:
        path = Path(value)
        if not path.is_relative_to(root):
            raise ValueError('manuscript input outside project')
        fingerprint[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    for section in sections:
        sid = section.get('id')
        if not isinstance(sid, str) or not sid.strip() or sid in ids:
            raise ValueError('section IDs must be nonempty and unique')
        ids.add(sid)
        pages = section.get('planned_body_pages')
        if type(pages) not in (float, int) or not math.isfinite(pages) or pages <= 0:
            raise ValueError('planned pages must be positive finite numbers')
        total += pages
        if not section.get('purpose') or not section.get('evidence'):
            issue('section_evidence_missing', sid)
        for value in section.get('evidence', []):
            path = project_file(root, value)
            fingerprint[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    for key, ref in refs.items():
        for support in ref.get('supports', []):
            if not support.get('claim') or support.get('section') not in ids:
                issue('invalid_claim_mapping', key)
    target = actual['reference_target']
    tolerance = actual['reference_tolerance']
    if not target-tolerance <= len(refs) <= target+tolerance:
        issue('planned_reference_count', str(len(refs)))
    cited = set(actual['body_citations'])
    printed = set(actual['expected_printed_references'])
    for key in sorted(cited-refs.keys()):
        issue('citation_without_verified_record', key)
    for key in sorted(refs.keys()-cited):
        issue('mapped_reference_not_cited', key)
    for key in sorted(cited-printed):
        issue('citation_not_in_bibliography', key)
    # Page allocation is a planning alarm, never an actual PDF count.
    minimum = policy.get('minimum_body_pages', 20)
    if isinstance(policy.get('body_pages'), dict):
        minimum = policy['body_pages'].get('minimum', minimum)
    if total < minimum:
        issue('planned_body_shortfall', f'{total:g} < {minimum}')
    maximum = policy.get('maximum_body_pages', 30)
    if maximum is not None and total > maximum:
        issue('planned_body_excess', f'{total:g} > {maximum}')
    return dict(workflow_check_type='paper_plan', status='failed' if issues else 'record_checks_passed',
        issues=issues, main=str(main), planned_body_pages=total,
        actual_body_pages_verified=False, mapped_reference_count=len(refs),
        body_citation_count=len(cited), printed_reference_count=actual['reference_count'],
        files_sha256={p.relative_to(root).as_posix():h for p,h in fingerprint.items()},
        scope='Early record and correspondence checks only. Human source/claim review, actual PDF body count, visual checks and manuscript peer review remain required.')
