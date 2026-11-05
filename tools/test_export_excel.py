import tempfile
from pathlib import Path
import unittest
import zipfile
from export_excel import export_numeric


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_root=Path(__file__).resolve().parent/'.test_tmp'
        cls.temp_root.mkdir(exist_ok=True)

    def template(self, root, formula=False):
        p = root/'template.xlsx'
        with zipfile.ZipFile(p, 'w') as z:
            z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="结果" sheetId="1" r:id="rId1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" s="4"/><c r="B1"><v>7</v></c>'+('<c r="C1"><f>A1+1</f><v>2</v></c>' if formula else '')+'</row></sheetData></worksheet>')
            z.writestr('custom.bin', b'\x00preserve\xff')
            z.writestr('xl/styles.xml','<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cellXfs count="5">'+5*'<xf numFmtId="0" fontId="0"/>'+'</cellXfs></styleSheet>')
        return p

    def test_precision_and_preservation(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as t:
            r=Path(t); p=self.template(r); out=r/'out.xlsx'
            a=export_numeric(p,out,{'结果':{'A1':0.1234567890123456}})
            self.assertEqual(a['checked_numeric_cells'],1)
            with zipfile.ZipFile(out) as z:
                self.assertEqual(z.read('custom.bin'),b'\x00preserve\xff')
                self.assertIn(b'<c r="B1"><v>7</v></c>',z.read('xl/worksheets/sheet1.xml'))
                self.assertIn(b's="4"',z.read('xl/worksheets/sheet1.xml'))
            with self.assertRaises(ValueError): export_numeric(p,out,{'结果':{'A1':2}})

    def test_reject_bad_inputs_without_output(self):
        for updates in [{'结果':{'A1':float('nan')}},{'结果':{'A1':True}}, {'结果':{'Z9':2}}, {'missing':{'A1':2}}, {}]:
            with self.subTest(updates=updates), tempfile.TemporaryDirectory(dir=self.temp_root) as t:
                r=Path(t);p=self.template(r);out=r/'out.xlsx'
                with self.assertRaises(ValueError):export_numeric(p,out,updates)
                self.assertFalse(out.exists())

    def test_reject_formula_cache(self):
        with tempfile.TemporaryDirectory(dir=self.temp_root) as t:
            r=Path(t);p=self.template(r,True)
            with self.assertRaisesRegex(ValueError,'recalculation'):export_numeric(p,r/'out.xlsx',{'结果':{'A1':2}})

    def test_display_precision_does_not_round_values(self):
        import xml.etree.ElementTree as ET
        with tempfile.TemporaryDirectory(dir=self.temp_root) as t:
            r=Path(t);p=self.template(r);out=r/'out.xlsx'
            export_numeric(p,out,{'结果':{'A1':1.23456789}},number_format='0.###')
            with zipfile.ZipFile(out) as z:
                ET.fromstring(z.read('xl/styles.xml'))
                self.assertIn(b'formatCode="0.###"',z.read('xl/styles.xml'))
                self.assertIn(b'<v>1.23456789</v>',z.read('xl/worksheets/sheet1.xml'))


if __name__=='__main__':unittest.main()
