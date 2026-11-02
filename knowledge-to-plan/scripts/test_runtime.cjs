#!/usr/bin/env node
'use strict';

// Synthetic browser-state smoke tests. No browser, packages, or network required.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assets = path.join(__dirname, '..', 'assets', 'learning-site');
const script = fs.readFileSync(path.join(assets, 'app.js'), 'utf8');
const html = fs.readFileSync(path.join(assets, 'index.html'), 'utf8');
const clone = value => JSON.parse(JSON.stringify(value));
const fixture = {
  schema_version: 1,
  course: { id: 'synthetic-runtime-test', title: '合成测试课程', goal: '测试学习状态', background: '初学者', days: 4, daily_minutes: 17, timezone: 'Asia/Hong_Kong' },
  sources: [],
  lessons: [1, 2, 3, 4].map(day => ({
    id: 'lesson-' + day, day, title: '合成课程 ' + day, objectives: ['理解测试要点'],
    activities: [{ kind: 'reading', minutes: 17 }], sections: [{ title: '合成内容', body: '这是一段完全虚构的教学内容。' }],
    takeaways: ['记录进步'], source_ids: [],
    questions: Array.from({ length: day === 1 ? 2 : 1 }, (_, index) => ({
      id: 'question-' + index, prompt: `合成问题 ${day}-${index}`, options: ['错误选项甲', '正确选项', '错误选项乙'],
      correct_index: 1, explanations: ['甲错误的具体原因', '正确选项的具体原因', '乙错误的具体原因']
    }))
  }))
};

function launch(data, storage = new Map(), hash = '', unavailable = false, now = Date.now(), reducedMotion = true) {
  const walk = element => element.children.flatMap(child => [child, ...walk(child)]);
  class Element {
    constructor(tagName) {
      this.tagName = tagName; this.children = []; this.events = {}; this.attributes = {}; this.className = ''; this._text = '';
      this.style = { setProperty(name, value) { this[name] = String(value); } };
      this.classList = {
        toggle: name => { const present = this.className.split(' ').includes(name); present ? this.classList.remove(name) : this.classList.add(name); return !present; },
        add: name => { this.className = [...new Set([...this.className.split(' ').filter(Boolean), name])].join(' '); },
        remove: name => { this.className = this.className.split(' ').filter(value => value !== name).join(' '); }
      };
    }
    get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
    set textContent(value) { this._text = String(value); this.replaceChildren(); }
    append(...elements) { for (const element of elements) { element.remove(); element.parent = this; this.children.push(element); } }
    replaceChildren(...elements) { for (const child of this.children) child.parent = null; this.children = []; this.append(...elements); }
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); this.parent = null; }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) { return this.attributes[name]; }
    removeAttribute(name) { delete this.attributes[name]; }
    addEventListener(name, handler) { this.events[name] = handler; }
    focus() { this.focused = true; }
    querySelector(selector) { return walk(this).find(element => selector.startsWith('.') ? element.className.split(' ').includes(selector.slice(1)) : element.tagName === selector); }
    click() { if (!this.disabled) return this.events.click?.({ target: this }); }
  }
  const body = new Element('body');
  for (const match of html.matchAll(/id="([^"]+)"/g)) { const element = new Element('div'); element.id = match[1]; body.append(element); }
  const document = { body, createElement: tag => new Element(tag), getElementById: id => walk(body).find(element => element.id === id), addEventListener: (name, handler) => { handlers['document:' + name] = handler; } };
  const handlers = {}, location = { hash }, downloads = [];
  let tick = now;
  class TestDate extends Date {
    constructor(...args) { super(...(args.length ? args : [tick])); }
    static now() { return ++tick; }
  }
  class TestURL extends URL { static createObjectURL(blob) { downloads.push(blob); return 'blob:synthetic-export'; } static revokeObjectURL() {} }
  const context = {
    document, window: { COURSE: clone(data), addEventListener: (name, handler) => { handlers[name] = handler; }, setInterval: handler => { handlers.interval = handler; return 1; }, matchMedia: () => ({ matches: reducedMotion }) }, location,
    history: { replaceState: (_state, _title, nextHash) => { location.hash = nextHash; } },
    localStorage: {
      getItem: key => { if (unavailable) throw new Error('Synthetic storage failure'); return storage.get(key) ?? null; },
      setItem: (key, value) => { if (unavailable) throw new Error('Synthetic storage failure'); storage.set(key, value); },
      removeItem: key => storage.delete(key)
    },
    URL: TestURL, Blob, Date: TestDate, Intl, setTimeout: handler => { handler(); }
  };
  vm.runInNewContext(script, context, { filename: 'learning-site/app.js' });
  const get = id => { const element = document.getElementById(id); assert.ok(element, 'Missing element: ' + id); return element; };
  const click = (label, root = 'content') => {
    const element = walk(get(root)).find(item => item.tagName === 'button' && item.textContent === label);
    assert.ok(element, 'Missing button: ' + label); assert.ok(!element.disabled, 'Disabled button: ' + label); return element.click();
  };
  const snapshot = () => {
    for (const value of storage.values()) { const candidate = JSON.parse(value); if (candidate.course_id === data.course.id) return candidate; }
    assert.fail('No course-namespaced state was saved');
  };
  return {
    get, click, snapshot, storage, location, handlers, downloads,
    all(root = 'content') { return walk(get(root)); },
    advanceTo(timestamp) { tick = timestamp; },
    choose(index) { const radio = get('answer-option-' + index); assert.ok(!radio.disabled); radio.checked = true; radio.events.change({ target: radio }); },
    async import(payload) { const input = get('import-file'); input.files = [{ size: 1, text: async () => JSON.stringify(payload) }]; await input.events.change({ target: input }); },
    note(text) { const input = get('lesson-notes'); input.value = text; input.events.input({ target: input }); }
  };
}

