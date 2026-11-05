"""Synthetic workflow behavior tests; no competition evidence is generated."""
import json
import unittest
import contextlib
import io
from unittest.mock import patch
from test_workbench import WorkspaceTest
from workflow_checks import EvidenceGraph, research_check
from workbench import main_cli


class Fixture(unittest.TestCase):
    setUp = WorkspaceTest.setUp
    put = WorkspaceTest.put
    codes = WorkspaceTest.codes
    result_fixture = WorkspaceTest.result_fixture


class ResearchTests(Fixture):
    def contract(self, **changes):
        q = dict(id='Q2', requested_target='first event', modeled_target='first event',
                 independent_unit='person', validation_unit='person', claim_scope='full_target',
                 evidence=['proof.md'])
        q.update(changes)
        self.put('proof.md')
        return self.put('contract.json', json.dumps(dict(schema_version=1, questions=[q])))

    def test_three_known_failure_classes(self):
        p = self.contract(modeled_target='current probability',
                          shape=dict(basis='positive_hinge', nonnegative_coefficients=True,
                                     declared_properties=['nondecreasing']),
                          time_unit='week', time_records=[dict(available_at=13, decide_at=11)])
        report = research_check(self.root, p)
        self.assertEqual(self.codes(report), {'target_substitution','hidden_shape_constraint','decision_before_input'})
        self.assertFalse(report['scientific_validity_certified'])

    def test_conditional_target_retains_warning(self):
        report = research_check(self.root, self.contract(modeled_target='proxy', claim_scope='conditional_proxy'))
        self.assertEqual(report['status'], 'record_consistent_review_required')
        self.assertIn('conditional_target', self.codes(report))

    def test_repeated_measurements_and_partition(self):
        report = research_check(self.root, self.contract(validation_unit='record', repeated_measurements=True))
        self.assertEqual(self.codes(report), {'validation_unit_mismatch','repeated_measurements_unhandled'})

    def test_nonfinite_time_rejected(self):
        with self.assertRaises(ValueError):
            research_check(self.root, self.contract(time_unit='week', time_records=[dict(available_at=float('nan'), decide_at=11)]))

    def test_evidence_escape_rejected(self):
        with self.assertRaises(ValueError):
            research_check(self.root, self.contract(evidence=['../escape.md']))


class GraphTests(Fixture):
    def graph(self, status='success', products=None):
        self.result_fixture(status)
        self.put('paper.tex')
        self.put('chart.pdf')
        data = dict(schema_version=1, results_manifest='manifest.json',
                    selections={'estimate':dict(run='run.json',path='out.csv')},
                    products=products or {
                        'chart':dict(depends_on=['estimate'],sources=[],outputs=['chart.pdf']),
                        'paper':dict(depends_on=['chart'],sources=['paper.tex'],outputs=[]),
                        'review':dict(depends_on=['paper'],sources=[],outputs=[])})
        return EvidenceGraph(self.root, self.put('map.json', json.dumps(data)))

    def test_only_downstream_products_affected(self):
        g = self.graph()
        r = g.impact(changed=['paper.tex'])
        self.assertEqual(r['affected_products'], ['paper','review'])
        self.assertEqual(r['affected_selections'], [])
        self.assertEqual(g.impact(changed=['data.csv'])['affected_products'], ['chart','paper','review'])

    def test_unchanged_snapshot_and_mutated_output(self):
        g = self.graph()
        p = self.put('snapshot.json', json.dumps(g.snapshot()))
        self.assertEqual(g.impact(p)['affected_products'], [])
        self.put('out.csv', 'changed fixture')
        self.assertEqual(g.impact(p)['affected_products'], ['chart','paper','review'])

    def test_failed_run_cannot_be_adopted(self):
        with self.assertRaises(ValueError):
            self.graph('failed')

    def test_cycle_rejected(self):
        with self.assertRaises(ValueError):
            self.graph(products={'a':dict(depends_on=['b'],outputs=[]),'b':dict(depends_on=['a'],outputs=[])})

    def test_unknown_dependency_rejected(self):
        with self.assertRaises(ValueError):
            self.graph(products={'a':dict(depends_on=['missing'],outputs=[])})

    def test_output_escape_rejected(self):
        with self.assertRaises(ValueError):
            self.graph(products={'a':dict(depends_on=['estimate'],outputs=['../bad'])})

    def test_unknown_changes_reported_without_writes(self):
        g = self.graph()
        before = g.mapping.read_bytes()
        r = g.impact(changed=['unmapped.py'])
        self.assertEqual(r['unknown_changed_inputs'], ['unmapped.py'])
        self.assertEqual(g.mapping.read_bytes(), before)

    def test_cli_snapshot_is_immutable(self):
        self.graph()
        argv = ['workbench.py', '--root', str(self.root), 'evidence-snapshot', '--mapping', 'map.json', '--output', 'snapshot.json']
        with patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main_cli(), 0)
            frozen = (self.root/'snapshot.json').read_bytes()
            self.assertEqual(main_cli(), 2)
            self.assertEqual((self.root/'snapshot.json').read_bytes(), frozen)

    def test_cli_report_cannot_overwrite_inputs_or_unrelated_json(self):
        self.graph()
        for output in ['map.json', '../escape.json', 'run.json']:
            before = (self.root/'run.json').read_bytes()
            argv = ['workbench.py', '--root', str(self.root), 'impact', '--mapping', 'map.json', '--output', output]
            with patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main_cli(), 2)
            self.assertEqual((self.root/'run.json').read_bytes(), before)


del WorkspaceTest
