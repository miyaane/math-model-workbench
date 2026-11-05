"""Research-record consistency and explicit adopted-evidence dependency checks.

These checks do not infer science from arbitrary prose or execute model code.
"""
import hashlib
import math
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def research_check(root, contract):
    from workbench import load_json, project_file
    root = root.resolve()
    data = load_json(contract)
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('questions'), list) or not data['questions']:
        raise ValueError('research contract needs schema_version 1 and nonempty questions')
    issues, evidence, ids = [], {}, set()
    def issue(level, code, qid, detail):
        issues.append(dict(level=level, code=code, question=qid, detail=detail))
    for q in data['questions']:
        if not isinstance(q, dict):
            raise ValueError('question record must be an object')
        qid = q.get('id')
        if not isinstance(qid, str) or not qid.strip() or qid in ids:
            raise ValueError('question ids must be unique nonempty strings')
        ids.add(qid)
        for field in ['requested_target', 'modeled_target', 'independent_unit', 'validation_unit', 'claim_scope']:
            if not isinstance(q.get(field), str) or not q[field].strip():
                issue('error', 'missing_research_definition', qid, field)
        refs = q.get('evidence', [])
        if not isinstance(refs, list) or not refs:
            issue('warning', 'research_evidence_missing', qid, 'No evidence locations supplied.')
        for value in refs:
            p = project_file(root, value)
            evidence[value] = digest(p)
        if q.get('requested_target') != q.get('modeled_target'):
            bridge = q.get('target_bridge', {})
            conditional = q.get('claim_scope') == 'conditional_proxy'
            reviewed = isinstance(bridge, dict) and bridge.get('status') == 'reviewed' and bool(refs)
            if not reviewed:
                issue('warning' if conditional else 'error', 'target_substitution', qid,
                      'Requested and modeled targets differ. Supply a reviewed bridge or retain a conditional proxy claim; constructed targets are not ground truth.')
            if conditional:
                issue('warning', 'conditional_target', qid, 'Proxy target remains conditional; exact requested target is not certified.')
        if q.get('independent_unit') != q.get('validation_unit'):
            issue('error', 'validation_unit_mismatch', qid, 'Validation partition must respect independent units, or explicitly redesign the task.')
        if q.get('repeated_measurements') is True and q.get('dependence_handling') in [None, '', 'none']:
            issue('error', 'repeated_measurements_unhandled', qid, 'Repeated observations lack a declared dependence treatment.')
        spec = q.get('shape', {})
        if spec:
            if not isinstance(spec, dict) or not isinstance(spec.get('declared_properties', []), list):
                raise ValueError('shape must contain declared_properties list')
            if spec.get('basis') == 'positive_hinge' and spec.get('nonnegative_coefficients') is True:
                if 'convex_linear_predictor' not in spec.get('declared_properties', []):
                    issue('error', 'hidden_shape_constraint', qid,
                          'Nonnegative positive-hinge increments imply convexity of the linear predictor, not merely monotonicity. For Logistic this is logit convexity, not probability convexity.')
            elif spec.get('basis') not in ['positive_hinge', 'independent_segments']:
                issue('warning', 'shape_requires_manual_review', qid, 'Unsupported shape representation; no symbolic inference performed.')
        if 'time_records' in q:
            if not isinstance(q['time_records'], list) or not q.get('time_unit'):
                raise ValueError('time records need a list and explicit common time_unit')
            violations = []
            for row in q['time_records']:
                if not isinstance(row, dict):
                    raise ValueError('time record must be an object')
                a, t = row.get('available_at'), row.get('decide_at')
                if type(a) not in [int, float] or type(t) not in [int, float] or not math.isfinite(a) or not math.isfinite(t):
                    raise ValueError('times must be finite numbers using the same origin/unit')
                if t < a - 1e-10:
                    violations.append(a - t)
            if violations:
                issue('error', 'decision_before_input', qid,
                      dict(records=len(q['time_records']), violations=len(violations), max_advance=max(violations), unit=q['time_unit']))
    return dict(workflow_check_type='research', status='failed' if any(i['level'] == 'error' for i in issues) else 'record_consistent_review_required',
                questions=sorted(ids), issues=issues, evidence_sha256=evidence, contract_sha256=digest(contract),
                scientific_validity_certified=False,
                scope='Declared-record consistency plus finite time comparisons. Does not parse arbitrary model code or certify target bridges, assumptions, or causal/clinical validity. Retrospective replay does not prove prospective detection of unknown issues.')