async function main() {
  for (const token of ['STYLE', 'COURSE_JSON', 'SCRIPT']) assert.equal(html.split('{{' + token + '}}').length - 1, 1, 'Each replacement token occurs once');
  const store = new Map(); let ui = launch(fixture, store, '#day-1');
  assert.match(ui.get('course-meta').textContent, /4 天.*17 分钟/);
  ui.click('03 当日测验', 'study-tabs'); ui.choose(0); ui.click('提交答案');
  assert.equal(ui.get('progress-percent').textContent, '0%', 'Wrong answers cannot pass a lesson');
  for (const explanation of fixture.lessons[0].questions[0].explanations) assert.ok(ui.get('content').textContent.includes(explanation), 'Each option has an explanation');
  ui.click('再试一次'); ui.choose(1); ui.click('提交答案');
  assert.equal(ui.get('progress-percent').textContent, '0%', 'One correct answer cannot pass a two-question lesson');
  ui.click('下一题 →'); ui.choose(1); ui.click('提交答案');
  assert.equal(ui.get('progress-percent').textContent, '25%', 'All correct answers pass exactly one of four lessons');
  const records = ui.snapshot().answers, ids = Object.keys(records);
  assert.equal(records[ids[0]].attempts.length, 2, 'Retry retains wrong and correct attempts');
  ui.click('02 练习与笔记', 'study-tabs'); ui.note('合成的本地学习笔记'); ui.click('03 当日测验', 'study-tabs');

  ui = launch(fixture, store, '#day-1');
  assert.ok(ui.get('content').textContent.includes('第 2 / 2 题'), 'Reload restores the question cursor and quiz view');
  assert.equal(ui.get('answer-option-1').checked, true, 'Reload restores the selected answer');
  assert.equal(ui.get('answer-option-1').disabled, true, 'Passed questions retain their submitted state');
  ui.get('wrong-book').click();
  assert.match(ui.get('content').textContent, /已(?:订正|掌握) · 历史保留/, 'Resolved wrong answers remain in history');
  ui.location.hash = '#day-3'; ui.handlers.hashchange(); assert.equal(ui.snapshot().lastDay, 3, 'Hash changes select the matching day');

  const changed = clone(fixture); changed.lessons[0].questions[0].prompt += '（修订）';
  const revised = launch(changed, new Map(store), '#day-1'), revisedRecords = revised.snapshot().answers;
  assert.equal(revised.get('progress-percent').textContent, '0%', 'Changed questions invalidate completion');
  assert.equal(Object.keys(revisedRecords).length, 1, 'Only changed question records are discarded');
  assert.ok(revisedRecords[ids[1]], 'Unchanged question records survive');

  ui = launch(fixture, store, '#day-1');
  const before = ui.snapshot(), incoming = clone(before), now = Date.now() + 1000;
  incoming.answers = {
    [ids[0]]: { ...before.answers[ids[0]], updated_at: now, attempts: [{ selected: 2, at: now - 1 }, { selected: 1, at: now }] },
    [ids[1]]: { ...before.answers[ids[1]], updated_at: now + 2, attempts: [{ selected: 0, at: now + 1 }, { selected: 1, at: now + 2 }] },
    'q:["unknown-lesson","unknown-question"]': clone(before.answers[ids[0]]),
    'q:["lesson-2","question-0"]': { ...before.answers[ids[0]], fingerprint: 'outdated-content' }
  };
  incoming.notes['l:lesson-1'] = { text: '合成的较新导入笔记', updated_at: now + 3 };
  await ui.import(incoming);
  assert.match(ui.get('notice').textContent, /合并了 2 道题.*2 条记录/, 'Import reports two accepted and two rejected records');
  const merged = ui.snapshot();
  assert.equal(Object.keys(merged.answers).length, 2, 'Import excludes unknown and mismatched fingerprints');
  assert.equal(merged.answers[ids[0]].attempts.length, 4, 'Import unions old and new attempt histories');
  assert.equal(merged.notes['l:lesson-1'].text, '合成的较新导入笔记', 'Newer imported notes win');
  assert.equal(ui.get('progress-percent').textContent, '25%', 'Merged valid completion remains complete');
  await ui.import(incoming); assert.equal(ui.snapshot().answers[ids[0]].attempts.length, 4, 'Repeated imports do not duplicate attempts');
  const olderNotes = clone(incoming); olderNotes.notes['l:lesson-1'] = { text: '合成的过期笔记', updated_at: 1 };
  await ui.import(olderNotes); assert.equal(ui.snapshot().notes['l:lesson-1'].text, '合成的较新导入笔记', 'Older imported notes cannot replace newer notes');
  const foreign = clone(incoming); foreign.course_id = 'different-synthetic-course';
  await ui.import(foreign); assert.match(ui.get('notice').textContent, /无法导入/, 'Other courses cannot overwrite state');
  ui.get('export-progress').click();
  const exported = JSON.parse(await ui.downloads[0].text()); assert.equal(exported.course_id, fixture.course.id); assert.equal(Object.keys(exported.answers).length, 2);

  const noQuiz = clone(fixture); noQuiz.course.id += '-no-quiz'; noQuiz.lessons[3].questions = [];
  const empty = launch(noQuiz, new Map(), '#day-4');
  assert.equal(empty.get('progress-percent').textContent, '0%', 'An empty question list cannot pass a lesson');
  const disabled = launch(fixture, new Map(), '#day-1', true);
  assert.equal(disabled.get('storage-warning').hidden, false, 'Unavailable local storage produces a visible warning');
  disabled.click('03 当日测验', 'study-tabs'); disabled.choose(1); disabled.click('提交答案');
  assert.ok(disabled.get('content').textContent.includes('答对了'), 'Learning continues without local storage');
  await testDashboard();
  await testDailyVolume();
  console.log('PASS: quiz gating/retry/completion, resume, fingerprints, deep links, history, import/export, notes, storage fallback; dashboard metrics, lesson navigation, calendar map, check-in idempotency, timezone boundaries, real-activity migration, backup validation, and uncapped daily learning volume.');
}
async function testDashboard() {
  const morning = Date.parse('2026-11-02T02:00:00Z');
  const freshStore = new Map();
  let ui = launch(fixture, freshStore, '', false, morning);
  assert.equal(ui.location.hash, '#dashboard', 'A fresh course opens at its dashboard');
  assert.equal(ui.get('stat-completed').textContent, '0 / 4');
  assert.equal(ui.get('stat-questions').textContent, '0 / 5');
  assert.equal(ui.get('stat-review').textContent, '0');
  assert.equal(ui.get('stat-minutes').textContent, '0');
  assert.equal(ui.get('checkin-total').textContent, '0', 'Viewing the dashboard does not fabricate activity');
  assert.equal(Object.keys(ui.snapshot().checkins).length, 0);
  const lessonLinks = ui.all('lesson-list').filter(el => el.className.split(' ').includes('lesson-link'));
  assert.equal(lessonLinks.length, fixture.lessons.length, 'The lesson directory contains every lesson');
  assert.ok(lessonLinks.every((el, i) => el.getAttribute('aria-label').includes(String(i + 1))));
  lessonLinks[0].click();
  assert.equal(ui.location.hash, '#day-1', 'The lesson directory opens its selected lesson');
  ui.get('dashboard-link').click();
  const map = ui.get('checkin-map');
  const dates = ui.all('checkin-map').filter(el => el.tagName === 'button');
  assert.equal(map.children.length, 13, 'The map contains thirteen calendar weeks');
  assert.equal(dates.length, 91, 'The map includes all seven dates per week');
  assert.ok(dates.some(el => el.disabled), 'Future dates cannot be checked in');
  const todayCell = dates.find(el => el.className.split(' ').includes('is-today'));
  assert.ok(todayCell, 'The real current date is marked');
  const oldDate = dates.find(el => !el.disabled && el !== todayCell);
  oldDate.click();
  assert.equal(Object.keys(ui.snapshot().checkins).length, 0, 'Inspecting a past date cannot backfill activity');
  assert.ok(ui.get('checkin-detail').textContent, 'Map selection exposes readable date details');

  ui.get('today-checkin').click();
  assert.deepEqual(Object.keys(ui.snapshot().checkins), ['2026-11-02']);
  assert.equal(ui.snapshot().checkins['2026-11-02'].kind, 'manual');
  assert.equal(ui.get('checkin-total').textContent, '1');
  assert.equal(ui.get('checkin-streak').textContent, '1');
  assert.equal(ui.get('checkin-longest').textContent, '1');
  assert.equal(ui.get('stat-completed').textContent, '0 / 4', 'Check-in does not pass any quiz');
  const checked = clone(ui.snapshot().checkins);
  ui.get('today-checkin').click();
  assert.deepEqual(ui.snapshot().checkins, checked, 'Repeating same-day check-in does not change activity');
  ui = launch(fixture, freshStore, '', false, morning + 1000);
  assert.equal(ui.get('checkin-total').textContent, '1', 'Refresh keeps the check-in');

  ui.get('continue-learning').click();
  assert.equal(ui.location.hash, '#day-1', 'Continue opens the first incomplete lesson');
  ui.click('03 当日测验', 'study-tabs');
  const submit = ui.all().find(el => el.tagName === 'button' && el.textContent === '提交答案');
  assert.ok(submit.disabled, 'An unselected answer cannot be submitted');
  ui.choose(0);
  ui.click('提交答案');
  assert.equal(ui.snapshot().checkins['2026-11-02'].kind, 'study', 'A real submission upgrades manual activity');
  ui.get('dashboard-link').click();
  assert.equal(ui.location.hash, '#dashboard');
  assert.equal(ui.get('stat-review').textContent, '1', 'Wrong submissions count once as pending questions');
  assert.equal(ui.get('stat-completed').textContent, '0 / 4', 'Wrong answers remain incomplete');
  assert.equal(ui.get('checkin-total').textContent, '1', 'Many actions on one day count as one check-in');

  // Notes only create activity when the user records non-whitespace content.
  const noteStore = new Map();
  const notes = launch(fixture, noteStore, '#day-1', false, morning);
  notes.click('02 练习与笔记', 'study-tabs'); notes.note('   ');
  assert.equal(Object.keys(notes.snapshot().checkins).length, 0, 'Whitespace is not study activity');
  notes.note('已写出练习步骤');
  assert.equal(notes.snapshot().checkins['2026-11-02'].kind, 'study');
  notes.get('dashboard-link').click();
  assert.equal(notes.get('stat-completed').textContent, '0 / 4', 'Notes do not bypass the quiz');

  // Midnight follows the course timezone, regardless of the execution host timezone.
  const boundaryStore = new Map();
  let boundary = launch(fixture, boundaryStore, '', false, Date.parse('2026-11-02T15:59:00Z'));
  boundary.get('today-checkin').click();
  boundary = launch(fixture, boundaryStore, '', false, Date.parse('2026-11-02T16:01:00Z'));
  boundary.get('today-checkin').click();
  assert.deepEqual(Object.keys(boundary.snapshot().checkins).sort(), ['2026-11-02', '2026-11-03']);
  assert.equal(boundary.get('checkin-streak').textContent, '2', 'Consecutive course-local dates form a streak');
  // Keep the same live page open over midnight: timers and restored visibility update it.
  for (const trigger of ['interval', 'focus', 'document:visibilitychange']) {
    const live = launch(fixture, new Map(), '#dashboard', false, Date.parse('2026-11-02T15:59:00Z'));
    live.get('today-checkin').click();
    assert.ok(live.get('today-checkin').disabled, 'The old date is already checked in');
    live.advanceTo(Date.parse('2026-11-02T16:01:00Z'));
    assert.equal(typeof live.handlers[trigger], 'function', trigger + ' is registered');
    live.handlers[trigger]();
    assert.equal(live.get('today-checkin').disabled, false, trigger + ' enables the new day without reloading');
    assert.equal(live.get('checkin-total').textContent, '1', 'Calendar rollover does not create study activity');
    const current = live.all('checkin-map').filter(el => el.className.split(' ').includes('is-today'));
    assert.equal(current.length, 1);
    assert.ok(current[0].getAttribute('aria-label').startsWith('2026-11-03'), 'The map highlights the new course-local date');
    live.get('today-checkin').click();
    assert.deepEqual(Object.keys(live.snapshot().checkins).sort(), ['2026-11-02', '2026-11-03']);
    assert.equal(live.get('checkin-streak').textContent, '2', 'The next deliberate check-in records the new date');
  }
  const pacific = clone(fixture); pacific.course.timezone = 'Pacific/Honolulu';
  const otherZone = launch(pacific, new Map(), '', false, Date.parse('2026-11-02T02:00:00Z'));
  otherZone.get('today-checkin').click();
  assert.deepEqual(Object.keys(otherZone.snapshot().checkins), ['2026-11-01'], 'A different course timezone changes the date bucket');

  // Old schema-version-1 backups have no checkins: migrate only persisted evidence.
  const legacy = clone(notes.snapshot()); delete legacy.checkins;
  legacy.notes['l:lesson-1'] = { text: '旧记录中的真实笔记', updated_at: Date.parse('2026-10-30T02:00:00Z') };
  const l = fixture.lessons[1], q = l.questions[0], at = Date.parse('2026-10-31T03:00:00Z');
  legacy.answers = { ['q:' + JSON.stringify([l.id, q.id])]: {
    fingerprint: JSON.stringify([q.prompt, q.options, q.correct_index, q.explanations]),
    selected: q.correct_index, submitted: true, updated_at: at, attempts: [{ selected: q.correct_index, at }]
  } };
  const migrated = launch(fixture, new Map([['knowledge-to-plan:v1:' + fixture.course.id, JSON.stringify(legacy)]]), '#dashboard', false, morning);
  assert.deepEqual(Object.keys(migrated.snapshot().checkins).sort(), ['2026-10-30', '2026-10-31'], 'Legacy check-ins come from valid answers and nonempty notes');
  assert.equal(migrated.get('stat-completed').textContent, '1 / 4');
  assert.equal(migrated.get('stat-questions').textContent, '1 / 5');
  assert.equal(migrated.get('stat-minutes').textContent, '17', 'Minutes sum passed lessons’ planned activities');
  assert.equal(migrated.get('checkin-streak').textContent, '0', 'A broken streak does not continue through missing days');
  assert.equal(migrated.get('checkin-longest').textContent, '2');

  const backup = { schema_version: 1, course_id: fixture.course.id, answers: {}, notes: {}, checkins: {
    '2026-11-01': { at: Date.parse('2026-11-01T02:00:00Z'), kind: 'manual' },
    '2026-11-03': { at: Date.parse('2026-11-03T02:00:00Z'), kind: 'manual' },
    '2026-10-29': { at: Date.parse('2026-10-28T02:00:00Z'), kind: 'study' },
    '2026-02-30': { at: Date.parse('2026-03-02T02:00:00Z'), kind: 'manual' }
  } };
  await migrated.import(backup);
  assert.ok(migrated.snapshot().checkins['2026-11-01'], 'A valid historical check-in merges');
  assert.equal(migrated.snapshot().checkins['2026-11-03'], undefined, 'A future check-in is rejected');
  assert.equal(migrated.snapshot().checkins['2026-10-29'], undefined, 'A date that disagrees with its timestamp is rejected');
  assert.equal(migrated.snapshot().checkins['2026-02-30'], undefined, 'Impossible calendar dates are rejected');
  assert.equal(migrated.get('checkin-streak').textContent, '3', 'Before today’s activity, a streak ending yesterday remains current');
  await migrated.import(backup);
  assert.equal(Object.keys(migrated.snapshot().checkins).length, 3, 'Repeated backup imports do not duplicate days');
  migrated.get('export-progress').click();
  const exported = JSON.parse(await migrated.downloads[0].text());
  assert.equal(Object.keys(exported.checkins).length, 3, 'Exports include the actual activity map');
  migrated.location.hash = '#day-4'; migrated.handlers.hashchange();
  assert.equal(migrated.snapshot().lastDay, 4);
  migrated.location.hash = '#dashboard'; migrated.handlers.hashchange();
  assert.equal(migrated.get('stat-completed').textContent, '1 / 4', 'Dashboard links work through the hash router');
}

