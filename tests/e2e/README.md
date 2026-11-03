# Browser regression checks

These tests run in Linux CI using the Chromium downloaded by Playwright. They do
not control or launch the user's installed Chrome profile. On the configured Mac,
use the supported browser tools for manual checks; do not run a shell browser
launch as a workaround for local browser access restrictions.

Development-only dependencies are pinned in `package-lock.json`. A permitted
Linux environment can run:

```sh
python3 -m pip install -r requirements.txt
npm ci
npx playwright install --with-deps chromium
npm run test:e2e
```

The four project names distinguish desktop (1440 px) and narrow mobile viewport
(390 px), each under HTTP and `file://`. A narrow viewport is not a real-phone
certification. `file://` tests explicitly verify localStorage restoration in the
CI browser; behavior in Safari, Firefox or another machine remains unverified.

Checks cover the answer gate, wrong answer and retry, keyboard focus after
rerendering, all-correct lesson completion, reload, same-day multiple lessons,
unique question totals, real JSON download/import, notes, embedded MathML/SVG,
page overflow and a print-media smoke check. These are interaction tests, not a
test of subject-matter correctness or a complete accessibility audit.

Failures retain screenshots, browser traces and videos in `test-results/`; the
HTML report is in `playwright-report/`. CI uploads both directories even when a
browser test fails. The fixture server binds only to `127.0.0.1:4173` and creates
`.e2e/site/`; it never rewrites checked-in examples.
