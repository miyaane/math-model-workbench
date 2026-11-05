"""Synthetic prose tests: candidate localization, scientific-boundary retention and safe outputs."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from paper_style import check_style
from workbench import main_cli

class StyleTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).parent/'.test_tmp';base.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve()
    def put(self,name,text):
        path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8');return path
    def test_chinese_candidates_have_locations_without_rewriting(self):
        source='直接报告实际结果。\n\n虽然数据有限，但结果是可靠的。仅供参考。'
        path=self.put('main.tex',source);r=check_style(self.root,path)
        self.assertEqual(path.read_text(encoding='utf-8'),source)
        self.assertGreaterEqual(r['candidate_count'],3)
        self.assertTrue(all(f['line']==3 for f in r['findings']))
        self.assertFalse(r['quality_accepted'])
    def test_no_hits_is_still_semantic_review_required(self):
        r=check_style(self.root,self.put('main.tex','报告实测温度、误差与适用工况。'))
        self.assertEqual(r['candidate_count'],0);self.assertEqual(r['status'],'review_required')
    def test_comments_literals_preamble_and_bibliography_not_prose(self):
        text=r'''\newcommand{\x}{仅供参考}
\begin{document}
% 不能保证
\begin{verbatim}不能保证\end{verbatim}
\verb|仅供参考|
直接陈述证据。
\begin{thebibliography}{1}仅供参考\end{thebibliography}
\end{document}'''
        self.assertEqual(check_style(self.root,self.put('main.tex',text))['candidate_count'],0)
    def test_english_and_clustered_qualifiers_preserve_review_boundary(self):
        text='This is for reference only and cannot guarantee transfer.\n\nThe effect may arise, could vary and might depend on temperature.'
        r=check_style(self.root,self.put('main.tex',text))
        self.assertIn('clustered_qualifiers',{f['category'] for f in r['findings']})
        self.assertTrue(all(f['decision']=='pending_context_review' for f in r['findings']))
    def test_input_files_and_fingerprints_change_with_prose(self):
        main=self.put('latex/main.tex',r'\input{body}')
        body=self.put('latex/body.tex','仅供参考。仅供参考。')
        before=check_style(self.root,main);body.write_text('以给定工况为适用范围。',encoding='utf-8')
        after=check_style(self.root,main)
        self.assertEqual(before['repeated_phrases']['仅供参考'],2)
        self.assertNotEqual(before['files_sha256'],after['files_sha256'])
        self.assertEqual(after['candidate_count'],0)
    def test_outside_project_input_refused(self):
        main=self.put('main.tex',r'\input{../outside}')
        with self.assertRaisesRegex(ValueError,'outside project'):check_style(self.root,main)
    def test_cli_never_overwrites_unrelated_json(self):
        self.put('06_paper/latex/main.tex','仅供参考。');original=self.put('evidence.json','{"source":"immutable fixture"}')
        args=['workbench','--root',str(self.root),'paper-style','--output','evidence.json']
        with patch('sys.argv',args),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):code=main_cli()
        self.assertEqual(code,2);self.assertEqual(json.loads(original.read_text())['source'],'immutable fixture')
        args[-1]='06_paper/checks/style.json'
        with patch('sys.argv',args),contextlib.redirect_stdout(io.StringIO()):code=main_cli()
        self.assertEqual(code,0)
        self.assertEqual(json.loads((self.root/args[-1]).read_text(encoding='utf-8'))['status'],'review_required')

if __name__=='__main__':unittest.main()
