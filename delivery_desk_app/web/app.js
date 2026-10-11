// Delivery Desk: the page's behaviour. It shows things and asks the bridge (Python) to do things.
// Rule: anything that came from a delivery or from the computer goes into the page with
// textContent, never as HTML, so a file name that looks like code is shown, never run.
'use strict';

(function () {
  const state = { folder: null, manifest: null, view: null, result: null, status: null, filter: 'ALL' };
  const byId = (id) => document.getElementById(id);
  const api = () => window.pywebview.api;
  const plural = (n, one, many) => n.toLocaleString('en-GB') + ' ' + (n === 1 ? one : many);

  // Builds an element whose words are always plain text, never HTML.
  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) { node.className = className; }
    if (text !== undefined && text !== null) { node.textContent = text; }
    return node;
  }
  const FIELDS = ['reports_dir', 'ops_hub_path', 'ops_hub_config', 'ai_triage_path', 'ai_triage_python'];
  const SECRETS = ['webhook_secret', 'ai_key'];

  // --- Navigation -----------------------------------------------------------------------------------

  function show(screen) {
    document.querySelectorAll('.screen').forEach((s) => { s.hidden = s.id !== 'screen-' + screen; });
    document.querySelectorAll('.nav-link').forEach((b) => {
      if (b.dataset.screen === screen) { b.setAttribute('aria-current', 'page'); } else { b.removeAttribute('aria-current'); }
    });
    if (screen === 'settings') { loadSettings(); }
  }

  function toast(text) {
    const box = byId('toast');
    box.textContent = text;
    box.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { box.hidden = true; }, 2600);
  }

  // --- Start: the two cards -------------------------------------------------------------------------

  function accept(kind, info) {
    if (!info) { return; }                               // the picker was cancelled
    byId(kind + 'Error').textContent = info.ok ? '' : info.error;
    if (info.ok) { state[kind] = info; }
    renderCards();
  }

  function renderCards() {
    const folder = state.folder;
    const manifest = state.manifest;
    byId('folderEmpty').hidden = !!folder;
    byId('folderChosen').hidden = !folder;
    byId('folderCard').classList.toggle('is-chosen', !!folder);
    if (folder) {
      byId('folderName').textContent = folder.name;
      byId('folderPath').textContent = folder.path;
      byId('folderFiles').textContent = plural(folder.files, 'file', 'files');
    }
    byId('manifestEmpty').hidden = !!manifest;
    byId('manifestChosen').hidden = !manifest;
    byId('manifestCard').classList.toggle('is-chosen', !!manifest);
    if (manifest) {
      byId('manifestName').textContent = manifest.name;
      byId('manifestPath').textContent = manifest.path;
      byId('manifestEntries').textContent = plural(manifest.entries, 'entry', 'entries');
    }
    const ready = !!(folder && manifest);
    byId('checkButton').disabled = !ready;
    let hint = 'Add the delivery folder and its manifest to start.';
    if (ready) { hint = 'The check reads every file once, so a large delivery takes a while.'; }
    else if (folder) { hint = 'Now add the manifest.'; }
    else if (manifest) { hint = 'Now add the delivery folder.'; }
    byId('readyHint').textContent = hint;
  }

  function watchDragging(card) {
    card.addEventListener('dragenter', () => card.classList.add('is-dragging'));
    card.addEventListener('dragover', (e) => { e.preventDefault(); card.classList.add('is-dragging'); });
    card.addEventListener('dragleave', (e) => { if (!card.contains(e.relatedTarget)) { card.classList.remove('is-dragging'); } });
    card.addEventListener('drop', () => card.classList.remove('is-dragging'));
  }

  // --- Checking ----------------------------------------------------------------------------------------

  let poll = null;
  let polling = false;

  async function startCheck() {
    const started = await api().start_check(state.folder.path, state.manifest.path);
    if (!started.ok) { toast(started.error); return; }
    byId('checkName').textContent = state.folder.name;
    byId('checkManifest').textContent = state.manifest.name;
    byId('stopButton').disabled = false;
    byId('stopButton').textContent = 'Stop checking';
    renderProgress({ progress: {}, eta_seconds: null });
    show('checking');
    poll = setInterval(pollCheck, 300);
  }

  async function pollCheck() {
    if (polling) { return; }                       // never two questions in flight at once
    polling = true;
    try {
      const status = await api().check_status();
      if (status.state === 'running') { renderProgress(status); return; }
      clearInterval(poll);
      poll = null;
      await finished(status);
    } finally {
      polling = false;
    }
  }

  async function finished(status) {
    state.status = status;
    if (status.state === 'stopped') { show('start'); toast('Stopped. Nothing was changed.'); return; }
    if (status.state === 'failed') { showNotChecked(status.error, status.messages); return; }
    const outcome = status.outcome;
    if (!outcome || !outcome.report_id) { showNotChecked(notCheckedReason(status), status.messages); return; }
    const view = await api().get_result(outcome.report_id);
    if (!view.ok) { showNotChecked(view.error, status.messages); return; }
    state.result = view;
    if (view.result === 'CLEAN') { renderAllClear(view, status); } else { renderResults(view, status); }
  }

  function timeLeft(seconds) {
    if (seconds === null || seconds === undefined) { return 'working out the time left'; }
    if (seconds < 60) { return 'less than a minute left'; }
    const minutes = Math.round(seconds / 60);
    if (minutes < 60) { return 'about ' + minutes + ' min left'; }
    return 'about ' + Math.floor(minutes / 60) + ' h ' + (minutes % 60) + ' min left';
  }

  function renderProgress(status) {
    const p = status.progress || {};
    const stage = p.stage || 'preparing';
    const done = p.files_done || 0;
    const total = p.files_total || 0;
    let pct = 0;
    if (p.bytes_total) { pct = Math.floor(100 * (p.bytes_done || 0) / p.bytes_total); }
    else if (total) { pct = Math.floor(100 * done / total); }
    if (stage === 'finished') { pct = 100; }
    byId('checkPct').textContent = pct + '%';
    byId('checkBar').style.width = pct + '%';
    byId('checkBarBox').setAttribute('aria-valuenow', String(pct));
    byId('checkCounts').textContent = stage === 'preparing'
      ? 'Getting ready…' : done.toLocaleString('en-GB') + ' of ' + plural(total, 'file', 'files') + ' · ' + timeLeft(status.eta_seconds);
    byId('nowFile').textContent = p.current_file || '…';
    const comparing = stage === 'finished' || (stage === 'hashing' && total > 0 && done >= total);
    const order = ['preparing', 'hashing', 'comparing'];
    const active = comparing ? 'comparing' : stage;
    order.forEach((name, i) => {
      const item = byId('stage-' + name);
      const activeIndex = order.indexOf(active);
      item.classList.toggle('is-active', i === activeIndex);
      item.classList.toggle('is-done', i < activeIndex);
    });
  }

  async function stopCheck() {
    byId('stopButton').disabled = true;
    byId('stopButton').textContent = 'Stopping…';
    await api().stop_check();
  }

  // --- Results ---------------------------------------------------------------------------------------

  const SEVERITY = { ERROR: ['Error', 'pill-bad'], WARNING: ['Warning', 'pill-warn'], INFO: ['Info', ''] };

  function alertLine(id, view, status) {
    const line = byId(id);
    line.hidden = !status.alerts;
    if (!status.alerts) { return; }
    const said = (status.messages || []).join('\n');
    let text = 'Logged by delivery-ops-hub, which raises an alert for deliveries with problems.';
    let warn = false;
    if (said.includes('NOT DELIVERED')) {
      text = 'Not delivered to n8n. It is waiting in delivery-ops-hub’s outbox, to be sent again later. See what the tools said, below.';
      warn = true;
    } else if (said.includes('ALERT FAILED')) {
      text = 'Logged, but the alert itself failed. Tell the team directly.';
      warn = true;
    } else if (status.outcome && status.outcome.code === 3) {
      text = 'delivery-ops-hub reported a problem with the alert. See what the tools said, below.';
      warn = true;
    }
    line.textContent = text;
    line.classList.toggle('is-warn', warn);
  }

  function renderAllClear(view, status) {
    byId('allclear-title').textContent = view.headline;
    byId('acManifests').textContent = view.manifests.join(', ');
    byId('acTree').textContent = view.tree;
    byId('acManifest').textContent = view.manifests.join(', ');
    byId('acWhen').textContent = view.checked_at;
    const list = byId('acChecked');
    list.replaceChildren();
    view.categories.forEach((c) => {
      const item = el('li');
      item.append(el('span', 'pill ' + (c.count ? 'pill-warn' : 'pill-ok'), c.count ? '!' : '✓'),
                  el('span', 'label', c.label), el('span', 'value', c.count ? plural(c.count, 'found', 'found') : 'None'));
      list.append(item);
    });
    alertLine('acAlert', view, status);
    show('allclear');
  }

  function renderResults(view, status) {
    const problems = view.result === 'PROBLEMS FOUND';
    const pill = byId('rsPill');
    pill.textContent = view.result;
    pill.className = 'pill ' + (problems ? 'pill-bad' : 'pill-warn');
    byId('results-title').textContent = view.headline;
    byId('rsSubline').textContent = view.subline || '';
    byId('rsTree').textContent = view.tree;
    byId('rsManifests').textContent = view.manifests.join(', ');
    byId('rsWhen').textContent = view.checked_at;
    byId('rsErrors').textContent = (view.counts.ERROR || 0).toLocaleString('en-GB');
    byId('rsWarnings').textContent = (view.counts.WARNING || 0).toLocaleString('en-GB');
    byId('rsInfo').textContent = (view.counts.INFO || 0).toLocaleString('en-GB');
    byId('startNote').hidden = !view.has_note;
    alertLine('rsAlert', view, status);
    renderCauses(view.causes);
    const chipText = { ALL: ['All', view.findings_total], ERROR: ['Errors', view.counts.ERROR || 0],
                       WARNING: ['Warnings', view.counts.WARNING || 0], INFO: ['Info', view.counts.INFO || 0] };
    document.querySelectorAll('[data-filter]').forEach((chip) => {
      const pair = chipText[chip.dataset.filter];
      chip.textContent = pair[0] + ' · ' + pair[1].toLocaleString('en-GB');
    });
    setFilter('ALL');
    byId('rsCap').textContent = view.findings_total > view.findings.length
      ? 'Showing the first ' + view.findings.length.toLocaleString('en-GB') + ' of ' + view.findings_total.toLocaleString('en-GB') + '. The full list is in the report files.'
      : '';
    byId('rsOutput').textContent = (status.messages || []).join('\n');
    byId('rsDetails').open = false;
    show('results');
  }

  function renderCauses(causes) {
    const box = byId('rsCauses');
    box.replaceChildren();
    byId('rsCausesBlock').hidden = causes.length === 0;
    causes.forEach((c) => {
      const card = el('article', 'cause');
      const top = el('div', 'cause-top');
      top.append(el('span', 'pill ' + SEVERITY[c.severity][1], SEVERITY[c.severity][0]), el('span', 'cause-code', c.code));
      const files = el('ul', 'cause-files');
      c.paths.forEach((p) => files.append(el('li', null, p)));
      if (c.more) { files.append(el('li', null, 'and ' + c.more.toLocaleString('en-GB') + ' more (see the report)')); }
      card.append(top, el('h3', 'cause-title', c.title), el('p', 'cause-summary', c.summary));
      if (c.paths.length) { card.append(el('span', 'eyebrow', c.paths.length + c.more === 1 ? 'Affected file' : 'Affected files'), files); }
      card.append(el('span', 'cause-note', 'A likely explanation, not a verdict.'));
      box.append(card);
    });
  }

  function setFilter(filter) {
    state.filter = filter;
    document.querySelectorAll('[data-filter]').forEach((chip) => chip.setAttribute('aria-pressed', String(chip.dataset.filter === filter)));
    const rows = state.result.findings.filter((r) => filter === 'ALL' || r.severity === filter);
    const body = byId('rsRows');
    body.replaceChildren();
    rows.forEach((r) => {
      const tr = el('tr');
      const sev = el('td');
      sev.append(el('span', 'pill ' + (SEVERITY[r.severity] || ['', ''])[1], (SEVERITY[r.severity] || [r.severity])[0]));
      const what = el('td');
      const box = el('div', 'what');
      box.append(el('span', null, r.title));
      if (r.detail) { box.append(el('span', 'detail', r.detail)); }
      what.append(box);
      tr.append(sev, what, el('td', 'file', r.path || '—'), el('td', 'code', r.code));
      body.append(tr);
    });
    byId('rsEmpty').hidden = rows.length > 0;
  }

  function notCheckedReason(status) {
    if (status.alerts) {
      return 'delivery-ops-hub couldn’t run the check. Its own explanation is below. A missing webhook secret or a settings problem are the usual reasons.';
    }
    return 'The checking tool stopped before it could verify anything. Its own explanation is below.';
  }

  function showNotChecked(reason, messages) {
    byId('ncReason').textContent = reason;
    const lines = (messages || []).slice(-60);
    byId('ncOutput').textContent = lines.join('\n');
    byId('ncSaidBlock').hidden = lines.length === 0;
    show('notchecked');
  }

  function checkAnother() {
    state.folder = null;
    state.manifest = null;
    byId('folderError').textContent = '';
    byId('manifestError').textContent = '';
    renderCards();
    show('start');
  }

  // --- Settings ----------------------------------------------------------------------------------------

  const ALERTS = { set_up: ['Set up', 'pill-ok'], needs_secret: ['Needs the webhook secret', 'pill-warn'], not_set_up: ['Not set up', ''] };
  const AI = { set_up: ['Set up', 'pill-ok'], no_key: ['Set up, no AI key', 'pill-warn'], not_set_up: ['Not set up', ''] };

  function setPill(id, pair) {
    const pill = byId(id);
    pill.textContent = pair[0];
    pill.className = 'pill ' + pair[1];
  }

  async function loadSettings() {
    renderSettings(await api().get_settings());
  }

  function renderSettings(view) {
    state.view = view;
    setPill('alertsStatus', ALERTS[view.status.alerts]);
    setPill('aiStatus', AI[view.status.ai]);
    byId('reportsInUse').textContent = view.reports_in_use;
    byId('reportsInUseWhy').textContent = view.values.ops_hub_path
      ? ' (delivery-ops-hub’s reports folder, because alerts are set up).' : '.';
    FIELDS.forEach((f) => { byId('f-' + f).value = view.values[f] || ''; });
    SECRETS.forEach((s) => {
      byId(s + '-saved').hidden = !view.secrets[s];
      byId(s + '-edit').hidden = !!view.secrets[s];
    });
    const warning = byId('settingsWarning');
    warning.textContent = view.warning || '';
    warning.hidden = !view.warning;
    clearErrors();
  }

  function clearErrors() {
    document.querySelectorAll('.field').forEach((f) => f.classList.remove('has-error'));
    document.querySelectorAll('.field-error').forEach((e) => { e.textContent = ''; });
  }

  function showError(field, message) {
    if (!field) { toast(message); return; }
    setMode('advanced');
    const box = byId('e-' + field);
    if (box) {
      box.textContent = message;
      box.closest('.field').classList.add('has-error');
    } else {
      toast(message);
    }
  }

  function setMode(mode) {
    const advanced = mode === 'advanced';
    byId('standardView').hidden = advanced;
    byId('advancedView').hidden = !advanced;
    byId('modeStandard').setAttribute('aria-pressed', String(!advanced));
    byId('modeAdvanced').setAttribute('aria-pressed', String(advanced));
    byId('modeHint').textContent = advanced ? 'Where the connected tools live on this computer.' : 'Which tools Delivery Desk works with.';
  }

  async function saveSettings() {
    const values = {};
    FIELDS.forEach((f) => { values[f] = byId('f-' + f).value; });
    clearErrors();
    const result = await api().save_settings(values);
    if (!result.ok) { showError(result.field, result.error); return; }
    renderSettings(result);
    byId('savedNote').textContent = 'Saved.';
    setTimeout(() => { byId('savedNote').textContent = ''; }, 2400);
  }

  async function saveSecret(name) {
    const input = byId('s-' + name);
    const value = input.value;
    input.value = '';                                       // never left sitting in the page
    const result = await api().save_secret(name, value);
    if (!result.ok) { showError(name, result.error); return; }
    renderSettings(result);
    toast('Saved in Windows Credential Manager.');
  }

  async function removeSecret(name) {
    const result = await api().remove_secret(name);
    if (!result.ok) { showError(name, result.error); return; }
    renderSettings(result);
    toast('Removed from Windows Credential Manager.');
  }

  // --- Wiring ---------------------------------------------------------------------------------------

  function init() {
    document.querySelectorAll('.nav-link').forEach((b) => b.addEventListener('click', () => show(b.dataset.screen)));
    byId('chooseFolder').addEventListener('click', async () => accept('folder', await api().choose_folder()));
    byId('changeFolder').addEventListener('click', async () => accept('folder', await api().choose_folder()));
    byId('chooseManifest').addEventListener('click', async () => accept('manifest', await api().choose_manifest()));
    byId('changeManifest').addEventListener('click', async () => accept('manifest', await api().choose_manifest()));
    byId('checkButton').addEventListener('click', startCheck);
    byId('stopButton').addEventListener('click', stopCheck);
    document.querySelectorAll('[data-again]').forEach((b) => b.addEventListener('click', checkAnother));
    document.querySelectorAll('[data-show-folder]').forEach((b) => b.addEventListener('click', async () => {
      const opened = await api().show_report_folder(state.result.report_id);
      if (!opened.ok) { toast(opened.error); }
    }));
    document.querySelectorAll('[data-filter]').forEach((chip) => chip.addEventListener('click', () => setFilter(chip.dataset.filter)));
    byId('startNote').addEventListener('click', () => toast('The incident note screen arrives in the next part of the build.'));
    byId('ncBack').addEventListener('click', () => show('start'));
    byId('ncSettings').addEventListener('click', () => show('settings'));
    watchDragging(byId('folderCard'));
    watchDragging(byId('manifestCard'));

    byId('modeStandard').addEventListener('click', () => setMode('standard'));
    byId('modeAdvanced').addEventListener('click', () => setMode('advanced'));
    byId('saveSettings').addEventListener('click', saveSettings);
    document.querySelectorAll('[data-browse]').forEach((b) => b.addEventListener('click', async () => {
      const path = await api().choose_path(b.dataset.kind);
      if (path) { byId('f-' + b.dataset.browse).value = path; }
    }));
    document.querySelectorAll('[data-save-secret]').forEach((b) => b.addEventListener('click', () => saveSecret(b.dataset.saveSecret)));
    document.querySelectorAll('[data-remove]').forEach((b) => b.addEventListener('click', () => removeSecret(b.dataset.remove)));
    document.querySelectorAll('[data-replace]').forEach((b) => b.addEventListener('click', () => {
      byId(b.dataset.replace + '-saved').hidden = true;
      byId(b.dataset.replace + '-edit').hidden = false;
      byId('s-' + b.dataset.replace).focus();
    }));
    renderCards();
  }

  // Called by Python after something is dropped on a card (only Python learns the real location).
  window.app = { dropped: accept, show: show, state: state };
  window.addEventListener('pywebviewready', init);
})();
