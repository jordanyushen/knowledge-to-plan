"""Formula/diagram validation tests; they do not certify teaching facts."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from build_learning_site import build
from test_workflow import fixture
from validate_plan import validate_plan

EXAMPLE = Path(__file__).resolve().parents[1] / 'assets' / 'stem-example' / 'plan.json'
MATH_NS = 'http://www.w3.org/1998/Math/MathML'
SVG_NS = 'http://www.w3.org/2000/svg'


def stem_fixture():
    return json.loads(EXAMPLE.read_text(encoding='utf-8'))


def formula(plan):
    return plan['lessons'][0]['sections'][0]['formulas'][0]


def diagram(plan):
    return plan['lessons'][0]['sections'][1]['diagrams'][0]


class StemPlanTests(unittest.TestCase):
    def test_optional_stem_fields_preserve_legacy_courses(self):
        self.assertEqual(validate_plan(fixture()), [])
        self.assertEqual(validate_plan(stem_fixture(), 1, 20), [])

    def test_simple_expression_does_not_require_mathml_or_variables(self):
        plan = stem_fixture()
        item = formula(plan)
        item.pop('mathml')
        item.update(expression='1 m = 1000 mm', variables=[],
                    explanation='同一长度使用不同单位表示。', conditions='采用SI长度单位及其毫米前缀。')
        self.assertEqual(validate_plan(plan), [])

    def test_formula_required_text_and_variable_units(self):
        for key in ['title', 'expression', 'explanation', 'conditions', 'variables']:
            plan = stem_fixture()
            formula(plan).pop(key)
            with self.subTest(missing=key):
                self.assertTrue(validate_plan(plan))
        for key in ['symbol', 'meaning', 'unit']:
            plan = stem_fixture()
            formula(plan)['variables'][0][key] = ' '
            with self.subTest(variable_key=key):
                self.assertTrue(validate_plan(plan))

    def test_diagram_requires_an_explanation_and_accessible_alternative(self):
        for key in ['title', 'svg', 'alt', 'caption']:
            plan = stem_fixture()
            diagram(plan).pop(key)
            with self.subTest(missing=key):
                self.assertTrue(validate_plan(plan))

    def test_malformed_math_and_fraction_arity_rejected(self):
        invalid = [
            f'<math xmlns="{MATH_NS}"><mfrac><mi>U</mi></math>',
            '<math xmlns="https://example.invalid/math"><mi>I</mi></math>',
            f'<svg xmlns="{SVG_NS}" viewBox="0 0 100 100"><text>I</text></svg>',
            f'<math xmlns="{MATH_NS}"><mfrac><mi>U</mi></mfrac></math>',
            f'<math xmlns="{MATH_NS}"><mfrac><mi>U</mi><mi>R</mi><mn>2</mn></mfrac></math>'
        ]
        for markup in invalid:
            plan = stem_fixture()
            formula(plan)['mathml'] = markup
            with self.subTest(markup=markup):
                self.assertTrue(validate_plan(plan))

    def test_math_does_not_accept_script_events_or_links(self):
        invalid = [
            f'<math xmlns="{MATH_NS}"><script>alert(1)</script></math>',
            f'<math xmlns="{MATH_NS}" onclick="alert(1)"><mi>I</mi></math>',
            f'<math xmlns="{MATH_NS}"><mi href="https://example.invalid/remote">I</mi></math>',
            f'<!DOCTYPE math [<!ENTITY label "I">]><math xmlns="{MATH_NS}"><mi>&label;</mi></math>'
        ]
        for markup in invalid:
            plan = stem_fixture()
            formula(plan)['mathml'] = markup
            with self.subTest(markup=markup):
                self.assertTrue(validate_plan(plan))

    def test_math_operators_cannot_be_hidden_in_xml_tail_text(self):
        plan = stem_fixture()
        formula(plan)['mathml'] = f'<math xmlns="{MATH_NS}"><mi>x</mi>+<mn>2</mn></math>'
        self.assertTrue(validate_plan(plan), 'The operator must be an mo token, not an XML tail.')

    def test_readable_expression_cannot_expose_raw_latex(self):
        plan = stem_fixture()
        formula(plan)['expression'] = r'\frac{U}{R}'
        self.assertTrue(validate_plan(plan), 'Fallback and accessible text must remain human-readable.')

    def test_math_accessible_label_is_allowed_only_on_the_root(self):
        plan = stem_fixture()
        formula(plan)['mathml'] = f'<math xmlns="{MATH_NS}" aria-label="x + 2"><mrow><mi>x</mi><mo>+</mo><mn>2</mn></mrow></math>'
        self.assertEqual(validate_plan(plan), [])
        formula(plan)['mathml'] = f'<math xmlns="{MATH_NS}"><mrow><mi aria-label="not x">x</mi><mo>+</mo><mn>2</mn></mrow></math>'
        self.assertTrue(validate_plan(plan), 'A child label must not replace a mathematical token meaning.')

    def test_svg_requires_namespace_and_well_formed_xml(self):
        invalid = [
            '<svg viewBox="0 0 100 100"><path d="M0 0 L1 1"/></svg>',
            '<svg xmlns="https://example.invalid/svg" viewBox="0 0 100 100"/>',
            f'<svg xmlns="{SVG_NS}" viewBox="0 0 100 100"><path></svg>'
        ]
        for markup in invalid:
            plan = stem_fixture()
            diagram(plan)['svg'] = markup
            with self.subTest(markup=markup):
                self.assertTrue(validate_plan(plan))

    def test_svg_disallows_active_content_and_external_resources(self):
        invalid = [
            f'<svg xmlns="{SVG_NS}" viewBox="0 0 100 100"><script>alert(1)</script></svg>',
            f'<svg xmlns="{SVG_NS}" viewBox="0 0 100 100" onload="alert(1)"/>',
            f'<svg xmlns="{SVG_NS}" viewBox="0 0 100 100"><foreignObject><div>HTML</div></foreignObject></svg>',
            f'<svg xmlns="{SVG_NS}" viewBox="0 0 100 100"><image href="https://example.invalid/remote.png"/></svg>',
            f'<svg xmlns="{SVG_NS}" viewBox="0 0 100 100"><path fill="url(https://example.invalid/paint)" d="M0 0 L1 1"/></svg>'
        ]
        for markup in invalid:
            plan = stem_fixture()
            diagram(plan)['svg'] = markup
            with self.subTest(markup=markup):
                self.assertTrue(validate_plan(plan))

    def test_local_svg_marker_reference_is_supported(self):
        plan = stem_fixture()
        self.assertIn('url(#current-arrow)', diagram(plan)['svg'])
        self.assertEqual(validate_plan(plan), [])

    def test_stem_sources_must_belong_to_the_lesson(self):
        for kind in [formula, diagram]:
            for source_id in ['missing-source', 'another-lesson-source']:
                plan = stem_fixture()
                plan['sources'].append({'id': 'another-lesson-source', 'title': '其他课的来源', 'locator': '本课未引用'})
                kind(plan)['source_ids'] = [source_id]
                with self.subTest(kind=kind.__name__, source_id=source_id):
                    self.assertTrue(validate_plan(plan))

    def test_optional_stem_fields_with_wrong_types_report_errors(self):
        for key, value in [('formulas', None), ('formulas', {}), ('diagrams', 'image')]:
            plan = stem_fixture()
            plan['lessons'][0]['sections'][0][key] = value
            with self.subTest(key=key, value=value):
                self.assertTrue(validate_plan(plan))


class StemOutputTests(unittest.TestCase):
    def test_generated_html_keeps_formula_and_diagram_without_external_runtime(self):
        plan = stem_fixture()
        with tempfile.TemporaryDirectory() as folder:
            output = build(plan, folder, expected_days=1, expected_daily_minutes=20)
            html = Path(output['html']).read_text(encoding='utf-8')
            embedded = json.loads(re.search(r'<script>window\.COURSE=(.*?);</script>', html, re.S).group(1))
            self.assertEqual(formula(embedded)['mathml'], formula(plan)['mathml'])
            self.assertEqual(diagram(embedded)['svg'], diagram(plan)['svg'])
            self.assertEqual(json.loads(Path(output['plan']).read_text(encoding='utf-8')), plan)
            self.assertFalse(re.search(r'<script[^>]+src=', html))
            self.assertNotIn('@import', ''.join(re.findall(r'<style\b[^>]*>(.*?)</style>', html, re.S)))
            self.assertEqual(output['offline_dependencies'], 'none')

    def test_invalid_stem_content_does_not_write_partial_output(self):
        plan = stem_fixture()
        diagram(plan)['svg'] = f'<svg xmlns="{SVG_NS}" viewBox="0 0 100 100" onload="alert(1)"/>'
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError):
                build(plan, folder)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_cli_validation_does_not_claim_teaching_facts_are_verified(self):
        validator = Path(__file__).with_name('validate_plan.py')
        run = subprocess.run([sys.executable, '-B', str(validator), str(EXAMPLE),
                              '--expected-days', '1', '--expected-daily-minutes', '20'],
                             text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads(run.stdout)
        self.assertTrue(result['valid'])
        self.assertIs(result['facts_verified'], False)


if __name__ == '__main__':
    unittest.main()
