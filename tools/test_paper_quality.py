"""Behavioral regression fixtures only; never modeling evidence."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from workbench import main_cli, preflight, resolve_root
import initialize_case


POLICY = dict(schema_version=1, reference_target=2, reference_tolerance=0,
              require_background=True, require_restatement=True, require_bold_abstract_numbers=True)


class QualityTest(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parent / '.test_tmp'
        base.mkdir(exist_ok=True)
        tmp = tempfile.TemporaryDirectory(dir=base)
        self.root = Path(tmp.name)
        def cleanup():
            if not self.root.resolve().is_relative_to(base.resolve()):
                raise ValueError('unexpected cleanup target')
            tmp.cleanup()
        self.addCleanup(cleanup)

    def put(self, name, content):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding='utf-8')
        return p

    def paper(self, abstract=r'Samples \textbf{20}; proportion \textbf{80\%}.'):
        return (r'\begin{document}\begin{abstract}' + abstract +
                r'\end{abstract}\section{问题背景}Evidence\cite{a}.'
                r'\subsection{问题重述}Task\cite{b}.'
                r'\begin{thebibliography}{9}\bibitem{a}Source A.\bibitem{b}Source B.\end{thebibliography}\end{document}')

    def check(self, text, final=True):
        return preflight(self.put('main.tex', text), final=final, quality_policy=POLICY)

    def codes(self, report):
        return {i['code'] for i in report['issues']}

    def test_compliant_static_subset_passes_and_keeps_manual_checks(self):
        r = self.check(self.paper())
        self.assertEqual(r['status'], 'static_checks_passed')
        self.assertEqual(r['issues'], [])
        self.assertEqual(r['paper_quality']['reference_count'], 2)
        self.assertTrue(r['paper_quality']['manual_checks'])
        self.assertFalse(r['compilation_performed'])

    def test_known_real_gap_pattern_is_not_a_pass(self):
        # Mirrors the earlier case failure pattern without using real patient data.
        text = self.paper('267 samples, Brier 0.10996.')
        text = text.replace('问题背景', '问题分析与研究路线').replace('问题重述', '研究路线')
        r = self.check(text)
        self.assertEqual(r['status'], 'failed')
        self.assertTrue({'missing_background', 'missing_restatement', 'abstract_number_not_bold'} <= self.codes(r))

    def test_draft_warns_final_blocks(self):
        r = self.check(self.paper('20 samples.'), final=False)
        self.assertEqual(r['status'], 'static_checks_passed')
        self.assertTrue(all(i['level'] == 'warning' for i in r['issues']))
        self.assertEqual(self.check(self.paper('20 samples.'))['status'], 'failed')

    def test_nested_input_and_bold_scientific_numbers(self):
        self.put('body.tex', self.paper(r'Effects $\boldsymbol{-1.2\times10^{-3}}$ and \textbf{三}项.'))
        r = self.check(r'\input{body}')
        self.assertNotIn('abstract_number_not_bold', self.codes(r))
        self.assertEqual(r['status'], 'static_checks_passed')

    def test_bold_group_does_not_hide_following_unbold_number(self):
        r = self.check(self.paper(r'\textbf{20} samples; 30 tests.'))
        details = [i['detail'] for i in r['issues'] if i['code'] == 'abstract_number_not_bold']
        self.assertEqual(len(details), 1)
        self.assertIn('30', details[0])

    def test_percent_symbol_must_be_in_same_bold_group(self):
        self.assertIn('abstract_percent_outside_bold', self.codes(self.check(self.paper(r'Rate \textbf{80}\%.'))))

    def test_whole_abstract_bold_is_not_numerical_emphasis(self):
        self.assertIn('abstract_whole_bold', self.codes(self.check(self.paper(r'\textbf{We use 20 samples and explain all results here.}'))))

    def test_appendix_or_abstract_citations_do_not_cover_main_body(self):
        text = self.paper().replace(r'Task\cite{b}', 'Task').replace(r'\end{document}', r'\appendix Details\cite{b}\end{document}')
        self.assertIn('reference_not_cited_in_body', self.codes(self.check(text)))

    def test_unused_bib_database_keys_are_not_printed_references(self):
        self.put('library.bib', '@article{a,title={A}}\n@article{b,title={B}}\n@article{unused,title={Unused}}')
        text = self.paper()
        start = text.index(r'\begin{thebibliography}')
        text = text[:start] + r'\bibliography{library}\end{document}'
        r = self.check(text)
        self.assertEqual(r['paper_quality']['reference_count'], 2)
        self.assertNotIn('reference_not_cited_in_body', self.codes(r))

    def test_nocite_star_cannot_manufacture_reference_coverage(self):
        self.put('library.bib', '@article{a,title={A}}\n@article{b,title={B}}\n@article{unused,title={Unused}}')
        text = self.paper().replace(r'\end{document}', r'\nocite{*}\bibliography{library}\end{document}')
        r = self.check(text)
        self.assertTrue({'nocite_all', 'reference_not_cited_in_body', 'reference_count'} <= self.codes(r))

    def test_comments_macros_and_reference_titles_do_not_supply_body_evidence(self):
        text = self.paper().replace(r'\subsection{问题重述}Task\cite{b}.', r'\newcommand{\hidden}{\subsection{问题重述}\cite{b}}')
        text = text.replace('Source B.', r'Source B with \cite{b}.')
        text += '\n% \\subsection{问题重述} \\cite{b}\n'
        self.assertTrue({'missing_restatement', 'reference_not_cited_in_body'} <= self.codes(self.check(text)))

    def test_reference_count_is_configured_not_hardcoded(self):
        r = preflight(self.put('main.tex', self.paper()), final=True, quality_policy={**POLICY, 'reference_target': 20, 'reference_tolerance': 2})
        self.assertIn('reference_count', self.codes(r))

    def test_english_equivalent_sections(self):
        self.assertEqual(self.check(self.paper().replace('问题背景', 'Background').replace('问题重述', 'Problem Restatement'))['status'], 'static_checks_passed')

    def test_reference_metadata_is_not_a_false_check_result(self):
        self.assertIn('文献元数据真实性与实际支持内容', self.check(self.paper())['paper_quality']['manual_checks'])

    def test_escaped_fake_heading_or_citation_does_not_count(self):
        text = self.paper().replace(r'\subsection{问题重述}Task\cite{b}.', r'\\subsection{问题重述}Task\\cite{b}.')
        self.assertTrue({'missing_restatement', 'reference_not_cited_in_body'} <= self.codes(self.check(text)))

    def test_initializer_propagates_tools_policy_and_context_without_old_results(self):
        actual = Path(__file__).resolve().parent
        for name in ['initialize_case.py', 'workbench.py', 'paper_quality.py', 'paper_pages.py', 'paper_plan.py', 'paper_style.py', 'workflow_checks.py', 'README.md']:
            self.put('tools/' + name, (actual / name).read_text(encoding='utf-8'))
        for name in ['AGENTS.md', 'WORKFLOW.md']:
            self.put(name, '# Generic workflow')
        self.put('templates/model.md', '# Model template')
        self.put('paper_requirements.json', json.dumps(POLICY))
        self.put('templates/results_guide.md', '# Generic result guide')
        self.put('04_experiments/old/result.json', 'old evidence not to copy')
        self.put('source/problem.txt', 'Synthetic case fixture, no actual modeling claim.')
        with patch('initialize_case.ROOT', self.root), patch('sys.argv', ['initialize_case.py', '--source', str(self.root / 'source'), '--name', 'fresh']), contextlib.redirect_stdout(io.StringIO()):
            initialize_case.main()
        dest = self.root / 'cases/fresh'
        self.assertEqual((dest / '00_inputs/source/problem.txt').read_bytes(), (self.root / 'source/problem.txt').read_bytes())
        self.assertEqual(json.loads((dest / 'paper_requirements.json').read_text(encoding='utf-8')), POLICY)
        self.assertTrue((dest / 'tools/paper_quality.py').is_file())
        self.assertTrue(all((dest / n).is_file() for n in ['AGENTS.md', 'README.md', 'competition.md', 'STATUS.md', 'WORKFLOW.md']))
        self.assertFalse((dest / '04_experiments/old').exists())
        self.assertEqual(json.loads((dest / '04_experiments/results_manifest.json').read_text())['runs'], [])

    def test_initializer_refuses_source_containing_new_destination(self):
        with patch('initialize_case.ROOT', self.root), patch('sys.argv', ['initialize_case.py', '--source', str(self.root), '--name', 'fresh']):
            with self.assertRaises(SystemExit):
                initialize_case.main()
        self.assertFalse((self.root / 'cases/fresh').exists())

    def test_active_case_explicit_override_and_invalid_pointer(self):
        case = self.root / 'cases/c'
        case.mkdir(parents=True)
        self.put('workspace.json', json.dumps(dict(schema_version=1, active_case='cases/c')))
        self.assertEqual(resolve_root(self.root), case)
        self.assertEqual(resolve_root(self.root, explicit_root=self.root), self.root)
        with self.assertRaises(ValueError):
            resolve_root(self.root, case='../outside')
        self.put('workspace.json', json.dumps(dict(schema_version=1, active_case='cases/missing')))
        with self.assertRaises(ValueError):
            resolve_root(self.root)

    def test_cli_uses_active_case_policy_and_reports_quality_failure(self):
        child = self.root / 'cases/c'
        child.mkdir(parents=True)
        self.put('workspace.json', json.dumps(dict(schema_version=1, active_case='cases/c')))
        self.put('cases/c/paper_requirements.json', json.dumps(POLICY))
        self.put('cases/c/06_paper/latex/main.tex', self.paper('20 samples.'))
        with patch('workbench.ROOT', self.root), patch('sys.argv', ['workbench.py', 'preflight', '--final']), contextlib.redirect_stdout(io.StringIO()):
            code = main_cli()
        self.assertEqual(code, 1)
        self.assertTrue((child / '06_paper/checks/preflight.json').is_file())
        self.assertFalse((self.root / '06_paper/checks/preflight.json').exists())


if __name__ == '__main__':
    unittest.main()
