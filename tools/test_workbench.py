"""Fixtures are synthetic tool tests, never competition experiment data."""
import json
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from workbench import build_summary, load_json, main_cli, preflight, read_results, summary_text, tex_text


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        # Keep disposable fixtures in the intended project test directory.
        test_base = Path(__file__).resolve().parent / ".test_tmp"
        test_base.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=test_base)
        def cleanup():
            target = Path(self.tmp.name).resolve()
            if not target.is_relative_to(test_base.resolve()):
                raise ValueError("test cleanup outside intended directory")
            self.tmp.cleanup()
        self.addCleanup(cleanup)
        self.root = Path(self.tmp.name)

    def put(self, name, text="test fixture"):
        file = self.root / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")
        return file

    def check(self, text, final=False):
        return preflight(self.put("main.tex", text), final)

    def codes(self, report):
        return {issue["code"] for issue in report["issues"]}

    def result_fixture(self, status="success"):
        for name in ("card.md", "config.json", "env.txt", "log.txt", "data.csv", "out.csv", "model.py"):
            self.put(name)
        run = dict(schema_version=1, run_id="fixture", question="Q1", model_id="baseline",
                   status=status, recorded_at="2026-10-31T10:00:00+08:00", command="synthetic test",
                   code_version="test-only", seed=None, inputs=["data.csv"], artifacts=["out.csv"],
                   code_files=["model.py"],
                   experiment_card="card.md", config="config.json", environment="env.txt", log="log.txt",
                   metrics={"error": dict(value=0.25, unit="1", direction="min", definition="synthetic fixture")})
        if status != "success":
            run["failure_reason"] = "test-only failure"
        self.put("run.json", json.dumps(run))
        manifest = self.put("manifest.json", json.dumps(dict(schema_version=1, runs=["run.json"])))
        return run, manifest

    def test_graphicspath_extension_and_main_relative_inputs(self):
        self.put("images/chart.pdf")
        self.put("sections/q1.tex", r"\includegraphics{chart}\input{sections/detail}")
        self.put("sections/detail.tex", "Details")
        report = self.check(r"\graphicspath{{images/}}\input{sections/q1}")
        self.assertEqual(report["status"], "static_checks_passed")
        self.assertEqual(len(report["files_scanned"]), 3)

    def test_comments_and_verbatim_not_scanned(self):
        text = "% TODO AGENTS.md \\input{missing}\n" + r"\begin{verbatim}\includegraphics{missing} TODO\end{verbatim}"
        self.assertEqual(self.check(text, final=True)["issues"], [])
        self.assertIn(r"\%", tex_text(r"Text \% visible % hidden"))
        self.assertNotIn("hidden", tex_text(r"Text \% visible % hidden"))
        self.assertNotIn("hidden", tex_text(r"Text \\% hidden"))

    def test_placeholder_draft_vs_final(self):
        self.assertEqual(self.check("待填写")["status"], "static_checks_passed")
        self.assertEqual(self.check("待填写", final=True)["status"], "failed")

    def test_missing_resources_fail(self):
        report = self.check(r"\input{missing}\includegraphics{missing}\bibliography{missing}")
        self.assertEqual(report["status"], "failed")
        self.assertTrue({"missing_tex", "missing_image", "missing_bibliography"} <= self.codes(report))

    def test_dynamic_resource_warns(self):
        report = self.check(r"\input{\sectionname}\includegraphics{\plotname}")
        self.assertEqual(report["status"], "static_checks_passed")
        self.assertTrue({"dynamic_input", "dynamic_image"} <= self.codes(report))

    def test_bib_and_references(self):
        self.put("refs.bib", "@article{realkey, title={Fixture}}")
        report = self.check(r"\bibliography{refs}\cite{realkey}\label{eq:x}\eqref{eq:x}\cite{missing}\ref{missing}")
        self.assertEqual(self.codes(report), {"unresolved_ref", "unresolved_cite"})

    def test_cycle_terminates(self):
        self.put("a.tex", r"\input{main}")
        self.assertIn("repeated_input", self.codes(self.check(r"\input{a}")))

    def test_duplicate_labels(self):
        self.assertIn("duplicate_label", self.codes(self.check(r"\label{x}\label{x}")))

    def test_compile_log_is_not_compilation(self):
        main = self.put("main.tex", "body")
        log = self.put("main.log", "! Fatal error\nOverfull box")
        report = preflight(main, log=log)
        self.assertEqual(report["status"], "failed")
        self.assertFalse(report["compilation_performed"])
        self.assertIn("compile_warning", self.codes(report))

    def test_result_success_and_failure_separation(self):
        _, manifest = self.result_fixture()
        self.assertIn("0.25", summary_text(read_results(self.root, manifest)))
        self.result_fixture(status="failed")
        text = summary_text(read_results(self.root, manifest))
        self.assertNotIn("0.25", text)
        self.assertIn("test-only failure", text)

    def test_empty_registry_is_not_evidence(self):
        manifest = self.put("manifest.json", '{"schema_version":1,"runs":[]}')
        self.assertIn("尚无", summary_text(read_results(self.root, manifest)))

    def test_invalid_metric_and_missing_provenance(self):
        for invalid in (True, float("nan"), float("inf"), "0.25"):
            run, manifest = self.result_fixture()
            run["metrics"]["error"]["value"] = invalid
            self.put("run.json", json.dumps(run))
            with self.assertRaises(ValueError):
                read_results(self.root, manifest)
        run, manifest = self.result_fixture()
        run["log"] = "not-present.log"
        self.put("run.json", json.dumps(run))
        with self.assertRaises(ValueError):
            read_results(self.root, manifest)

    def test_duplicate_record_and_path_escape(self):
        _, manifest = self.result_fixture()
        manifest.write_text('{"schema_version":1,"runs":["run.json","run.json"]}', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_results(self.root, manifest)
        manifest.write_text('{"schema_version":1,"runs":["../outside.json"]}', encoding="utf-8")
        with self.assertRaises(ValueError):
            read_results(self.root, manifest)

    def test_duplicate_keys_rejected(self):
        file = self.put("bad.json", '{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            load_json(file)

    def test_commented_literal_does_not_hide_real_errors(self):
        text = "% \\begin{verbatim}\n\\input{missing}\n% \\end{verbatim}"
        self.assertIn("missing_tex", self.codes(self.check(text)))
        self.assertIn("TODO", tex_text("% \\verb|\nTODO\n% |"))

    def test_summary_fingerprints_detect_changed_evidence(self):
        _, manifest = self.result_fixture()
        output = self.root / "summary.md"
        build_summary(self.root, manifest, output)
        build_summary(self.root, manifest, output, verify=True)
        for file in ("data.csv", "out.csv", "model.py", "config.json", "log.txt"):
            original = (self.root / file).read_text(encoding="utf-8")
            self.put(file, "changed")
            with self.assertRaises(ValueError):
                build_summary(self.root, manifest, output, verify=True)
            self.put(file, original)
        output.write_text("modified summary", encoding="utf-8")
        with self.assertRaises(ValueError):
            build_summary(self.root, manifest, output, verify=True)

    def test_invalid_run_preserves_existing_summary(self):
        _, manifest = self.result_fixture()
        output = self.root / "summary.md"
        build_summary(self.root, manifest, output)
        original = output.read_bytes()
        self.put("run.json", "invalid JSON")
        with self.assertRaises(ValueError):
            build_summary(self.root, manifest, output)
        self.assertEqual(original, output.read_bytes())

    def test_summary_cannot_overwrite_evidence(self):
        _, manifest = self.result_fixture()
        with self.assertRaises(ValueError):
            build_summary(self.root, manifest, self.root / "card.md")

    def test_end_to_end_synthetic_handoff(self):
        _, manifest = self.result_fixture()
        build_summary(self.root, manifest, self.root / "summary.md")
        self.put("plot.pdf")
        self.put("refs.bib", "@article{fixture, title={Synthetic test only}}")
        report = self.check(r"\section{Results}\label{sec:r}\includegraphics{plot}\cite{fixture}\bibliography{refs}\ref{sec:r}", final=True)
        self.assertEqual(report["issues"], [])
        self.assertFalse(report["compilation_performed"])
        self.assertEqual(build_summary(self.root, manifest, self.root / "summary.md", verify=True), 1)

    def test_escaped_command_not_treated_as_resource(self):
        self.assertEqual(self.check(r"\\includegraphics{not-a-command}")["issues"], [])

    def call_cli(self, *args):
        with patch("sys.argv", ["workbench.py", "--root", str(self.root), *args]):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                return main_cli()

    def test_cli_protects_nonreport_json(self):
        self.put("main.tex", "body")
        source = self.put("manifest.json", '{"schema_version":1,"runs":[]}')
        original = source.read_bytes()
        self.assertEqual(self.call_cli("preflight", "--main", "main.tex", "--output", "manifest.json"), 2)
        self.assertEqual(source.read_bytes(), original)

    def test_cli_draft_and_final_exit_codes(self):
        self.put("main.tex", "TODO")
        self.assertEqual(self.call_cli("preflight", "--main", "main.tex", "--output", "report.json"), 0)
        self.assertEqual(self.call_cli("preflight", "--main", "main.tex", "--output", "report.json", "--final"), 1)


if __name__ == "__main__":
    unittest.main()
