"""Synthetic import tests verify only new input and reusable framework are inherited."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from initialize_case import initialize_case,ROOT,TOOL_FILES

class InitializeTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).parent/'.test_tmp';base.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.ws=self.base/'workspace';self.ws.mkdir()
        for name in ['AGENTS.md','WORKFLOW.md','paper_requirements.json']:shutil.copy2(ROOT/name,self.ws/name)
        shutil.copytree(ROOT/'templates',self.ws/'templates');(self.ws/'tools').mkdir()
        for name in TOOL_FILES:shutil.copy2(ROOT/'tools'/name,self.ws/'tools'/name)
        (self.ws/'workspace.json').write_text('{"schema_version":1,"active_case":"."}',encoding='utf-8')
        stale=self.ws/'cases/stale_case';stale.mkdir(parents=True);(stale/'old_fixture.csv').write_text('synthetic stale sentinel')
        self.source=self.base/'new_inputs';self.source.mkdir();(self.source/'problem.txt').write_text('synthetic new problem')
    def test_only_framework_and_new_input_and_empty_records(self):
        dest=initialize_case(self.source,'fresh_case',self.ws)
        self.assertTrue((dest/'tools/paper_style.py').exists())
        self.assertTrue((dest/'templates/question_completion.md').exists())
        self.assertTrue((dest/'templates/paper_style_review.md').exists())
        self.assertFalse(list(dest.rglob('old_fixture.csv')))
        self.assertEqual(json.loads((dest/'04_experiments/results_manifest.json').read_text())['runs'],[])
        self.assertEqual(json.loads((dest/'04_experiments/adopted_results.json').read_text())['selections'],{})
        self.assertFalse((dest/'06_paper/active.json').exists());self.assertFalse((dest/'06_paper/latex/main.tex').exists())
        self.assertEqual(json.loads((self.ws/'workspace.json').read_text())['active_case'],'.')
        inventory=json.loads((dest/'01_problem/input_inventory.json').read_text(encoding='utf-8'))
        self.assertEqual(len(inventory),1)
        self.assertEqual((dest/inventory[0]['copy']).read_bytes(),(self.source/'problem.txt').read_bytes())
    def test_escape_recursive_source_and_existing_target_refused(self):
        with self.assertRaises(ValueError):initialize_case(self.source,'../escape',self.ws)
        with self.assertRaises(ValueError):initialize_case(self.ws,'recursive',self.ws)
        dest=initialize_case(self.source,'same',self.ws)
        with self.assertRaises(ValueError):initialize_case(self.source,'same',self.ws)
        self.assertTrue((dest/'00_inputs/new_inputs/problem.txt').exists())

if __name__=='__main__':unittest.main()
