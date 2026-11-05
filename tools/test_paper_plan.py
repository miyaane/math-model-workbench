"""Synthetic editorial fixtures; never research evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from paper_plan import active_main, check_plan


class PaperPlanTest(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parent/'.test_tmp'
        base.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base)
        def cleanup():
            if not Path(self.tmp.name).resolve().is_relative_to(base.resolve()):
                raise ValueError('test cleanup outside workspace test directory')
            self.tmp.cleanup()
        self.addCleanup(cleanup)
        self.root=Path(self.tmp.name)
        self.write('paper_requirements.json',dict(schema_version=1,minimum_body_pages=25,reference_target=1,reference_tolerance=0))
        self.write('evidence.json',{'metric':'synthetic'})
        self.ref=dict(key='a',title='Synthetic',authors='Fixture',year=2000,status='verified_for_claim',
            source_urls=['https://example.org/source'],checked_on='2026-11-01',read_depth='synthetic',
            supports=[dict(section='Q1',claim='Synthetic claim')])
        self.plan=dict(schema_version=1,main='main.tex',references='refs.json',
            sections=[dict(id='Q1',purpose='Synthetic section',planned_body_pages=25,evidence=['evidence.json'])])
        self.write('main.tex',r'\cite{a}\begin{thebibliography}{9}\bibitem{a}Synthetic\end{thebibliography}')
        self.write('refs.json',dict(schema_version=1,references=[self.ref]))
        self.write('plan.json',self.plan)

    def write(self,name,value):
        path=self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(value if isinstance(value,str) else json.dumps(value),encoding='utf-8')
        return path

    def check(self):
        return check_plan(self.root,self.root/'plan.json')

    def test_record_pass_is_not_page_or_truth_certification(self):
        report=self.check()
        self.assertEqual(report['status'],'record_checks_passed')
        self.assertFalse(report['actual_body_pages_verified'])

    def test_early_citation_gap(self):
        self.write('main.tex',r'\cite{unknown}')
        codes={i['code'] for i in self.check()['issues']}
        self.assertIn('citation_without_verified_record',codes)
        self.assertIn('mapped_reference_not_cited',codes)

    def test_provisional_source_never_counts_as_verified(self):
        self.ref['status']='candidate'
        self.write('refs.json',dict(schema_version=1,references=[self.ref]))
        self.assertIn('reference_not_verified',{i['code'] for i in self.check()['issues']})

    def test_missing_section_evidence_is_rejected(self):
        self.plan['sections'][0]['evidence']=['absent.json']
        self.write('plan.json',self.plan)
        with self.assertRaises(ValueError):self.check()

    def test_page_allocation_shortfall_before_pdf(self):
        self.plan['sections'][0]['planned_body_pages']=17
        self.write('plan.json',self.plan)
        self.assertIn('planned_body_shortfall',{i['code'] for i in self.check()['issues']})

    def test_nonfinite_and_bool_allocations_rejected(self):
        for value in [True,-1,float('inf')]:
            self.plan['sections'][0]['planned_body_pages']=value
            self.write('plan.json',self.plan)
            with self.assertRaises(ValueError):self.check()

    def test_unknown_claim_section(self):
        self.ref['supports'][0]['section']='absent'
        self.write('refs.json',dict(schema_version=1,references=[self.ref]))
        self.assertIn('invalid_claim_mapping',{i['code'] for i in self.check()['issues']})

    def test_evidence_change_changes_fingerprint(self):
        before=self.check()['files_sha256']
        self.write('evidence.json',{'metric':'changed fixture'})
        self.assertNotEqual(before,self.check()['files_sha256'])

    def test_active_manuscript_and_explicit_override(self):
        self.write('06_paper/active.json',dict(schema_version=1,main='main.tex'))
        self.write('historical.tex','old fixture')
        self.assertEqual(active_main(self.root),self.root/'main.tex')
        self.assertEqual(active_main(self.root,'historical.tex'),self.root/'historical.tex')

    def test_active_pointer_escape_rejected(self):
        self.write('06_paper/active.json',dict(schema_version=1,main='../outside.tex'))
        with self.assertRaises(ValueError):active_main(self.root)

if __name__=='__main__':unittest.main()
