"""Local, standard-library workflow checks. Does not execute TeX or model code."""
import argparse
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from paper_quality import check_quality

ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    def reject(value):
        raise ValueError(f"non-finite JSON constant: {value}")
    def unique(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise ValueError(f"duplicate JSON key: {key}")
            obj[key] = value
        return obj
    return json.loads(path.read_text(encoding="utf-8-sig"),
                      parse_constant=reject, object_pairs_hook=unique)


def project_file(root, value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("expected a nonempty project-relative file path")
    if Path(value).is_absolute() or re.match(r"^[A-Za-z]:", value):
        raise ValueError(f"absolute path is not allowed: {value}")
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"missing file or outside project: {value}")
    return path


def read_results(root, manifest):
    data = load_json(manifest)
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1:
        raise ValueError("manifest schema_version must be integer 1")
    if not isinstance(data.get("runs"), list):
        raise ValueError("manifest runs must be a list of result paths")
    runs, ids, paths = [], set(), set()
    for value in data["runs"]:
        path = project_file(root, value)
        if path in paths:
            raise ValueError(f"duplicate run file: {value}")
        paths.add(path)
        run = load_json(path)
        if not isinstance(run, dict) or type(run.get("schema_version")) is not int or run["schema_version"] != 1:
            raise ValueError(f"{value}: invalid result schema")
        for field in ("run_id", "question", "model_id", "recorded_at", "command", "code_version"):
            if not isinstance(run.get(field), str) or not run[field].strip():
                raise ValueError(f"{value}: missing/non-string {field}")
        if run["run_id"] in ids:
            raise ValueError(f"duplicate run_id: {run['run_id']}")
        ids.add(run["run_id"])
        date = datetime.fromisoformat(run["recorded_at"])
        if date.tzinfo is None or date.utcoffset() is None:
            raise ValueError(f"{value}: recorded_at needs timezone")
        if "seed" not in run or (run["seed"] is not None and type(run["seed"]) is not int):
            raise ValueError(f"{value}: seed must be integer or null")
        if run.get("status") not in ("success", "failed", "unverified"):
            raise ValueError(f"{value}: invalid status")
        for field in ("experiment_card", "config", "environment", "log"):
            project_file(root, run.get(field))
        for field in ("inputs", "artifacts", "code_files"):
            if not isinstance(run.get(field), list):
                raise ValueError(f"{value}: {field} must be a list")
            for file in run[field]:
                project_file(root, file)
        if not run["code_files"]:
            raise ValueError(f"{value}: code_files must include the actual source/snapshot files")
        metrics = run.get("metrics")
        if not isinstance(metrics, dict):
            raise ValueError(f"{value}: metrics must be an object")
        if run["status"] == "success" and (not metrics or not run["artifacts"]):
            raise ValueError(f"{value}: success needs metrics and artifacts")
        if run["status"] != "success" and (not isinstance(run.get("failure_reason"), str) or not run["failure_reason"].strip()):
            raise ValueError(f"{value}: unsuccessful run needs failure_reason")
        for name, metric in metrics.items():
            if not name.strip() or not isinstance(metric, dict):
                raise ValueError(f"{value}: invalid metric {name}")
            number = metric.get("value")
            if type(number) not in (int, float) or not math.isfinite(number):
                raise ValueError(f"{value}: metric {name} must be finite numeric")
            for field in ("unit", "definition"):
                if not isinstance(metric.get(field), str) or not metric[field].strip():
                    raise ValueError(f"{value}: metric {name} missing {field}")
            if metric.get("direction") not in ("min", "max", "target", "report"):
                raise ValueError(f"{value}: metric {name} invalid direction")
        runs.append((value, run))
    return runs


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def summary_text(runs):
    lines = ["# 实验结果汇总（由登记文件生成）", "",
             "文件完整与格式通过检查，不代表结果真实、已复跑或不同运行可直接比较。", "",
             "| run_id | 小问 | 模型 | 指标 | 数值 | 单位 | 方向 | 定义 | 结果文件 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for path, run in runs:
        if run["status"] == "success":
            for name, metric in run["metrics"].items():
                values = [run["run_id"], run["question"], run["model_id"], name,
                          repr(metric["value"]), metric["unit"], metric["direction"], metric["definition"], path]
                lines.append("| " + " | ".join(map(cell, values)) + " |")
    if not any(run["status"] == "success" for _, run in runs):
        lines += ["", "尚无登记为成功的实验；不得据此填写论文数值。"]
    lines += ["", "## 失败与未验证运行", ""]
    for path, run in runs:
        if run["status"] != "success":
            lines.append(f"- {cell(run['run_id'])} [{run['status']}]：{cell(run['failure_reason'])}；{cell(path)}")
    return "\n".join(lines) + "\n"


def tex_text(text):
    # Lex comments and literals together: commented begin/verb must not mask body.
    parts, i = [], 0
    while i < len(text):
        end = None
        if text[i] == "%":
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
        elif text[i:i + 2] in ("\\%", "\\\\"):
            parts.append(text[i:i + 2])
            i += 2
            continue
        elif text[i] == "\\":
            env = re.match(r"\\begin\{(verbatim\*?|lstlisting|minted|comment)\}", text[i:])
            verb = re.match(r"\\verb\*?([^\w\s])", text[i:])
            if env:
                closing = "\\end{" + env[1] + "}"
                pos = text.find(closing, i + env.end())
                end = len(text) if pos < 0 else pos + len(closing)
            elif verb:
                pos = text.find(verb[1], i + verb.end())
                if pos >= 0:
                    end = pos + 1
        if end is not None:
            parts.append("".join("\n" if c == "\n" else " " for c in text[i:end]))
            i = end
        else:
            parts.append(text[i])
            i += 1
    return "".join(parts)


def result_sources(root, manifest, runs):
    paths = {manifest.resolve()}
    for value, run in runs:
        paths.add(project_file(root, value))
        for field in ("experiment_card", "config", "environment", "log"):
            paths.add(project_file(root, run[field]))
        for field in ("inputs", "artifacts", "code_files"):
            paths.update(project_file(root, value) for value in run[field])
    return paths


def summary_snapshot(root, sources, text):
    return {"schema_version": 1,
            "summary_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "sources": {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in sorted(sources)}}


def build_summary(root, manifest, output, verify=False):
    runs = read_results(root, manifest)
    sources = result_sources(root, manifest, runs)
    sidecar = output.with_suffix(".sources.json").resolve()
    output = output.resolve()
    if not output.is_relative_to(root) or not sidecar.is_relative_to(root):
        raise ValueError("summary outputs must stay inside project")
    if output in sources or sidecar in sources or output == sidecar:
        raise ValueError("summary output would overwrite source evidence")
    text = summary_text(runs)
    snapshot = summary_snapshot(root, sources, text)
    if verify:
        if not output.is_file() or not sidecar.is_file():
            raise ValueError("summary or source fingerprint missing; run summarize first")
        if output.read_text(encoding="utf-8") != text or load_json(sidecar) != snapshot:
            raise ValueError("summary is stale or modified; inspect changes and rerun summarize")
    else:
        write_report(output, text)
        write_report(sidecar, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    return len(runs)


def commands(text, name):
    """Read balanced braced arguments for a static command subset."""
    pattern = r"\\" + name + r"(?![A-Za-z])\*?\s*(?:\[[^\]]*\]\s*)*\{"
    for match in re.finditer(pattern, text):
        preceding = text[:match.start()]
        if (len(preceding) - len(preceding.rstrip("\\"))) % 2:
            continue
        depth, end = 1, match.end()
        while end < len(text) and depth:
            preceding = text[:end]
            escaped = (len(preceding) - len(preceding.rstrip("\\"))) % 2
            if text[end] == "{" and not escaped:
                depth += 1
            elif text[end] == "}" and not escaped:
                depth -= 1
            end += 1
        if not depth:
            yield text[match.end():end - 1].strip()


def preflight(main, final=False, log=None, quality_policy=None):
    main = main.resolve()
    base = main.parent
    issues, texts, visited = [], {}, set()

    def issue(level, code, file, detail):
        issues.append({"level": level, "code": code, "file": str(file), "detail": detail})

    def dynamic(value):
        return any(c in value for c in "\\#{}$")

    def visit(path):
        path = path.resolve()
        if path in visited:
            issue("warning", "repeated_input", path, "重复或循环输入，需结合实际编译核对。")
            return
        visited.add(path)
        if not path.is_file():
            issue("error", "missing_tex", path, "主文件或静态输入文件不存在。")
            return
        text = tex_text(path.read_text(encoding="utf-8-sig"))
        texts[path] = text
        if re.search(r"(?i)\b(?:TODO|TBD|PLACEHOLDER|XXX)\b|待填写|待补充|待完成|待续写|To Be Completed", text):
            issue("error" if final else "warning", "placeholder", path, "存在待完成内容；草稿允许保留，最终版须移除。")
        if re.search(r"RESULTS_REPORT|ANALYSIS_MODELING_REPORT|AGENTS\.md|STATUS\.md|04_experiments/|_tmp/", text):
            issue("warning", "internal_text", path, "正文疑似含内部工作记录；检查是否应移至复现附录。")
        for name in ("input", "include"):
            for value in commands(text, name):
                if dynamic(value):
                    issue("warning", "dynamic_input", path, f"动态输入需实际编译：{value}")
                    continue
                target = base / value
                if not target.suffix:
                    target = target.with_suffix(".tex")
                visit(target)
        if re.search(r"\\(?:input|include)\s+(?!\{)\S", text):
            issue("warning", "unbraced_input", path, "未展开无花括号输入，请结合编译核对。")

    visit(main)
    graphic_dirs = [base]
    labels, refs, bibkeys, citations = [], [], set(), []
    extensions = [".pdf", ".png", ".jpg", ".jpeg", ".PDF", ".PNG", ".JPG", ".JPEG"]
    for path, text in texts.items():
        for group in commands(text, "graphicspath"):
            for folder in re.findall(r"\{([^{}]+)\}", group):
                if dynamic(folder):
                    issue("warning", "dynamic_graphicspath", path, folder)
                else:
                    graphic_dirs.append(base / folder)
        for group in commands(text, "DeclareGraphicsExtensions"):
            extensions += [ext.strip() for ext in group.split(",") if ext.strip().startswith(".")]
        labels.extend(commands(text, "label"))
        for name in ("ref", "eqref", "autoref", "pageref", "cref", "Cref"):
            refs += [key.strip() for group in commands(text, name) for key in group.split(",")]
        for name in ("cite", "citep", "citet", "parencite", "textcite", "autocite", "nocite"):
            citations += [key.strip() for group in commands(text, name) for key in group.split(",") if key.strip() != "*"]
        bibkeys.update(commands(text, "bibitem"))
        for name in ("bibliography", "addbibresource"):
            for group in commands(text, name):
                for value in group.split(","):
                    if dynamic(value):
                        issue("warning", "dynamic_bibliography", path, value)
                        continue
                    file = base / value.strip()
                    if not file.suffix:
                        file = file.with_suffix(".bib")
                    if file.is_file():
                        bibkeys.update(re.findall(r"@\w+\s*\{\s*([^\s,]+)\s*,", file.read_text(encoding="utf-8-sig")))
                    else:
                        issue("error", "missing_bibliography", path, str(file))
    for path, text in texts.items():
        for value in commands(text, "includegraphics"):
            if dynamic(value):
                issue("warning", "dynamic_image", path, value)
                continue
            candidates = [folder / value for folder in graphic_dirs]
            found = any(file.is_file() or (not file.suffix and any(file.with_suffix(ext).is_file() for ext in extensions)) for file in candidates)
            if not found:
                issue("error", "missing_image", path, f"未在主文件目录及静态 graphicspath 中找到：{value}")
    seen_labels = set()
    for label in labels:
        if label in seen_labels:
            issue("warning", "duplicate_label", main, label)
        seen_labels.add(label)
    for ref in sorted(set(refs) - set(labels)):
        issue("warning", "unresolved_ref", main, f"静态扫描未找到标签：{ref}")
    for key in sorted(set(citations) - bibkeys):
        issue("warning", "unresolved_cite", main, f"静态扫描未找到文献键：{key}")
    if log is not None:
        if not log.is_file():
            issue("error", "missing_log", log, "指定的编译日志不存在。")
        else:
            text = log.read_text(encoding="utf-8", errors="replace")
            if re.search(r"(?m)^!|Emergency stop|Fatal error", text):
                issue("error", "compile_error", log, "日志含编译错误；需确认日志对应当前源文件。")
            if re.search(r"undefined|Missing character|Overfull", text, re.I):
                issue("warning", "compile_warning", log, "日志含未定义引用、缺字或溢出提示。")
    quality = check_quality(main, texts, quality_policy, final) if quality_policy is not None else None
    if quality:
        issues.extend(quality['issues'])
    from paper_pages import check_pages
    pages = check_pages(main, texts, quality_policy, final) if quality_policy is not None else None
    if pages:
        issues.extend(pages['issues'])
    return {"status": "failed" if any(i["level"] == "error" for i in issues) else "static_checks_passed",
            "paper_quality": quality, "paper_pages": pages,
            "mode": "final" if final else "draft", "main": str(main), "files_scanned": [str(p) for p in texts],
            "issues": issues, "compilation_performed": False, "visual_review_performed": False,
            "scope": "静态子集检查：不展开宏、条件分支、包加载或生成资源；图片路径以主文件目录为编译工作目录。文献存在性、数值一致性、数学正确性和比赛合规需另外核验。日志未核验时效；通过不代表可提交。"}


def write_report(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def resolve_root(workspace, explicit_root=None, case=None):
    workspace = workspace.resolve()
    if explicit_root is not None:
        return explicit_root.resolve()
    if case is None and (workspace / 'workspace.json').is_file():
        config = load_json(workspace / 'workspace.json')
        if not isinstance(config, dict) or type(config.get('schema_version')) is not int or config['schema_version'] != 1:
            raise ValueError('invalid workspace.json schema')
        case = config.get('active_case')
        if not isinstance(case, str) or not case.strip():
            raise ValueError('workspace active_case must be nonempty')
    if case is None:
        return workspace
    if Path(case).is_absolute() or re.match(r'^[A-Za-z]:', str(case)):
        raise ValueError('case path must be workspace-relative')
    root = (workspace / case).resolve()
    if not root.is_relative_to(workspace) or not root.is_dir():
        raise ValueError('case missing or outside workspace')
    return root


def main_cli():
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--root", type=Path, help='Explicit historical/standalone project; bypass active-case selection')
    selection.add_argument("--case", help='Workspace-relative case path; overrides workspace.json')
    sub = parser.add_subparsers(dest="action", required=True)
    summary = sub.add_parser("summarize")
    summary.add_argument("--manifest", default="04_experiments/results_manifest.json")
    summary.add_argument("--output", default="04_experiments/RESULTS_SUMMARY.md")
    summary.add_argument("--verify", action="store_true", help="Check source fingerprints without writing")
    check = sub.add_parser("preflight")
    check.add_argument("--main", help="Explicit main, otherwise use 06_paper/active.json or canonical LaTeX main")
    check.add_argument("--output", default="06_paper/checks/preflight.json")
    check.add_argument("--log")
    check.add_argument("--final", action="store_true")
    sub.add_parser('context', help='Read-only active project and required startup documents')
    paperplan = sub.add_parser('paper-plan', help='Early citation-to-claim and evidence-backed section allocation checks')
    paperplan.add_argument('--plan', default='06_paper/manuscript_plan.json')
    paperplan.add_argument('--output', default='06_paper/checks/paper_plan.json')
    style = sub.add_parser('paper-style', help='Locate defensive-prose candidates; contextual review remains required')
    style.add_argument('--main')
    style.add_argument('--output', default='06_paper/checks/paper_style_candidates.json')
    research = sub.add_parser('research-check', help='Check explicitly recorded target, shape and information timing')
    research.add_argument('--contract', default='02_models/research_contract.json')
    research.add_argument('--output', default='06_paper/checks/research_check.json')
    snapshot = sub.add_parser('evidence-snapshot', help='Write an immutable dependency fingerprint')
    snapshot.add_argument('--mapping', default='04_experiments/adopted_results.json')
    snapshot.add_argument('--output', required=True)
    impact = sub.add_parser('impact', help='Report affected products; execute no actions')
    impact.add_argument('--mapping', default='04_experiments/adopted_results.json')
    impact.add_argument('--baseline')
    impact.add_argument('--changed', action='append', default=[])
    impact.add_argument('--output')
    args = parser.parse_args()
    try:
        root = resolve_root(ROOT, args.root, args.case)
        if args.action == 'paper-style':
            from paper_plan import active_main
            from paper_style import check_style
            report = check_style(root, active_main(root, args.main))
            output = (root/args.output).resolve()
            if not output.is_relative_to(root) or output.suffix != '.json':
                raise ValueError('style report must be project-local JSON')
            if output.relative_to(root).as_posix() in report['files_sha256']:
                raise ValueError('style report would overwrite manuscript input')
            if output.exists() and load_json(output).get('workflow_check_type') != 'paper_style':
                raise ValueError('refusing to overwrite a nonmatching style report')
            write_report(output, json.dumps(report, ensure_ascii=False, indent=2)+'\n')
            print(f"review_required: {report['candidate_count']} candidates. Report: {args.output}")
            return 0
        if args.action == 'paper-plan':
            from paper_plan import check_plan
            source = project_file(root, args.plan)
            report = check_plan(root, source)
            output = (root/args.output).resolve()
            if not output.is_relative_to(root) or output.suffix != '.json' or output == source:
                raise ValueError('paper-plan output must be a separate project-local JSON report')
            if output.exists() and load_json(output).get('workflow_check_type') != 'paper_plan':
                raise ValueError('refusing to overwrite a nonmatching report')
            if output.relative_to(root).as_posix() in report['files_sha256']:
                raise ValueError('report would overwrite paper-plan evidence')
            write_report(output, json.dumps(report, ensure_ascii=False, indent=2)+'\n')
            print(f"{report['status']}: {len(report['issues'])} issues. Report: {args.output}")
            return int(report['status']=='failed')
        if args.action in ['research-check', 'evidence-snapshot', 'impact']:
            from workflow_checks import research_check, EvidenceGraph
            if args.action == 'research-check':
                source = project_file(root, args.contract)
                report = research_check(root, source)
            else:
                source = project_file(root, args.mapping)
                graph = EvidenceGraph(root, source)
                report = graph.snapshot() if args.action == 'evidence-snapshot' else graph.impact(
                    project_file(root, args.baseline) if args.baseline else None, args.changed)
            if args.output:
                output = (root / args.output).resolve()
                if not output.is_relative_to(root) or output.suffix != '.json' or output == source:
                    raise ValueError('output must be a separate project-local JSON report')
                if output.exists():
                    if args.action == 'evidence-snapshot':
                        raise ValueError('refusing to overwrite immutable evidence snapshot')
                    old = load_json(output)
                    if not isinstance(old, dict) or old.get('workflow_check_type') != report['workflow_check_type']:
                        raise ValueError('refusing to overwrite a nonmatching report')
                write_report(output, json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            if args.output:
                print(f"{report['workflow_check_type']}: {report.get('status', 'reported')}. Report: {args.output}")
            else:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            return int(report.get('status') == 'failed')
        if args.action == 'context':
            required = ['AGENTS.md', 'README.md', 'competition.md', 'STATUS.md', 'WORKFLOW.md']
            missing = [name for name in required if not (root / name).is_file()]
            if missing:
                raise ValueError('missing startup documents: ' + ', '.join(missing))
            pointer = root / '06_paper/active.json'
            from paper_plan import active_main
            current_main = str(active_main(root)) if pointer.exists() or (root/'06_paper/latex/main.tex').exists() else None
            print(json.dumps(dict(project_root=str(root), active_manuscript=current_main, reading_order=[str(root / n) for n in required],
                                  input_directory=str(root / '00_inputs') if (root / '00_inputs').is_dir() else None,
                                  quality_policy=str(root / 'paper_requirements.json'),
                                  scope='Read-only navigation. Read documents and original problem materials before deciding the next stage.'), ensure_ascii=False, indent=2))
            return 0
        if args.action == "summarize":
            count = build_summary(root, (root / args.manifest).resolve(), root / args.output, args.verify)
            print(f"Validated {count} run records. Summary {'verified' if args.verify else 'written'}: {args.output}")
            return 0
        from paper_plan import active_main
        manuscript = active_main(root, args.main)
        output = (root / args.output).resolve()
        if not output.is_relative_to(root) or output.suffix != ".json":
            raise ValueError("preflight output must be a .json report inside project")
        if output.exists():
            previous = load_json(output)
            if not isinstance(previous, dict) or not {"main", "issues", "compilation_performed"} <= previous.keys():
                raise ValueError("refusing to overwrite a file that is not a preflight report")
        policy_path = root / 'paper_requirements.json'
        policy = load_json(policy_path) if policy_path.is_file() else None
        report = preflight(manuscript, args.final, root / args.log if args.log else None, policy)
        report['project_root'] = str(root)
        report['quality_policy'] = dict(path=str(policy_path), sha256=hashlib.sha256(policy_path.read_bytes()).hexdigest()) if policy is not None else None
        protected = {manuscript}
        if args.log:
            protected.add((root / args.log).resolve())
        if output in protected:
            raise ValueError("report would overwrite input")
        write_report(output, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(f"{report['status']}: {len(report['issues'])} issues. Report: {args.output}")
        return int(report["status"] == "failed")
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main_cli())
