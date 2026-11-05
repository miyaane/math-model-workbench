"""Body-page gate behavior with a mocked PDF reader; fixtures are not manuscripts."""
import json
from unittest.mock import patch
from test_workflow_checks import Fixture
from paper_pages import check_pages, sha


class PageTests(Fixture):
    def setUp(self):
        super().setUp()
        self.main=self.put('06_paper/latex/main.tex','synthetic source')
        self.pdf=self.put('06_paper/latex/main.pdf','synthetic bytes; PDF reader mocked')
        self.texts={self.main:'synthetic source'}

    def check(self,total=30,final=True):
        with patch('pypdf.PdfReader') as reader:
            reader.return_value.pages=range(total)
            return check_pages(self.main,self.texts,dict(minimum_body_pages=25),final)

    def audit(self, pages=None, **extra):
        data=dict(schema_version=1,reviewed=True,pdf_sha256=sha(self.pdf),
                  tex_sha256={'main.tex':sha(self.main)},body_pages=pages or list(range(2,27)),
                  boundary_evidence='Synthetic reviewed boundaries; no actual page classification claim.')
        data.update(extra)
        self.put('06_paper/checks/body_pages.json',json.dumps(data))

    def test_short_pdf_rejected_without_inventing_body_count(self):
        r=self.check(14)
        self.assertEqual(self.codes(r),{'body_pages_below_minimum'})
        self.assertIsNone(r['verified_body_pages'])

    def test_total_does_not_substitute_for_body_count(self):
        self.assertEqual(self.codes(self.check()),{'body_page_audit_missing'})

    def test_reviewed_body_count(self):
        self.audit()
        r=self.check()
        self.assertEqual(r['verified_body_pages'],25)
        self.assertEqual(r['issues'],[])

    def test_short_body_in_long_pdf(self):
        self.audit(pages=list(range(2,20)))
        self.assertEqual(self.codes(self.check()),{'body_pages_below_minimum'})

    def test_stale_pdf_or_source_audit_rejected(self):
        for field in ['pdf_sha256','tex_sha256']:
            self.audit(**{field: 'wrong' if field=='pdf_sha256' else {}})
            self.assertEqual(self.codes(self.check()),{'body_page_audit_invalid'})

    def test_duplicate_outside_or_boolean_pages_rejected(self):
        for pages in [[1,1],[31],[True]]:
            self.audit(pages=pages)
            self.assertEqual(self.codes(self.check()),{'body_page_audit_invalid'})

    def test_draft_warns_and_final_blocks(self):
        self.assertEqual(self.check(14,False)['issues'][0]['level'],'warning')
        self.assertEqual(self.check(14,True)['issues'][0]['level'],'error')

    def test_missing_pdf(self):
        main=self.put('other/main.tex')
        self.assertEqual(self.codes(check_pages(main,{main:''},dict(minimum_body_pages=25),True)),{'body_pages_pdf_missing'})

    def test_invalid_minimum(self):
        for value in [True,0,'25']:
            with self.assertRaises(ValueError):
                check_pages(self.main,self.texts,dict(minimum_body_pages=value))

    def test_upper_limit_counts_body_not_appendix(self):
        for count, expected in [(20, set()), (30, set()), (31, {'body_pages_above_maximum'})]:
            self.audit(pages=list(range(2, count+2)))
            with patch('pypdf.PdfReader') as reader:
                reader.return_value.pages=range(45)
                result=check_pages(self.main,self.texts,dict(minimum_body_pages=20,maximum_body_pages=30),True)
            self.assertEqual(self.codes(result),expected)

    def test_case_specific_page_range(self):
        self.audit(pages=list(range(2,17)))
        with patch('pypdf.PdfReader') as reader:
            reader.return_value.pages=range(25)
            result=check_pages(self.main,self.texts,dict(minimum_body_pages=1,maximum_body_pages=20),True)
        self.assertEqual(result['issues'],[])

    def test_invalid_maximum(self):
        for maximum in [True,19,'30']:
            with self.assertRaises(ValueError):
                check_pages(self.main,self.texts,dict(minimum_body_pages=20,maximum_body_pages=maximum))
