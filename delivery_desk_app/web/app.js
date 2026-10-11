// Delivery Desk: the page's behaviour. It shows things and asks the bridge (Python) to do things.
// Rule: anything that came from a delivery or from the computer goes into the page with
// textContent, never as HTML, so a file name that looks like code is shown, never run.
'use strict';

(function () {
  const state = { folder: null, manifest: null, view: null };
  const byId = (id) => document.getElementById(id);
  const api = () => window.pywebview.api;
  const plural = (n, one, many) => n.toLocaleString('en-GB') + ' ' + (n === 1 ? one : many);
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
    byId('checkButton').addEventListener('click', () => toast('Checking arrives in the next part of the build.'));
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
  window.app = { dropped: accept, show: show };
  window.addEventListener('pywebviewready', init);
})();
