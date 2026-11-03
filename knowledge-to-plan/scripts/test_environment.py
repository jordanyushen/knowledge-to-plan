"""Timezone failures are environmental or input errors, never silent fallback."""
import datetime as dt
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_workflow import fixture
from timezone_support import InvalidTimezoneError, resolve_timezone
from validate_plan import validate_plan


SCRIPTS = Path(__file__).resolve().parent


class TimezoneEnvironmentTests(unittest.TestCase):
    def child(self, code, no_site=False):
        # Disable system TZ data and, when requested, installed site packages.
        # Fresh processes avoid ZoneInfo caches and do not mutate the test host.
        env = dict(os.environ, PYTHONTZPATH='', PYTHONDONTWRITEBYTECODE='1')
        args = [sys.executable, '-B'] + (['-S'] if no_site else [])
        source = 'import sys\nsys.path.insert(0, ' + repr(str(SCRIPTS)) + ')\n' + code
        return subprocess.run(args + ['-c', source], env=env, text=True, capture_output=True)

    def test_valid_zone_preserves_requested_key_and_offset(self):
        zone = resolve_timezone('Asia/Hong_Kong')
        self.assertEqual(zone.key, 'Asia/Hong_Kong')
        self.assertEqual(dt.datetime(2026, 11, 4, tzinfo=zone).utcoffset(), dt.timedelta(hours=8))

    def test_unknown_zone_is_distinct_from_missing_database(self):
        with self.assertRaises(InvalidTimezoneError) as issue:
            resolve_timezone('Mars/Olympus_Mons')
        self.assertIn('不在当前可用', str(issue.exception))
        self.assertIn('核对名称', str(issue.exception))

    def test_malformed_names_rejected_even_without_data(self):
        run = self.child("""
from timezone_support import InvalidTimezoneError, resolve_timezone
for key in ['/Asia/Hong_Kong', 'Asia/../Hong_Kong', 'Asia//Hong_Kong']:
    try:
        resolve_timezone(key)
    except InvalidTimezoneError:
        continue
    raise AssertionError('malformed key accepted: ' + key)
""", no_site=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_missing_system_and_package_gives_actionable_environment_error(self):
        run = self.child("""
from timezone_support import TimezoneDataError, resolve_timezone
try:
    resolve_timezone('Asia/Hong_Kong')
except TimezoneDataError as error:
    assert '缺少可用的 IANA 时区数据库' in str(error)
    assert 'python -m pip install tzdata' in str(error)
    print(str(error))
else:
    raise AssertionError('unexpected timezone fallback')
""", no_site=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('不会自动替换课程时区', run.stdout)

    @unittest.skipUnless(importlib.util.find_spec('tzdata'), 'install declared tzdata dependency to test package fallback')
    def test_package_timezone_data_works_without_system_database(self):
        run = self.child("""
import datetime as dt
from timezone_support import resolve_timezone
zone = resolve_timezone('Asia/Hong_Kong')
assert zone.key == 'Asia/Hong_Kong'
assert dt.datetime(2026, 11, 4, tzinfo=zone).utcoffset() == dt.timedelta(hours=8)
from test_workflow import fixture
from build_learning_site import make_ics
from validate_plan import validate_plan
assert validate_plan(fixture()) == []
assert 'DTSTART:20261102T063000Z' in make_ics(fixture())
""")
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_validation_reports_environment_failure_without_blame_on_plan(self):
        run = self.child("""
from test_workflow import fixture
from validate_plan import validate_plan
issues = validate_plan(fixture())
assert len(issues) == 1, issues
assert '缺少可用的 IANA 时区数据库' in issues[0], issues
assert '不是本环境可用的IANA时区' not in issues[0], issues
""", no_site=True)
        self.assertEqual(run.returncode, 0, run.stderr)

    def test_missing_database_cli_does_not_write_partial_output(self):
        with tempfile.TemporaryDirectory() as folder:
            plan = Path(folder) / 'plan.json'
            plan.write_text(json.dumps(fixture()), encoding='utf-8')
            output = Path(folder) / 'output'
            env = dict(os.environ, PYTHONTZPATH='', PYTHONDONTWRITEBYTECODE='1')
            run = subprocess.run([
                sys.executable, '-B', '-S', str(SCRIPTS / 'build_learning_site.py'),
                '--plan', str(plan), '--output', str(output), '--calendar',
            ], env=env, text=True, capture_output=True)
            self.assertEqual(run.returncode, 2, run.stderr)
            error = json.loads(run.stderr)
            self.assertFalse(error['built'])
            self.assertIn('pip install tzdata', error['error'])
            self.assertFalse(output.exists())

    def test_validator_rejects_unknown_timezone_with_database_available(self):
        plan = fixture()
        plan['course']['timezone'] = 'Mars/Olympus_Mons'
        issues = validate_plan(plan)
        self.assertEqual(len(issues), 1)
        self.assertIn('course.timezone', issues[0])
        self.assertIn('核对名称', issues[0])


if __name__ == '__main__':
    unittest.main()