async function testDailyVolume() {
  const now = Date.parse('2026-11-02T12:00:00Z'), today = '2026-11-02';
  const ui = launch(fixture, new Map(), '#dashboard', false, now);
  const payload = () => ({ schema_version: 1, course_id: fixture.course.id, answers: {}, notes: {}, checkins: {} });
  const put = (target, lessonIndex, questionIndex, attempts) => {
    const l = fixture.lessons[lessonIndex], q = l.questions[questionIndex], latest = attempts[attempts.length - 1];
    target.answers['q:' + JSON.stringify([l.id, q.id])] = {
      fingerprint: JSON.stringify([q.prompt, q.options, q.correct_index, q.explanations]),
      selected: latest.selected, submitted: true, updated_at: latest.at, attempts
    };
  };
  const attempt = (time, selected = 1) => ({ selected, at: Date.parse(time) });
  const cell = day => ui.all('checkin-map').find(el => el.tagName === 'button' && el.getAttribute('aria-label')?.startsWith(day));
  const metric = id => Number(ui.get(id).textContent);
  const assertDay = (lessons, questions, minutes, message) => {
    assert.equal(metric('day-completed-count'), lessons, message + ': lessons');
    assert.equal(metric('day-question-count'), questions, message + ': unique questions');
    assert.equal(metric('day-planned-minutes'), minutes, message + ': planned minutes');
  };
  assertDay(0, 0, 0, 'Empty dashboard selects the real current date');
  const imported = payload();
  // Day 1 was first passed yesterday; a repeated correct submission today is activity only.
  put(imported, 0, 0, [attempt('2026-10-31T02:00:00Z'), attempt('2026-11-02T01:00:00Z')]);
  put(imported, 0, 1, [attempt('2026-11-01T02:00:00Z')]);
  put(imported, 1, 0, [attempt('2026-11-02T02:00:00Z', 0), attempt('2026-11-02T02:01:00Z', 0)]);
  await ui.import(imported);
  assertDay(0, 2, 0, 'Repeated wrong answers count activity without passing a lesson');
  assert.ok(cell(today).className.split(' ').includes('level-2'), 'Answering without a pass creates the activity shade');
  const beforeInspection = clone(ui.snapshot().checkins);
  cell('2026-11-01').click();
  assertDay(1, 1, 17, 'A lesson completes when all questions have first been answered correctly');
  assert.ok(ui.get('day-detail').textContent.includes(fixture.lessons[0].title), 'Daily details name the passed lesson');
  assert.deepEqual(ui.snapshot().checkins, beforeInspection, 'Inspecting a day does not create activity');
  cell(today).click();
  assertDay(0, 2, 0, 'Returning to today restores today’s totals');

  const corrected = payload();
  put(corrected, 1, 0, [attempt('2026-11-02T02:00:00Z', 0), attempt('2026-11-02T02:01:00Z', 0), attempt('2026-11-02T02:02:00Z')]);
  await ui.import(corrected);
  assertDay(1, 2, 17, 'Correcting one question passes its lesson once');
  const second = payload(); put(second, 2, 0, [attempt('2026-11-02T03:00:00Z')]);
  await ui.import(second);
  assertDay(2, 3, 34, 'Two lessons in one day exceed the daily plan without being capped');
  assert.ok(cell(today).className.split(' ').includes('level-3'), 'Two completed lessons deepen the heatmap');
  const third = payload(); put(third, 3, 0, [attempt('2026-11-02T04:00:00Z')]);
  await ui.import(third);
  assertDay(3, 4, 51, 'Three lessons accumulate all their planned minutes');
  assert.ok(cell(today).className.split(' ').includes('level-4'), 'Three completed lessons use the strongest shade');
  for (const l of fixture.lessons.slice(1)) assert.ok(ui.get('day-detail').textContent.includes(l.title), 'Daily details include every passed lesson');
  assert.match(cell(today).getAttribute('aria-label'), /完成\s*3\s*课.*答题\s*4\s*道.*计划\s*51\s*分钟/, 'The heatmap exposes daily quantity to keyboard and screen-reader users');
  await ui.import(third); await ui.import(second); await ui.import(corrected);
  assertDay(3, 4, 51, 'Importing the same records repeatedly cannot inflate daily totals');
  ui.get('export-progress').click();
  const exported = JSON.parse(await ui.downloads[0].text());
  const restored = launch(fixture, new Map([['knowledge-to-plan:v1:' + fixture.course.id, JSON.stringify(exported)]]), '#dashboard', false, now + 1000);
  assert.equal(Number(restored.get('day-completed-count').textContent), 3, 'Backup restoration rebuilds the completed lesson count');
  assert.equal(Number(restored.get('day-question-count').textContent), 4, 'Backup restoration rebuilds the unique question count');
  assert.equal(Number(restored.get('day-planned-minutes').textContent), 51, 'Backup restoration rebuilds uncapped planned minutes');

  const future = payload(); put(future, 1, 0, [attempt('2026-11-02T14:00:00Z')]);
  const futureUI = launch(fixture, new Map(), '#dashboard', false, now);
  await futureUI.import(future);
  assert.equal(Number(futureUI.get('day-completed-count').textContent), 0, 'Future answer times cannot create a daily completion');
  assert.equal(Number(futureUI.get('day-question-count').textContent), 0, 'Future answer times cannot create daily answered volume');
  assert.equal(Number(futureUI.get('day-planned-minutes').textContent), 0, 'Future answer times cannot create daily planned minutes');

  // Motion preferences affect presentation, while check-in and learning amounts stay the same.
  const animated = launch(fixture, new Map(), '#dashboard', false, now, false);
  assert.ok(animated.get('content').className.split(' ').includes('motion-enter'), 'A new view can animate when motion is allowed');
  animated.get('today-checkin').click();
  assert.equal(animated.all().filter(el => el.className === 'checkin-spark').length, 8, 'A deliberate check-in can celebrate once');
  assert.equal(Object.keys(animated.snapshot().checkins).length, 1, 'Celebration does not generate extra check-ins');
  assert.equal(Number(animated.get('day-completed-count').textContent), 0, 'Celebration cannot pass courses');
  assert.ok(!animated.get('content').className.split(' ').includes('motion-enter'), 'Same-view data updates do not replay the whole entrance');
  const reduced = launch(fixture, new Map(), '#dashboard', false, now, true);
  reduced.get('today-checkin').click();
  assert.equal(reduced.all().filter(el => el.className === 'checkin-spark').length, 0, 'Reduced-motion preference skips celebratory particles');
  assert.equal(Object.keys(reduced.snapshot().checkins).length, 1, 'Reduced-motion mode preserves the exact same check-in behavior');
}

main().catch(error => { console.error(error); process.exitCode = 1; });
