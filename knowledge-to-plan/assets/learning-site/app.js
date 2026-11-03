(() => {
  'use strict';
  const data = window.COURSE, course = data.course, lessons = data.lessons;
  const $ = id => document.getElementById(id);
  const make = (tag, cls, text) => { const el = document.createElement(tag); if (cls) el.className = cls; if (text !== undefined) el.textContent = text; return el; };
  const button = (text, cls, action) => { const el = make('button', cls, text); el.type = 'button'; el.addEventListener('click', action); return el; };
  const key = 'knowledge-to-plan:v1:' + course.id;
  const qkey = (l, q) => 'q:' + JSON.stringify([l.id, q.id]);
  const nkey = l => 'l:' + l.id;
  // A canonical content fingerprint changes whenever any part of a question changes.
  const fingerprint = q => JSON.stringify([q.prompt, q.options, q.correct_index, q.explanations]);
  const questionMap = new Map(lessons.flatMap(l => l.questions.map(q => [qkey(l, q), { l, q }])));
  let state = { schema_version: 1, course_id: course.id, answers: {}, notes: {}, checkins: {}, quarantined: [], lastDay: lessons[0]?.day, view: 'dashboard', cursors: {} };
  let lesson, view = 'dashboard', storageAvailable = true, dashboardDate;
  let lastRenderedView, enteringView = false, lastProgress, selectedDate, pendingCelebration = false;
  const motionAllowed = () => !window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
  const dateFormat = new Intl.DateTimeFormat('en-US', { timeZone: course.timezone, year: 'numeric', month: '2-digit', day: '2-digit' });
  function dateKey(at = Date.now()) {
    const parts = dateFormat.formatToParts(new Date(at));
    const part = name => parts.find(p => p.type === name).value;
    return `${part('year')}-${part('month')}-${part('day')}`;
  }
  const shiftDate = (day, offset) => new Date(Date.parse(day + 'T12:00:00Z') + offset * 86400000).toISOString().slice(0, 10);
  function markActivity(at, kind = 'study') {
    if (!Number.isFinite(at) || at <= 0 || at > Date.now()) return;
    const day = dateKey(at), previous = state.checkins[day];
    state.checkins[day] = { at: Math.max(previous?.at || 0, at), kind: previous?.kind === 'study' || kind === 'study' ? 'study' : 'manual' };
  }
  const announce = message => { $('notice').textContent = message; $('notice').hidden = false; };
  function storageWarning() { storageAvailable = false; $('storage-warning').textContent = '当前浏览器无法持久保存学习记录。本次学习仍可继续，请在离开前导出记录；重新打开后可导入恢复。'; $('storage-warning').hidden = false; }
  function save() { if (storageAvailable) { try { localStorage.setItem(key, JSON.stringify(state)); } catch (_) { storageWarning(); } } }
  // Zero/missing timestamps are legacy dates, never an invented activity day.
  const validTime = x => Number.isFinite(x) && x > 0 && x <= Date.now();
  const unknownTime = x => x === undefined || x === null || x === 0;
  function archiveRecord(kind, id, record, reason) {
    const entry = { kind, id, reason, record }, signature = JSON.stringify(entry);
    if (state.quarantined.some(saved => JSON.stringify(saved) === signature)) return 0;
    state.quarantined.push(entry); return 1;
  }
  function sanitizeAnswer(raw, q) {
    if (!raw || raw.fingerprint !== fingerprint(q)) return null;
    const validSelection = n => Number.isInteger(n) && n >= 0 && n < q.options.length;
    let invalidTime = false;
    const attempts = [];
    for (const attempt of Array.isArray(raw.attempts) ? raw.attempts : []) {
      if (!attempt || !validSelection(attempt.selected)) continue;
      if (validTime(attempt.at) || unknownTime(attempt.at)) attempts.push({ selected: attempt.selected, at: attempt.at || 0 });
      else invalidTime = true;
    }
    let selected = validSelection(raw.selected) ? raw.selected : null;
    let submitted = raw.submitted === true && selected !== null;
    let updated_at = validTime(raw.updated_at) ? raw.updated_at : 0;
    if (!validTime(raw.updated_at) && (!unknownTime(raw.updated_at) || invalidTime)) {
      // Preserve older, dated evidence without accepting a future latest answer.
      invalidTime = true;
      const latest = attempts.filter(a => validTime(a.at)).sort((a, b) => b.at - a.at)[0];
      if (!latest) return { answer: null, invalidTime };
      selected = latest.selected; submitted = true; updated_at = latest.at;
    }
    if (submitted && !attempts.some(a => a.at === updated_at && a.selected === selected)) attempts.push({ selected, at: updated_at });
    return { answer: { fingerprint: fingerprint(q), selected, submitted, updated_at, attempts }, invalidTime };
  }
  function mergePayload(payload, restoring = false) {
    if (!payload || payload.schema_version !== 1 || payload.course_id !== course.id) throw new Error('记录不属于当前课程，或文件版本不受支持。');
    let accepted = 0, skipped = 0, quarantined = 0;
    // Archived anomalies are retained for export, never silently promoted to progress.
    for (const entry of Array.isArray(payload.quarantined) ? payload.quarantined : []) {
      if (entry && ['answer', 'note', 'checkin'].includes(entry.kind) && typeof entry.id === 'string' && typeof entry.reason === 'string' && entry.record && typeof entry.record === 'object') {
        archiveRecord(entry.kind, entry.id, entry.record, entry.reason);
      }
    }
    if (payload.answers && typeof payload.answers === 'object') for (const [id, raw] of Object.entries(payload.answers)) {
      const item = questionMap.get(id), sanitized = item && sanitizeAnswer(raw, item.q);
      if (!sanitized) { skipped++; continue; }
      if (sanitized.invalidTime) quarantined += archiveRecord('answer', id, raw, '时间在未来或无效，未采用异常时间的答案');
      const incoming = sanitized.answer;
      if (!incoming) continue;
      const previous = state.answers[id];
      if (previous) {
        const winner = previous.updated_at > incoming.updated_at ? previous : incoming;
        const attempts = [...previous.attempts, ...incoming.attempts];
        const unique = new Map(attempts.map(a => [a.at + ':' + a.selected, a]));
        state.answers[id] = { ...winner, attempts: [...unique.values()].sort((a, b) => a.at - b.at) };
      } else state.answers[id] = incoming;
      accepted++;
    }
    for (const l of lessons) {
      const id = nkey(l), note = payload.notes?.[id];
      if (note && typeof note.text === 'string') {
        if (!validTime(note.updated_at) && !unknownTime(note.updated_at)) quarantined += archiveRecord('note', id, note, '时间在未来或无效，未覆盖现有笔记');
        else {
          const at = note.updated_at || 0;
          if (!state.notes[id] || at >= state.notes[id].updated_at) state.notes[id] = { text: note.text, updated_at: at };
        }
      }
      const cursor = payload.cursors?.[id];
      if (restoring && Number.isInteger(cursor) && cursor >= 0 && cursor < l.questions.length) state.cursors[id] = cursor;
    }
    // v1 backups may predate check-ins. Recover only activity with real timestamps.
    for (const raw of Object.values(state.answers)) for (const attempt of raw.attempts) markActivity(attempt.at);
    for (const note of Object.values(state.notes)) if (note.text.trim()) markActivity(note.updated_at);
    if (payload.checkins && typeof payload.checkins === 'object') for (const [day, entry] of Object.entries(payload.checkins)) {
      if (entry && validTime(entry.at) && ['manual', 'study'].includes(entry.kind) && dateKey(entry.at) === day) markActivity(entry.at, entry.kind);
      else if (entry && typeof entry === 'object') quarantined += archiveRecord('checkin', day, entry, '活动日期或时间无效，未计入地图');
    }
    if (restoring) {
      if (lessons.some(l => l.day === payload.lastDay)) state.lastDay = payload.lastDay;
      if (['dashboard', 'learn', 'practice', 'quiz', 'wrong'].includes(payload.view)) state.view = payload.view;
    }
    return { accepted, skipped, quarantined };
  }
  try { const raw = localStorage.getItem(key); if (raw) { try { const result = mergePayload(JSON.parse(raw), true); if (result.quarantined) announce(`已保留 ${result.quarantined} 条异常时间记录，未将异常时间计入进度；可导出备份检查。`); } catch (_) { announce('已有记录无法读取。你可以导入备份继续学习。'); } } const probe = key + ':probe'; localStorage.setItem(probe, '1'); localStorage.removeItem(probe); } catch (_) { storageWarning(); }
  const record = (l, q) => state.answers[qkey(l, q)];
  const correct = (l, q) => { const a = record(l, q); return !!a?.submitted && (a.updated_at === 0 || validTime(a.updated_at)) && a.selected === q.correct_index; };
  const complete = l => l.questions.length > 0 && l.questions.every(q => correct(l, q));
  const wrongHistory = (l, q) => (record(l, q)?.attempts || []).filter(a => (a.at === 0 || validTime(a.at)) && a.selected !== q.correct_index);
  const firstCorrectAt = (l, q) => {
    const correctAttempts = (record(l, q)?.attempts || []).filter(a => a.selected === q.correct_index);
    if (correctAttempts.some(a => a.at === 0)) return null;
    const dated = correctAttempts.filter(a => validTime(a.at));
    return dated.length ? dated.reduce((earliest, a) => Math.min(earliest, a.at), Infinity) : null;
  };
  const datedPass = l => l.questions.every(q => firstCorrectAt(l, q) !== null);
  const plannedMinutes = l => l.activities.reduce((sum, a) => sum + a.minutes, 0);
  function dailyLearning() {
    const days = new Map(), now = Date.now();
    const bucket = day => {
      if (!days.has(day)) days.set(day, { lessons: [], questionIds: new Set(), minutes: 0 });
      return days.get(day);
    };
    for (const l of lessons) {
      const firstCorrect = [];
      for (const q of l.questions) {
        const attempts = (record(l, q)?.attempts || []).filter(a => a.at > 0 && a.at <= now);
        for (const a of attempts) bucket(dateKey(a.at)).questionIds.add(qkey(l, q));
        const first = firstCorrectAt(l, q);
        if (first !== null) firstCorrect.push(first);
      }
      // The lesson is first passed when the last outstanding question is first corrected.
      if (l.questions.length && firstCorrect.length === l.questions.length) {
        const day = bucket(dateKey(Math.max(...firstCorrect)));
        day.lessons.push(l); day.minutes += plannedMinutes(l);
      }
    }
    return days;
  }
  function finishMotion() {
    const content = $('content');
    if (enteringView && motionAllowed()) content.classList.add('motion-enter');
    const children = Array.from(content.children);
    children.forEach((el, i) => el.style?.setProperty('--motion-order', String(i)));
    for (const child of children) {
      if (child.className === 'dashboard-stats') Array.from(child.children).forEach((el, i) => el.style?.setProperty('--motion-order', String(i + 1)));
    }
  }
  function celebrateCheckin(panel) {
    if (!motionAllowed()) return;
    panel.querySelector('.is-today')?.classList.add('just-checked');
    $('today-checkin').classList.add('checkin-success');
    const burst = make('div', 'checkin-burst'); burst.setAttribute('aria-hidden', 'true');
    for (let i = 0; i < 8; i++) {
      const spark = make('span', 'checkin-spark'), angle = i * Math.PI / 4;
      spark.style?.setProperty('--spark-x', Math.round(Math.cos(angle) * 40) + 'px');
      spark.style?.setProperty('--spark-y', Math.round(Math.sin(angle) * 32) + 'px');
      spark.style?.setProperty('--spark-rotation', i * 45 + 'deg'); spark.style?.setProperty('--spark-order', String(i)); burst.append(spark);
    }
    panel.append(burst);
  }
  function updateAnswer(q, selected, submitted) {
    const id = qkey(lesson, q), before = state.answers[id], now = Date.now();
    state.answers[id] = { fingerprint: fingerprint(q), selected, submitted, updated_at: now, attempts: [...(before?.attempts || []), ...(submitted ? [{ selected, at: now }] : [])] };
    if (submitted) markActivity(now);
    save();
  }
  function updateSidebar() {
    const done = lessons.filter(complete).length, percent = lessons.length ? Math.round(done / lessons.length * 100) : 0;
    $('progress-label').textContent = `已通过 ${done} / ${lessons.length} 课`;
    $('progress-percent').textContent = percent + '%'; $('course-progress').value = percent;
    $('wrong-count').textContent = [...questionMap.values()].filter(({ l, q }) => wrongHistory(l, q).length && !correct(l, q)).length;
    $('lesson-list').replaceChildren(...lessons.map(l => {
      const b = button('', 'lesson-link', () => openLesson(l));
      b.append(make('span', 'day-number', String(l.day).padStart(2, '0')), make('span', '', l.title), make('span', 'lesson-check', complete(l) ? '✓' : ''));
      if (lesson?.id === l.id && !['wrong', 'dashboard'].includes(view)) b.setAttribute('aria-current', 'page');
      b.setAttribute('aria-label', `第 ${l.day} 天：${l.title}${complete(l) ? '，已通过' : ''}`);
      return b;
    }));
    if (view === 'dashboard') $('dashboard-link').setAttribute('aria-current', 'page');
    else $('dashboard-link').setAttribute('aria-current', 'false');
  }
  function openDashboard(focus = true) {
    view = 'dashboard'; state.view = view;
    if (location.hash !== '#dashboard') { try { history.replaceState(null, '', '#dashboard'); } catch (_) { location.hash = '#dashboard'; } }
    $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded', 'false');
    save(); render(); if (focus) $('main').focus();
  }
  function openLesson(l, tab = 'learn', qi, focus = true) {
    lesson = l; view = tab; state.lastDay = l.day; state.view = tab;
    if (Number.isInteger(qi)) state.cursors[nkey(l)] = qi;
    if (location.hash !== '#day-' + l.day) { try { history.replaceState(null, '', '#day-' + l.day); } catch (_) { location.hash = '#day-' + l.day; } }
    $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded', 'false');
    save(); render(); if (focus) $('main').focus();
  }
  function changeTab(tab) { view = tab; state.view = tab; save(); render(); $('study-tab-' + tab)?.focus(); }
  function changeQuestion(index) { state.cursors[nkey(lesson)] = index; save(); render(); $('quiz-question-heading')?.focus(); }
  function list(tag, cls, items) { const el = make(tag, cls); for (const text of items) el.append(make('li', '', text)); return el; }
  function card(title, text, cls = '') { const el = make('section', 'card ' + cls); if (title) el.append(make('h3', '', title)); if (text) el.append(make('div', 'section-body', text)); return el; }
  function renderDashboard() {
    const content = $('content'), today = dateKey(), done = lessons.filter(complete).length;
    if (selectedDate === dashboardDate) selectedDate = today;
    dashboardDate = today;
    const percent = lessons.length ? Math.round(done / lessons.length * 100) : 0;
    const items = [...questionMap.values()], answered = items.filter(({ l, q }) => correct(l, q)).length;
    const pending = items.filter(({ l, q }) => wrongHistory(l, q).length && !correct(l, q));
    const next = lessons.find(l => l.day === state.lastDay && !complete(l)) || lessons.find(l => !complete(l));
    const hero = make('section', 'dashboard-hero'), copy = make('div', 'hero-copy');
    copy.append(make('p', 'eyebrow', 'YOUR LEARNING DASHBOARD'), make('h2', '', done === lessons.length && lessons.length ? '每一步积累，都有迹可循。' : '今天，也向目标靠近一点。'), make('p', '', course.goal));
    const heroActions = make('div', 'hero-actions');
    const resume = button(next ? `继续学习 · 第 ${next.day} 天 →` : lessons.length ? '回顾第一课 →' : '暂无课程', 'primary', () => { if (next || lessons[0]) openLesson(next || lessons[0]); });
    resume.id = 'continue-learning'; resume.disabled = !lessons.length; heroActions.append(resume);
    heroActions.append(make('span', 'muted', `${course.days} 个学习日 · 每天 ${course.daily_minutes} 分钟`)); copy.append(heroActions);
    const heroProgress = make('div', 'hero-progress'); heroProgress.append(make('span', '', '课程通过进度'), make('strong', '', percent + '%'));
    const bar = make('progress', 'visually-hidden'); bar.max = 100; bar.value = percent; bar.setAttribute('aria-label', `已通过 ${done} / ${lessons.length} 课`);
    const track = make('div', 'progress-track' + (motionAllowed() && (enteringView || lastProgress !== percent) ? ' motion-progress' : ''));
    track.setAttribute('aria-hidden', 'true');
    const fill = make('span', 'progress-fill'); fill.style?.setProperty('width', percent + '%');
    fill.style?.setProperty('--progress-from', String(enteringView ? 0 : percent ? (lastProgress ?? percent) / percent : 1)); track.append(fill); lastProgress = percent;
    heroProgress.append(bar, track, make('span', '', `已通过 ${done} / ${lessons.length} 课`)); hero.append(copy, heroProgress); content.append(hero);
    const stats = make('div', 'dashboard-stats');
    const minutes = lessons.filter(complete).reduce((total, l) => total + l.activities.reduce((sum, a) => sum + a.minutes, 0), 0);
    for (const [id, label, value, caption] of [
      ['stat-completed', '已通过课程', `${done} / ${lessons.length}`, '本课测验全部订正正确后计入'],
      ['stat-questions', '测验答对', `${answered} / ${items.length}`, '每道题只计一次'],
      ['stat-review', '待订正题目', String(pending.length), '订正后保留错题历史'],
      ['stat-minutes', '已通过课次的计划分钟', String(minutes), '按课程安排汇总，非实际计时']
    ]) {
      const stat = make('section', 'stat-card'), valueEl = make('strong', 'stat-value', value); valueEl.id = id;
      stat.append(make('p', 'stat-label', label), valueEl, make('p', 'stat-caption', caption)); stats.append(stat);
    }
    content.append(stats);
    const undated = lessons.filter(l => complete(l) && !datedPass(l)).length;
    if (undated) { const note = make('p', 'dashboard-note', `${undated} 课的通过日期未知：已保留旧备份进度，未把它们计入某一天的学习量。`); note.id = 'progress-date-note'; content.append(note); }
    if (state.quarantined.length) content.append(make('p', 'dashboard-note', `${state.quarantined.length} 条异常记录已单独保留，异常时间不计入进度。导出备份包含这些原始记录，修正后可重新导入。`));
    const checkin = make('section', 'dashboard-panel checkin-panel'), header = make('div', 'panel-heading');
    const activity = dailyLearning(), emptyDay = () => ({ lessons: [], questionIds: new Set(), minutes: 0 });
    if (!selectedDate || selectedDate > today) selectedDate = today;
    const title = make('div'); title.append(make('p', 'eyebrow', 'A LITTLE MORE, EVERY DAY'), make('h3', '', '每天的学习，都看得见'), make('p', '', `近 13 周 · ${course.timezone} · 颜色随每日完成课数加深`));
    const check = button(state.checkins[today] ? '✓ 今日已打卡' : '今日打卡 +', 'secondary', () => { markActivity(Date.now(), 'manual'); selectedDate = dateKey(); pendingCelebration = true; save(); render(); announce('今日打卡已记录。完成多课会继续累加到今天的学习量。'); });
    check.id = 'today-checkin'; check.disabled = !!state.checkins[today]; header.append(title, check); checkin.append(header);
    const dates = Object.keys(state.checkins).filter(day => day <= today).sort();
    let longest = 0, run = 0, previous;
    for (const day of dates) { run = previous && shiftDate(previous, 1) === day ? run + 1 : 1; longest = Math.max(longest, run); previous = day; }
    let streak = 0, cursor = state.checkins[today] ? today : shiftDate(today, -1);
    while (state.checkins[cursor]) { streak++; cursor = shiftDate(cursor, -1); }
    const summary = make('div', 'checkin-summary');
    for (const [id, value, label] of [['checkin-total', dates.length, '累计打卡'], ['checkin-streak', streak, '当前连续'], ['checkin-longest', longest, '最长连续']]) {
      const group = make('div'), number = make('strong', '', String(value)); number.id = id; group.append(number, make('span', '', ` 天 · ${label}`)); summary.append(group);
    }
    checkin.append(summary);
    const scroll = make('div', 'checkin-grid-scroll'), weekdays = make('div', 'map-weekdays'); weekdays.setAttribute('aria-hidden', 'true');
    for (const day of ['一', '二', '三', '四', '五', '六', '日']) weekdays.append(make('span', '', day));
    const map = make('div', 'checkin-map'); map.id = 'checkin-map'; map.setAttribute('aria-label', '近 13 周每日学习记录，按周一至周日排列');
    const weekday = (new Date(today + 'T12:00:00Z').getUTCDay() + 6) % 7, start = shiftDate(today, -weekday - 84);
    const detail = make('p', 'map-note', '点击任意日期，查看当天完成的课程、答题量与对应计划时长。'); detail.id = 'checkin-detail'; detail.setAttribute('role', 'status');
    const dayDetail = make('section', 'day-detail'); dayDetail.id = 'day-detail'; dayDetail.setAttribute('aria-label', '所选日期的学习量');
    const cells = new Map();
    function showDay(date) {
      selectedDate = date;
      for (const [cellDate, cell] of cells) { cell.setAttribute('aria-pressed', String(cellDate === date)); if (cellDate === date) cell.classList.add('is-selected'); else cell.classList.remove('is-selected'); }
      const day = activity.get(date) || emptyDay(), entry = state.checkins[date];
      const status = day.lessons.length ? `今天多走了 ${day.lessons.length} 步` : day.questionIds.size ? '练习正在积累' : entry ? '已经为学习留出空间' : date === today ? '今天，从一小步开始' : '这一天还没有学习记录';
      dayDetail.replaceChildren(make('p', 'day-detail-date', `${date}${date === today ? ' · 今天' : ''}`), make('h4', 'day-detail-title', date === today ? status : day.lessons.length ? `完成了 ${day.lessons.length} 课` : status));
      const numbers = make('div', 'day-detail-stats');
      for (const [id, value, label] of [['day-completed-count', day.lessons.length, '完成课程 / 课'], ['day-question-count', day.questionIds.size, '答题 / 道'], ['day-planned-minutes', day.minutes, '对应计划 / 分钟']]) {
        const group = make('div'), number = make('strong', '', String(value)); number.id = id; group.append(number, make('span', '', label)); numbers.append(group);
      }
      dayDetail.append(numbers);
      if (day.lessons.length) {
        const list = make('ul', 'day-detail-lessons');
        for (const l of day.lessons) { const item = make('li'); item.append(button(`✓ 第 ${l.day} 课 · ${l.title}`, 'day-lesson-link', () => openLesson(l))); list.append(item); } dayDetail.append(list);
      }
      dayDetail.append(make('p', 'map-note', '一天可以学多课，完成量持续累加。时长来自当日首次通过课次的计划预算，未做实际计时。'));
      detail.textContent = `${date} · 完成 ${day.lessons.length} 课，答题 ${day.questionIds.size} 道，计划 ${day.minutes} 分钟。`;
    }
    for (let week = 0; week < 13; week++) {
      const column = make('div', 'checkin-week');
      for (let day = 0; day < 7; day++) {
        const date = shiftDate(start, week * 7 + day), entry = state.checkins[date], future = date > today, daily = activity.get(date) || emptyDay();
        const status = future ? '尚未到来' : entry ? entry.kind === 'study' ? '有学习活动' : '已主动打卡' : '未打卡';
        const level = daily.lessons.length >= 3 ? 4 : daily.lessons.length === 2 ? 3 : daily.lessons.length || daily.questionIds.size ? 2 : entry ? 1 : 0;
        const volume = `完成 ${daily.lessons.length} 课，答题 ${daily.questionIds.size} 道，计划 ${daily.minutes} 分钟`;
        const cell = button('', `checkin-cell level-${level}${date === today ? ' is-today' : ''}${future ? ' is-future' : ''}`, () => showDay(date));
        cell.style?.setProperty('--motion-order', String(week)); cells.set(date, cell);
        cell.disabled = future; cell.title = `${date} · ${status} · ${volume}`; cell.setAttribute('aria-label', `${date}，${status}，${volume}${date === today ? '，今天' : ''}`); if (date === today) cell.setAttribute('aria-current', 'date'); column.append(cell);
      }
      map.append(column);
    }
    scroll.append(weekdays, map); checkin.append(scroll);
    const legend = make('div', 'map-legend');
    for (const [level, label] of [[0, '未记录'], [1, '有活动'], [2, '答题 / 1课'], [3, '2课'], [4, '3课及以上']]) { const item = make('span'), swatch = make('i', `checkin-cell level-${level}`); swatch.setAttribute('aria-hidden', 'true'); item.append(swatch, make('span', '', label)); legend.append(item); }
    const range = make('span', 'map-range', `${start} — ${shiftDate(start, 90)}`); legend.append(range);
    showDay(selectedDate);
    checkin.append(legend, detail, dayDetail); content.append(checkin);
    scroll.scrollLeft = scroll.scrollWidth;
    if (pendingCelebration) { celebrateCheckin(checkin); pendingCelebration = false; }
    content.append(make('p', 'dashboard-note', '记录保存在当前浏览器，可导出备份并在其他设备导入。不同设备与副本之间需要手动同步。'));
  }
  function render() {
    const stamp = view + ':' + (view === 'dashboard' || view === 'wrong' ? '' : lesson?.id);
    enteringView = stamp !== lastRenderedView; lastRenderedView = stamp;
    $('content').classList.remove('motion-enter');
    updateSidebar(); $('content').replaceChildren(); $('lesson-heading').replaceChildren(); $('study-tabs').replaceChildren();
    $('study-tabs').hidden = ['dashboard', 'wrong'].includes(view);
    if (view === 'dashboard') { renderDashboard(); finishMotion(); return; }
    if (view === 'wrong') { renderWrong(); finishMotion(); return; }
    const heading = $('lesson-heading');
    heading.append(make('p', 'lesson-kicker', `DAY ${String(lesson.day).padStart(2, '0')} / ${course.days} · 每天 ${course.daily_minutes} 分钟`), make('h2', '', lesson.title));
    if (complete(lesson)) heading.append(make('span', 'badge', '✓ 本课已通过'));
    heading.append(make('p', 'lesson-goal', course.goal));
    [['learn', '01 阅读学习'], ['practice', '02 练习与笔记'], ['quiz', '03 当日测验']].forEach(([tab, label]) => {
      const b = button(label, 'tab', () => changeTab(tab)); b.id = 'study-tab-' + tab; if (view === tab) b.setAttribute('aria-current', 'step'); $('study-tabs').append(b);
    });
    if (view === 'quiz') renderQuiz(); else if (view === 'practice') renderPractice(); else renderLearning();
    finishMotion();
  }
  function renderLearning() {
    const content = $('content'), intro = card('今天你会学会'); intro.append(list('ul', 'objectives', lesson.objectives)); content.append(intro);
    const activities = make('div', 'activity-list');
    const kindNames = { read: '阅读', reading: '阅读', practice: '练习', quiz: '测验', review: '复习', notes: '笔记', exercise: '练习' };
    for (const a of lesson.activities) { const chip = make('div', 'activity', kindNames[a.kind] || a.kind); chip.append(make('span', '', a.minutes + ' 分钟')); activities.append(chip); } content.append(activities);
    if (lesson.review_of?.length) content.append(make('p', 'muted', '本课回顾：第 ' + lesson.review_of.join('、') + ' 天的内容。'));
    for (const s of lesson.sections) {
      const el = card(s.title, s.body);
      for (const formula of Array.isArray(s.formulas) ? s.formulas : []) el.append(renderFormula(formula));
      for (const diagram of Array.isArray(s.diagrams) ? s.diagrams : []) el.append(renderDiagram(diagram));
      if (s.example) { const example = make('div', 'example'); example.append(make('strong', '', '用一个例子理解'), make('div', 'example-body', s.example)); el.append(example); }
      content.append(el);
    }
    const takeaways = card('带走这几个要点', '', 'soft'); takeaways.append(list('ul', 'takeaways', lesson.takeaways)); content.append(takeaways);
    const sources = data.sources.filter(s => lesson.source_ids.includes(s.id));
    if (sources.length) {
      const el = card('本课来源'), ul = make('ul', 'source-list');
      for (const s of sources) { const li = make('li'); let url; try { const parsed = new URL(s.url); if (['https:', 'http:'].includes(parsed.protocol)) url = parsed.href; } catch (_) { /* Local or absent sources are displayed as plain text. */ }
        if (url) { const a = make('a', '', s.title); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; li.append(a); } else li.append(make('span', '', s.title));
        if (s.locator) li.append(make('span', 'source-locator', s.locator)); ul.append(li);
      } el.append(ul); content.append(el);
    }
    const actions = make('div', 'actions'); actions.append(button('开始练习与笔记 →', 'primary', () => changeTab('practice'))); content.append(actions);
  }
  function parseMathML(markup, expression) {
    if (typeof DOMParser !== 'function') return { warning: '当前环境无法显示数学排版，已保留可读表达式。' };
    const namespace = 'http://www.w3.org/1998/Math/MathML';
    const elements = new Set(['math', 'mrow', 'mi', 'mn', 'mo', 'mtext', 'mfrac', 'msqrt', 'mroot', 'msup', 'msub', 'msubsup', 'munder', 'mover', 'munderover', 'mtable', 'mtr', 'mtd', 'mspace', 'mstyle']);
    const attributes = new Set(['display', 'mathvariant', 'displaystyle', 'scriptlevel', 'stretchy', 'fence', 'separator', 'accent', 'accentunder', 'linethickness', 'columnalign', 'rowalign', 'columnspacing', 'rowspacing', 'notation', 'width', 'height', 'depth', 'lspace', 'rspace', 'mathsize', 'mathcolor', 'mathbackground', 'aria-label']);
    const arity = { mfrac: 2, mroot: 2, msup: 2, msub: 2, msubsup: 3, munder: 2, mover: 2, munderover: 3 };
    const tokens = new Set(['mi', 'mn', 'mo', 'mtext']);
    try {
      if (typeof markup !== 'string' || /<!\s*(?:DOCTYPE|ENTITY)|<\?/i.test(markup)) throw new Error('Unexpected declaration');
      const xml = new DOMParser().parseFromString(markup, 'application/xml'), root = xml.documentElement;
      if (!root || root.localName !== 'math' || root.namespaceURI !== namespace || xml.getElementsByTagName('parsererror').length) throw new Error('Invalid MathML');
      let count = 0;
      function check(node, depth = 0) {
        if (++count > 1000 || depth > 40 || !elements.has(node.localName) || node.namespaceURI !== namespace) throw new Error('Unexpected MathML node');
        for (const attr of Array.from(node.attributes)) {
          if (attr.name === 'xmlns' && node === root && attr.value === namespace) continue;
          if (attr.namespaceURI || !attributes.has(attr.name) || (attr.name === 'aria-label' && node !== root) || /url\s*\(|(?:javascript|https?|data)\s*:|@import|expression\s*\(/i.test(attr.value)) throw new Error('Unexpected MathML attribute');
        }
        const childNodes = Array.from(node.childNodes), children = childNodes.filter(child => child.nodeType === 1);
        const directText = childNodes.filter(child => [3, 4].includes(child.nodeType)).map(child => child.textContent || '').join('');
        if (arity[node.localName] && children.length !== arity[node.localName]) throw new Error('Invalid MathML arity');
        if (node.localName === 'math' && !children.length) throw new Error('Empty MathML');
        if (tokens.has(node.localName) ? children.length || !directText.trim() : directText.trim()) throw new Error('Unexpected MathML text');
        if (/\\(?:[A-Za-z]+|[\[\]()])|\$\$/.test(directText)) throw new Error('Unrendered TeX');
        if (node.localName === 'mtable' && (!children.length || children.some(child => child.localName !== 'mtr'))) throw new Error('Invalid MathML table');
        if (node.localName === 'mtr' && (!children.length || children.some(child => child.localName !== 'mtd'))) throw new Error('Invalid MathML row');
        for (const child of childNodes) {
          if (child.nodeType === 1) check(child, depth + 1);
          else if (![3, 4, 8].includes(child.nodeType)) throw new Error('Unexpected MathML content');
        }
      }
      check(root);
      const result = document.importNode(root, true);
      result.setAttribute('display', 'block'); result.setAttribute('aria-label', expression);
      return { node: result };
    } catch (_) { return { warning: '数学排版未能正确解析，已显示表达式；请核对该公式的排版。' }; }
  }
  function renderFormula(formula) {
    formula = formula && typeof formula === 'object' ? formula : {};
    const el = make('section', 'formula-block');
    if (formula.title) el.append(make('h4', 'formula-title', formula.title));
    const expression = typeof formula.expression === 'string' ? formula.expression : '公式表达式缺失，请先补全。';
    const display = make('div', 'formula-display');
    if (formula.mathml) {
      const result = parseMathML(formula.mathml, expression);
      if (result.node) display.append(result.node);
      else {
        display.append(make('div', 'formula-expression', expression));
        const warning = make('p', 'formula-warning', result.warning); warning.setAttribute('role', 'status'); el.append(warning);
      }
    } else display.append(make('div', 'formula-expression', expression));
    el.append(display);
    if (formula.explanation) el.append(make('p', 'formula-explanation', formula.explanation));
    if (Array.isArray(formula.variables) && formula.variables.length) {
      const wrap = make('div', 'formula-table-scroll'), table = make('table', 'formula-variables');
      const caption = make('caption', '', '符号与单位'), head = make('thead'), row = make('tr');
      for (const label of ['符号', '含义', '单位']) { const th = make('th', '', label); th.setAttribute('scope', 'col'); row.append(th); }
      head.append(row); table.append(caption, head);
      const body = make('tbody');
      for (const variable of formula.variables) {
        if (!variable || typeof variable !== 'object') continue;
        const tr = make('tr');
        for (const value of [variable.symbol, variable.meaning, variable.unit]) tr.append(make('td', '', typeof value === 'string' ? value : '待补充'));
        body.append(tr);
      }
      table.append(body); wrap.append(table); el.append(wrap);
    }
    if (formula.conditions) { const conditions = make('p', 'formula-conditions'); conditions.append(make('strong', '', '适用条件'), make('span', '', formula.conditions)); el.append(conditions); }
    return el;
  }
  function renderDiagram(diagram) {
    diagram = diagram && typeof diagram === 'object' ? diagram : {};
    const figure = make('figure', 'lesson-diagram');
    if (diagram.title) figure.append(make('h4', 'diagram-title', diagram.title));
    if (typeof diagram.svg === 'string' && diagram.svg.trim()) {
      const scroll = make('div', 'diagram-scroll'), img = make('img', 'diagram-image');
      img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(diagram.svg);
      img.alt = typeof diagram.alt === 'string' ? diagram.alt : '示意图缺少替代文字，请核对。';
      scroll.append(img); figure.append(scroll, make('p', 'diagram-hint', '宽图可横向滑动，查看完整连接与标注。'));
    } else figure.append(make('p', 'formula-warning', '示意图内容缺失，请先补全。'));
    if (diagram.caption) figure.append(make('figcaption', '', diagram.caption));
    return figure;
  }
  function practiceText(value) { if (typeof value === 'string') return value; if (Array.isArray(value)) return value.map(practiceText).join('\n'); if (value && typeof value === 'object') return Object.values(value).map(practiceText).join('\n'); return value == null ? '' : String(value); }
  function renderPractice() {
    const content = $('content'); if (lesson.practice) content.append(card('把知识用起来', practiceText(lesson.practice)));
    else content.append(card('用自己的话解释', '合上阅读内容，用自己的话写下今天学到的要点，再举一个你熟悉的例子。'));
    const el = card(), label = make('label', 'notes-label', '我的学习笔记'); label.htmlFor = 'lesson-notes';
    const notes = make('textarea'); notes.id = 'lesson-notes'; notes.placeholder = '记录你的理解、练习答案，以及还想弄清的问题……'; notes.value = state.notes[nkey(lesson)]?.text || '';
    const status = make('p', 'save-status', storageAvailable ? '输入后自动保存在当前浏览器' : '暂存于本次页面，请导出备份'); status.setAttribute('role', 'status');
    notes.addEventListener('input', () => { const now = Date.now(); state.notes[nkey(lesson)] = { text: notes.value, updated_at: now }; if (notes.value.trim()) markActivity(now); save(); status.textContent = storageAvailable ? '已自动保存' : '已暂存，请导出备份'; });
    el.append(label, notes, status); content.append(el);
    const actions = make('div', 'actions'); actions.append(button('← 返回阅读', 'secondary', () => changeTab('learn')), button('进入当日测验 →', 'primary', () => changeTab('quiz'))); content.append(actions);
  }
  function renderQuiz() {
    const content = $('content'), questions = lesson.questions, current = Math.min(state.cursors[nkey(lesson)] || 0, Math.max(questions.length - 1, 0));
    content.append(make('p', 'muted', '每道题答对后，本课才会通过。答错时可以查看解析，再试一次。'));
    if (!questions.length) { content.append(card('本课缺少测验', '暂不记录通过，请先补齐本课知识检查。')); return; }
    const nav = make('nav', 'question-nav'); nav.setAttribute('aria-label', '测验题目');
    questions.forEach((q, i) => { const a = record(lesson, q), b = button(String(i + 1), correct(lesson, q) ? 'correct' : a?.submitted ? 'wrong' : '', () => changeQuestion(i)); if (i === current) b.setAttribute('aria-current', 'true'); b.setAttribute('aria-label', `第 ${i + 1} 题，${correct(lesson, q) ? '已答对' : a?.submitted ? '待重试' : '未完成'}`); nav.append(b); }); content.append(nav);
    const q = questions[current], a = record(lesson, q), el = card(); el.append(make('p', 'quiz-counter', `第 ${current + 1} / ${questions.length} 题 · 已答对 ${questions.filter(item => correct(lesson, item)).length} 题`));
    const fieldset = make('fieldset'), legend = make('legend', '', q.prompt), options = make('div', 'options'); legend.id = 'quiz-question-heading'; legend.tabIndex = -1; fieldset.append(legend, options);
    q.options.forEach((text, i) => { const label = make('label', 'option'), input = make('input'); input.type = 'radio'; input.name = 'current-question'; input.id = 'answer-option-' + i; input.value = String(i); input.checked = a?.selected === i; input.disabled = !!a?.submitted; label.htmlFor = input.id;
      input.addEventListener('change', () => { updateAnswer(q, i, false); submit.disabled = false; }); label.append(input, make('span', '', text)); options.append(label);
    }); el.append(fieldset);
    if (a?.submitted) {
      const isCorrect = correct(lesson, q), feedback = make('div', 'feedback' + (isCorrect ? '' : ' incorrect')); feedback.setAttribute('role', 'status'); feedback.tabIndex = -1;
      feedback.append(make('strong', '', isCorrect ? '答对了，理解又深了一步。' : '这次还没有答对，看看每个选项的原因。'));
      q.options.forEach((option, i) => feedback.append(make('p', 'explanation-item', `${i === q.correct_index ? '✓ 正确选项' : '○ 其他选项'}${i === a.selected ? ' · 你的选择' : ''}\n${option}\n${q.explanations[i]}`)));
      el.append(feedback);
    }
    const actions = make('div', 'actions'), submit = button('提交答案', 'primary', () => { const selected = record(lesson, q)?.selected; if (!Number.isInteger(selected)) return; updateAnswer(q, selected, true); render(); $('content').querySelector('.feedback')?.focus(); });
    submit.disabled = !Number.isInteger(a?.selected); if (!a?.submitted) actions.append(submit);
    else if (!correct(lesson, q)) actions.append(button('再试一次', 'primary', () => { updateAnswer(q, null, false); render(); $('answer-option-0')?.focus(); }));
    if (current > 0) actions.append(button('上一题', 'secondary', () => changeQuestion(current - 1)));
    if (current + 1 < questions.length) actions.append(button('下一题 →', 'secondary', () => changeQuestion(current + 1)));
    el.append(actions); content.append(el); appendCompletion();
  }
  function appendCompletion() {
    if (!complete(lesson)) return;
    const el = make('div', 'completion'); el.setAttribute('role', 'status'); el.append(make('h3', '', '✓ 本课已通过'), make('p', '', '已完成本课知识检查，进度和错题历史已记录。实际能力仍需通过练习、项目或口述验证。'));
    const next = lessons[lessons.indexOf(lesson) + 1]; if (next) el.append(button('继续下一课 →', 'primary', () => openLesson(next))); else el.append(make('p', '', lessons.every(complete) ? '所有课程的知识检查已通过。可以导出记录，再核对练习与项目成果。' : '这是最后一课。你也可以回到目录，继续完成之前的知识检查。'));
    $('content').append(el);
  }
  function renderWrong() {
    $('lesson-heading').append(make('p', 'lesson-kicker', 'REVISIT & UNDERSTAND'), make('h2', '', '错题回顾'), make('p', 'lesson-goal', '答对后仍保留曾经的误选，方便回看理解是怎样建立起来的。'));
    const items = [...questionMap.values()].filter(({ l, q }) => wrongHistory(l, q).length);
    if (!items.length) $('content').append(make('p', 'empty', '还没有错题。完成每课测验后，你的复习线索会出现在这里。'));
    for (const { l, q } of items) {
      const history = wrongHistory(l, q), resolved = correct(l, q), el = card(), heading = make('div', 'history-title'); heading.append(make('h3', '', q.prompt), make('span', 'badge', resolved ? '已订正 · 历史保留' : '待订正')); el.append(heading, make('p', 'history-meta', `第 ${l.day} 天 · ${l.title} · 曾误选 ${history.length} 次`));
      for (const choice of [...new Set(history.map(a => a.selected))]) el.append(make('p', 'explanation-item', `曾选：${q.options[choice]}\n${q.explanations[choice]}`));
      const actions = make('div', 'actions'); actions.append(button(resolved ? '回看这道题 →' : '前往重试 →', 'secondary', () => openLesson(l, 'quiz', l.questions.indexOf(q)))); el.append(actions); $('content').append(el);
    }
    const actions = make('div', 'actions'); actions.append(button('返回当前课程', 'primary', () => openLesson(lesson))); $('content').append(actions);
  }
  $('menu-toggle').addEventListener('click', () => { const open = $('sidebar').classList.toggle('open'); $('menu-toggle').setAttribute('aria-expanded', String(open)); });
  $('dashboard-link').addEventListener('click', () => openDashboard());
  $('wrong-book').addEventListener('click', () => { view = 'wrong'; state.view = view; save(); render(); $('sidebar').classList.remove('open'); $('menu-toggle').setAttribute('aria-expanded', 'false'); $('main').focus(); });
  $('export-progress').addEventListener('click', () => { const blob = new Blob([JSON.stringify({ ...state, exported_at: new Date().toISOString() }, null, 2)], { type: 'application/json' }), url = URL.createObjectURL(blob), a = make('a'); a.href = url; a.download = 'KnowledgeToPlan-' + String(course.id).replace(/[^\p{L}\p{N}_-]/gu, '_') + '-progress.json'; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000); announce(`学习记录已导出，包含进度、错题历史、笔记和异常记录。${blob.size > 10 * 1024 * 1024 ? '文件较大，恢复时请保持页面打开；浏览器存储容量可能不足。' : ''}`); });
  $('import-progress').addEventListener('click', () => $('import-file').click());
  $('import-file').addEventListener('change', async event => { const file = event.target.files[0]; if (!file) return; try { if (file.size > 10 * 1024 * 1024) announce('正在读取较大的学习记录，请保持页面打开；存储不足时仍可在本次页面学习并导出。'); const result = mergePayload(JSON.parse(await file.text())); save(); render(); announce(`导入完成，合并了 ${result.accepted} 道题的记录。${result.skipped ? `另有 ${result.skipped} 条记录因题目已变更或格式无效而跳过。` : ''}${result.quarantined ? `${result.quarantined} 条异常时间记录已单独保留，可导出检查。` : ''}笔记已按更新时间合并。`); } catch (error) { announce('无法导入：' + (error instanceof SyntaxError ? '文件不是有效的 JSON 记录。' : error.message)); } event.target.value = ''; });
  $('course-title').textContent = course.title; document.title = course.title + ' · KnowledgeToPlan';
  $('course-meta').textContent = `${course.days} 天 · 每天 ${course.daily_minutes} 分钟${course.start_date ? ' · ' + course.start_date + ' 开始' : ''}${course.study_time ? ' · ' + course.study_time + ' ' + course.timezone : ''}`;
  const dayFromHash = () => { const match = /^#day-(\d+)$/.exec(location.hash); return match && lessons.find(l => l.day === Number(match[1])); };
  const refreshCalendar = () => { if (view === 'dashboard' && dashboardDate !== dateKey()) render(); };
  window.addEventListener('focus', refreshCalendar);
  document.addEventListener?.('visibilitychange', refreshCalendar);
  if (typeof window.setInterval === 'function') window.setInterval(refreshCalendar, 30000);
  window.addEventListener('hashchange', () => { const target = dayFromHash(); if (target) openLesson(target); else if (location.hash === '#dashboard' || !location.hash) openDashboard(); });
  lesson = dayFromHash() || lessons.find(l => l.day === state.lastDay) || lessons[0];
  if (dayFromHash()) openLesson(lesson, dayFromHash().day === state.lastDay && ['learn', 'practice', 'quiz'].includes(state.view) ? state.view : 'learn', undefined, false);
  else openDashboard(false);
})();