class EvidenceGraph:
    def __init__(self, root, mapping):
        from workbench import load_json, project_file, read_results
        self.root = root.resolve()
        self.mapping = mapping.resolve()
        self.data = load_json(self.mapping)
        if not isinstance(self.data, dict) or self.data.get('schema_version') != 1:
            raise ValueError('invalid adopted evidence schema')
        self.selections = self.data.get('selections', {})
        self.products = self.data.get('products', {})
        if not isinstance(self.selections, dict) or not self.selections or not isinstance(self.products, dict):
            raise ValueError('nonempty selections and products object required')
        if set(self.selections) & set(self.products):
            raise ValueError('selection and product ids must not collide')
        manifest = project_file(self.root, self.data.get('results_manifest', '04_experiments/results_manifest.json'))
        self.runs = {p: run for p, run in read_results(self.root, manifest)}
        self.producers = {path: run for run in self.runs.values() if run['status'] == 'success' for path in run['artifacts']}
        self.sources, self.deps = {}, {}
        self.selected_paths = {}
        for alias, selected in self.selections.items():
            if not isinstance(selected, dict) or selected.get('run') not in self.runs:
                raise ValueError(f'{alias}: unknown run')
            run = self.runs[selected['run']]
            role = selected.get('role', 'artifact')
            if run['status'] != 'success' or role not in ['input', 'artifact']:
                raise ValueError(f'{alias}: only registered successful run inputs/artifacts are selectable')
            value = selected.get('path')
            if value not in run['inputs' if role == 'input' else 'artifacts']:
                raise ValueError(f'{alias}: path is not declared in selected run {role}s')
            self.selected_paths[alias] = project_file(self.root, value)
            paths = {value, selected['run']}
            def provenance(r, seen):
                if r['run_id'] in seen:
                    return
                seen.add(r['run_id'])
                paths.update(r['inputs'] + r['code_files'] + [r['config'], r['environment']])
                for name in r['inputs']:
                    if name in self.producers:
                        provenance(self.producers[name], seen)
            provenance(run, set())
            self.sources[alias] = paths
            self.deps[alias] = []
        for name, product in self.products.items():
            if not isinstance(product, dict) or not isinstance(product.get('depends_on'), list) or not isinstance(product.get('outputs'), list):
                raise ValueError(f'{name}: invalid product definition')
            self.deps[name] = product['depends_on']
            self.sources[name] = set(product.get('sources', []))
            for value in product['outputs'] + list(self.sources[name]):
                self.relative(value)
        for name, deps in self.deps.items():
            if any(d not in self.deps for d in deps):
                raise ValueError(f'{name}: unknown dependency')
        visiting, visited = set(), set()
        def visit(n):
            if n in visiting:
                raise ValueError('evidence dependency cycle')
            if n in visited:
                return
            visiting.add(n)
            for d in self.deps[n]:
                visit(d)
            visiting.remove(n)
            visited.add(n)
        for name in self.deps:
            visit(name)

    def relative(self, value):
        if not isinstance(value, str) or not value or Path(value).is_absolute() or ':' in value:
            raise ValueError('evidence paths must be project-relative')
        path = (self.root / value).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('evidence path outside project')
        return path

    def path(self, alias):
        if alias not in self.selected_paths:
            raise ValueError(f'unknown adopted selection: {alias}')
        return self.selected_paths[alias]

    def snapshot(self):
        nodes = {}
        for name, paths in self.sources.items():
            files = {p: digest(self.relative(p)) if self.relative(p).is_file() else None for p in sorted(paths)}
            if name in self.products:
                files.update({p: digest(self.relative(p)) if self.relative(p).is_file() else None for p in self.products[name]['outputs']})
            nodes[name] = dict(definition=self.selections.get(name, self.products.get(name)), files=files)
        return dict(workflow_check_type='evidence_snapshot', schema_version=1, nodes=nodes,
                    mapping_sha256=digest(self.mapping),
                    missing_files=sorted({p for node in nodes.values() for p, h in node['files'].items() if h is None}),
                    scope='Dependency fingerprint only. Does not certify correct adoption, scientific validity, paper claims, or output quality.')

    def impact(self, baseline=None, changed=()):
        from workbench import load_json
        current = self.snapshot()
        changed_paths = set(changed)
        for p in changed_paths:
            self.relative(p)
        seeds = set()
        if baseline is not None:
            previous = load_json(baseline)
            if previous.get('workflow_check_type') != 'evidence_snapshot' or previous.get('schema_version') != 1:
                raise ValueError('not an evidence snapshot')
            for name in set(current['nodes']) | set(previous['nodes']):
                if current['nodes'].get(name) != previous['nodes'].get(name):
                    seeds.add(name)
        for name, node in current['nodes'].items():
            if changed_paths & set(node['files']):
                seeds.add(name)
        affected = set(seeds)
        while True:
            more = {name for name, deps in self.deps.items() if set(deps) & affected}
            if more <= affected:
                break
            affected |= more
        return dict(workflow_check_type='impact', affected_selections=sorted(affected & set(self.selections)),
                    affected_products=sorted(affected & set(self.products)),
                    actions={name: self.products[name].get('action', 'review') for name in sorted(affected & set(self.products))},
                    changed_inputs=sorted(changed_paths), unknown_changed_inputs=sorted(changed_paths - {p for n in current['nodes'].values() for p in n['files']}),
                    missing_files=current['missing_files'],
                    scope='Conservative declared dependency impact. Actions are recommendations only; no model, figure, compilation or review executed. Undeclared dependencies cannot be detected.')
