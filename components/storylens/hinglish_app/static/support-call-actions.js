(() => {
  const tools = {
    clean: 'Smart Clean', script: 'Smart Edit', captions: 'Auto Captions',
    soundLibrary: 'Sounds', matchCut: 'Match Cut Finder', introCreate: 'Intro Create',
    reelRecreate: 'Reel Recreate', referenceReel: 'Reference Reel', broll: 'Add B-roll',
    visuals: 'Smart Visuals', zoom: 'Smart Zoom', sound: 'Sound Design',
    eyecontact: 'Eye Contact', shorts: 'Long to Shorts', motion: 'Motion Graphics',
    gaming: 'Gaming Highlights', thumbnail: 'Thumbnail', aivideo: 'AI Video',
    cinematic: 'Cinematic Footage', slowMotion: 'Selective Slow Motion', beats: 'Beat Studio',
    downloader: 'Downloader', photos: 'Photo Collector', cricketDesk: 'Cricket Desk',
    gamingDesk: 'Gaming Desk', callQA: 'Call QA', editorLink: 'Editor Handoff',
    voiceover: 'Voice Clone', colorGrade: 'Color Grade', templateImport: 'Import Template',
    templateAligner: 'Template Aligner', templateText: 'Template Text', copyPaste: 'Copy Paste',
    imageDownload: 'Image Downloader', presetLibrary: 'Template Library',
    animationPresets: 'Animation Presets', importantCaptions: 'Important words',
    nativeCaptions: '3D captions', textEffects: 'Cinematic captions',
  };
  const aliases = new Map([['aiimage', 'thumbnail'], ['effectsLibrary', 'presetLibrary']]);
  const captionTabs = new Map([
    ['importantCaptions', '#autoCaptionPanel [data-extra="important"]'],
    ['nativeCaptions', '#autoCaptionPanel [data-family="3d1"]'],
    ['textEffects', '#autoCaptionPanel [data-extra="cinematic"]'],
  ]);
  const mainInputs = new Set(['clean', 'script', 'broll', 'visuals', 'zoom', 'sound',
    'eyecontact', 'shorts', 'motion', 'gaming', 'aivideo']);
  const timelineInputs = new Set(['clean', 'script', 'visuals', 'zoom', 'eyecontact', 'motion', 'aivideo']);
  const embeddedInputs = new Map([
    ['cinematic', { input: 'sourceFolder', upload: 'videoFiles', run: 'runTool', error: 'toolError' }],
    ['matchCut', { input: 'folders', upload: 'files', run: 'run', error: 'toolError' }],
    ['slowMotion', { input: 'folder', upload: 'files', submit: 'scan', error: 'toolError' }],
    ['importantCaptions', { input: 'source', run: 'transcribe' }],
  ]);
  const standalone = {
    aiAgents: ['AI Agents', '/ai-agents.html'],
    finance: ['Finance', '/finance.html'],
    analytics: ['Analytics', '/creator-analytics.html'],
    workflow: ['Workflow', '/workflow.html'],
    activation: ['Storylens activation', '/activation.html'],
    chromePublisher: ['Chrome Publisher', '/chrome.html'],
    stockBrowser: ['Stock Browser', '/stock-browser.html'],
    documentaryIntro: ['Documentary Intro', '/documentary-intro.html'],
    nativeCuration: ['Native Curation', '/native-curation.html'],
    cinematicReels: ['Cinematic Reels', '/cinematic.html'],
  };
  const overlays = new Map();
  let prepared = null;
  let sidebar = '';
  const headerActions = new Map([
    ['chats', { type: 'open_tool', tool: 'chatHistory' }],
    ['open chat history', { type: 'open_tool', tool: 'chatHistory' }],
    ['support', { type: 'open_tool', tool: 'support' }],
    ['prepare and post', { type: 'open_publishing' }],
    ['publishing studio', { type: 'open_publishing' }],
    ['finance', { type: 'open_tool', tool: 'finance' }],
    ['ai agents', { type: 'open_tool', tool: 'aiAgents' }],
    ['voice assistant', { type: 'open_tool', tool: 'storylensCall' }],
    ['ask the editor', { type: 'open_tool', tool: 'assistant' }],
    ['scheduled posts', { type: 'open_schedule' }],
    ['profile', { type: 'open_tool', tool: 'profiles' }],
    ['creator profiles', { type: 'open_tool', tool: 'profiles' }],
    ['creator profile settings', { type: 'open_tool', tool: 'profiles' }],
  ]);

  function modalFor(doc) {
    return [...doc.querySelectorAll('dialog:modal')].at(-1);
  }

  function topDocument(doc = document) {
    const modal = modalFor(doc);
    const frame = modal?.matches('.storylens-voice-workspace') && modal.querySelector('iframe');
    return frame?.contentDocument ? topDocument(frame.contentDocument) : doc;
  }

  function closeOtherWorkspaces(key) {
    for (const [name, view] of overlays) if (name !== key && view.dialog.open) view.dialog.close();
    for (const modal of document.querySelectorAll('.scheduled-dialog[open], .profile-dialog[open], .chat-transcript[open]')) {
      modal.close();
    }
  }

  window.storylensVoiceTool = () => {
    const doc = topDocument();
    if (doc.querySelector('.scheduled-dialog[open]')) return 'scheduledPosts';
    if (doc.querySelector('.profile-dialog[open]')) return 'profiles';
    if (doc.querySelector('.chat-transcript[open]')) return 'chatHistory';
    const route = Object.entries(standalone).find(([, [, path]]) => path === doc.location.pathname);
    if (route) return route[0];
    if (doc.location.pathname === '/prepare-post.html') return 'preparePost';
    if (sidebar === 'chatHistory' && doc.body.classList.contains('chat-history-open')) return sidebar;
    if (sidebar === 'assistant' && doc.body.classList.contains('assistant-open')) return sidebar;
    return '';
  };

  function normalizedTool(value) {
    const tool = aliases.get(value) || value;
    if (typeof tool !== 'string' || !Object.hasOwn(tools, tool)) {
      throw new Error('That Storylens tool is unavailable.');
    }
    return tool;
  }

  function reveal(node) {
    node?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    if (node && !node.matches('button,input,textarea,a[href]') && !node.hasAttribute('tabindex')) {
      node.tabIndex = -1;
    }
    node?.focus({ preventScroll: true });
  }

  async function waitFor(read, message, signal) {
    for (let attempt = 0; attempt < 80; attempt += 1) {
      signal?.throwIfAborted();
      const value = read();
      if (value) return value;
      await new Promise(resolve => setTimeout(resolve, 50));
    }
    throw new Error(message);
  }

  function overlay(key, title, href) {
    closeOtherWorkspaces(key);
    let view = overlays.get(key);
    if (!view) {
      const dialog = document.createElement('dialog');
      dialog.setAttribute('aria-label', title);
      dialog.className = 'storylens-voice-workspace';
      dialog.style.cssText = 'box-sizing:border-box;width:min(1400px,calc(100vw - 28px));max-width:none;height:calc(100dvh - 28px);max-height:none;padding:0;border:1px solid #405057;border-radius:13px;background:#13191d;color:#eef4f5;overflow:hidden';
      const header = document.createElement('header');
      header.style.cssText = 'height:46px;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:0 14px;border-bottom:1px solid #334349';
      const heading = document.createElement('b');
      heading.textContent = title;
      const close = document.createElement('button');
      close.type = 'button';
      close.textContent = 'Close';
      close.onclick = () => dialog.close();
      const frame = document.createElement('iframe');
      frame.title = title;
      frame.src = href;
      frame.style.cssText = 'display:block;width:100%;height:calc(100% - 46px);border:0';
      header.append(heading, close);
      dialog.append(header, frame);
      document.body.append(dialog);
      view = { dialog, frame };
      overlays.set(key, view);
    }
    if (!view.dialog.open) {
      if (view.frame.contentDocument && view.frame.contentDocument.location.href !== new URL(href, location.href).href) {
        view.frame.src = href;
      }
      view.dialog.showModal();
    }
    return view.frame;
  }

  async function openStandalone(key, signal) {
    signal?.throwIfAborted();
    const [name, path] = standalone[key];
    const frame = overlay(key, name, path);
    await waitFor(() => frame.contentDocument?.location.pathname === path &&
      frame.contentDocument.readyState === 'complete', name + ' did not finish opening.', signal);
    return 'Opened ' + name + '.';
  }

  async function workspace(signal) {
    signal?.throwIfAborted();
    if (document.querySelector('.panel #inputPath')) return document;
    const frame = overlay('editor', 'Storylens editor', '/');
    return waitFor(() => {
      const doc = frame.contentDocument;
      return doc?.defaultView?.editorAssist && doc.querySelector('.panel #inputPath') ? doc : null;
    }, 'Storylens editor did not open. Try opening it from the main toolbar.', signal);
  }

  function resetToolSearch(doc) {
    const search = doc.getElementById('toolSearch');
    if (search?.value) {
      search.value = '';
      search.dispatchEvent(new doc.defaultView.Event('input', { bubbles: true }));
    }
  }

  async function openTool(doc, tool, signal) {
    signal?.throwIfAborted();
    // A prior Publishing/standalone modal otherwise hides the newly opened tool.
    for (const view of overlays.values()) {
      if (view.dialog.open && view.frame.contentDocument !== doc) view.dialog.close();
    }
    doc.querySelectorAll('.scheduled-dialog[open]').forEach(dialog => dialog.close());
    resetToolSearch(doc);
    sidebar = '';
    const mode = captionTabs.has(tool) ? 'captions' : tool;
    const button = doc.querySelector('button.mode[data-mode="' + mode + '"]');
    if (!button || button.disabled) throw new Error(tools[tool] + ' is unavailable here.');
    button.click();
    const panel = doc.querySelector('.panel');
    if (panel?.dataset.mode !== mode) throw new Error(tools[tool] + ' did not open.');
    if (captionTabs.has(tool)) {
      const tab = doc.querySelector(captionTabs.get(tool));
      if (!tab) throw new Error(tools[tool] + ' is unavailable here.');
      tab.click();
      if (tab.getAttribute('aria-pressed') !== 'true') {
        throw new Error('Finish the current caption job before changing the caption tab.');
      }
      reveal(tab);
    } else {
      reveal(doc.getElementById('modeTitle'));
    }
    return panel;
  }

  function source(action, tool) {
    const path = action.path;
    const kind = action.path_kind;
    if (typeof path !== 'string' || !/^[a-z]:[\\/]/i.test(path) || /[\r\n\u0000]/.test(path) ||
        !['file', 'folder'].includes(kind)) {
      throw new Error('Use a verified local video or folder for this tool.');
    }
    if (tool === 'importantCaptions' && kind !== 'file') {
      throw new Error('Important words needs one video file.');
    }
    if (embeddedInputs.has(tool) && tool !== 'importantCaptions' && kind !== 'folder') {
      throw new Error(tools[tool] + ' needs a footage folder for voice selection.');
    }
    if (kind === 'file' && !/\.(mp4|mov|mxf|mkv|avi|mts|m2ts|webm)$/i.test(path) &&
        !(timelineInputs.has(tool) && /\.xml$/i.test(path))) {
      throw new Error('Choose a supported video file for ' + tools[tool] + '.');
    }
    if (tool === 'shorts' && kind === 'file' && !/\.(mp4|mov)$/i.test(path)) {
      throw new Error('Long to Shorts needs an MP4 or MOV video.');
    }
    return path;
  }

  function applyInput(input, value) {
    input.value = value;
    input.dispatchEvent(new input.ownerDocument.defaultView.Event('input', { bubbles: true }));
  }

  async function prepareMain(doc, action, tool, path, signal) {
    const run = doc.getElementById('run');
    const win = doc.defaultView;
    if (run?.disabled || win.editorAssist?.busy() || win.assistantBusy) {
      throw new Error('Finish the current edit before choosing another source.');
    }
    if (!action.reuse) await openTool(doc, tool, signal);
    signal?.throwIfAborted();
    const field = doc.getElementById('inputPath');
    if (!field || !run) throw new Error('The source field is unavailable.');
    const resolveTimeline = doc.getElementById('useResolve');
    if (action.reuse) {
      if (doc.querySelector('.panel')?.dataset.mode !== tool || field.value !== path || resolveTimeline?.checked) {
        throw new Error('The tool or source changed. Select the source again before running.');
      }
    } else {
      applyInput(field, path);
      if (resolveTimeline?.checked) resolveTimeline.checked = false;
    }
    if (!action.run) {
      reveal(field);
      return 'Selected the source in ' + tools[tool] + '.';
    }
    if (tool === 'script' && !doc.getElementById('script')?.value.trim()) {
      reveal(doc.getElementById('script'));
      if (action.reuse) throw new Error('Add your script before running Smart Edit.');
      return 'Selected the source in Smart Edit. Add your script before running it.';
    }
    if (tool === 'broll') {
      run.click();
      if (action.reuse) throw new Error('Choose a B-roll format in the tool to continue.');
      return 'Selected the source in Add B-roll. Choose its format to continue.';
    }
    if (typeof run.onclick !== 'function') throw new Error('The Run button is unavailable.');
    const job = await run.onclick();
    if (!job?.id) throw new Error('The source is selected. Check the tool’s message before running it again.');
    return 'Started ' + tools[tool] + '.';
  }

  async function prepareEmbedded(doc, action, tool, path, signal) {
    if (!action.reuse) await openTool(doc, tool, signal);
    else if (doc.querySelector('.panel')?.dataset.mode !== (captionTabs.has(tool) ? 'captions' : tool)) {
      throw new Error('The tool changed. Select the source again before running.');
    }
    const spec = embeddedInputs.get(tool);
    const frame = tool === 'importantCaptions'
      ? doc.querySelector('#autoCaptionPanel .caption-extra iframe')
      : doc.querySelector('#embeddedTools iframe[data-tool="' + tool + '"]');
    const localDoc = await waitFor(() => {
      const current = frame?.contentDocument;
      const run = spec.run && current?.getElementById(spec.run);
      const form = spec.submit && current?.getElementById(spec.submit);
      return current?.getElementById(spec.input) && (run?.form?.onsubmit || form?.onsubmit) ? current : null;
    }, tools[tool] + ' did not finish opening.', signal);
    signal?.throwIfAborted();
    const field = localDoc.getElementById(spec.input);
    const run = spec.run ? localDoc.getElementById(spec.run)
      : localDoc.getElementById(spec.submit).querySelector('button[type="submit"]');
    if (!run || run.disabled || field.disabled) throw new Error('Finish the current job in ' + tools[tool] + '.');
    if (action.reuse && (field.value !== path || (spec.upload && localDoc.getElementById(spec.upload)?.files.length))) {
      throw new Error('The source changed. Select it again before running.');
    }
    if (!action.reuse) {
      if (spec.upload) {
        const upload = localDoc.getElementById(spec.upload);
        upload.value = '';
        upload.dispatchEvent(new localDoc.defaultView.Event('change', { bubbles: true }));
      }
      applyInput(field, path);
    }
    reveal(field);
    if (!action.run) return 'Selected the source in ' + tools[tool] + '.';
    run.click();
    const issue = spec.error && localDoc.getElementById(spec.error);
    if (issue && !issue.hidden && issue.textContent.trim()) throw new Error(issue.textContent.trim());
    return 'Pressed ' + run.textContent.trim() + ' in ' + tools[tool] + '. Check its progress there.';
  }

  const settingName = value => String(value || '').normalize('NFKC').toLowerCase()
    .replace(/[^\p{L}\p{M}\p{N}]+/gu, ' ').trim();
  const numberWords = Object.fromEntries(
    ['zero','one','two','three','four','five','six','seven','eight','nine','ten',
     'eleven','twelve','thirteen','fourteen','fifteen','sixteen','seventeen','eighteen','nineteen','twenty']
      .map((word, index) => [word, String(index)])
  );
  const settingValue = value => {
    const key = settingName(value);
    return numberWords[key] ?? key;
  };

  function present(node) {
    if (node.closest('[hidden], .hidden, [aria-hidden="true"]')) return false;
    for (let item = node; item; item = item.parentElement) {
      const style = item.ownerDocument.defaultView.getComputedStyle(item);
      if (style.display === 'none' || style.visibility === 'hidden') return false;
    }
    return node.getClientRects().length > 0 || !!node.closest('details:not([open])')?.getClientRects().length;
  }

  function available(node) {
    return !node.disabled && !node.readOnly && !node.matches(':disabled') &&
      node.getAttribute('aria-disabled') !== 'true' && present(node);
  }

  function labelText(node) {
    const clone = node.cloneNode(true);
    clone.querySelectorAll('input, select, textarea, button, svg, small, [hidden], [aria-hidden="true"]').forEach(child => child.remove());
    return clone.textContent.trim();
  }

  function labels(field) {
    const labelledBy = field.getAttribute('aria-labelledby')?.split(/\s+/)
      .map(id => field.ownerDocument.getElementById(id)?.textContent.trim()).filter(Boolean).join(' ');
    return [field.getAttribute('aria-label'), labelledBy, ...Array.from(field.labels || [], labelText)]
      .filter(Boolean);
  }

  function matchScore(names, term) {
    const key = settingValue(term);
    if (!key) return 0;
    return Math.max(0, ...names.map(value => {
      const name = settingValue(value);
      if (name === key) return 2;
      return key.length >= 3 && name.startsWith(key + ' ') ? 1 : 0;
    }));
  }

  function optionFor(field, value) {
    if (!value || field.multiple) return null;
    const options = Array.from(field.options).filter(option => option.value && !option.disabled &&
      !option.hidden && !option.closest('optgroup:disabled'));
    const best = Math.max(0, ...options.map(option => matchScore([option.label, option.value], value)));
    const matches = options.filter(option => best && matchScore([option.label, option.value], value) === best);
    return matches.length === 1 ? matches[0] : null;
  }

  function settingScopes(doc) {
    const modal = modalFor(doc);
    if (modal && !modal.matches('.storylens-voice-workspace')) return [modal];
    if (doc.querySelector('#connectionPanel')) return [doc.querySelector('main')];
    if (sidebar && doc.body.classList.contains(sidebar === 'chatHistory' ? 'chat-history-open' : 'assistant-open')) {
      return [doc.querySelector(sidebar === 'chatHistory' ? '.chat-history' : '.assistant-panel')].filter(Boolean);
    }
    const panel = doc.querySelector('.panel[data-mode]');
    if (!panel) return [doc.querySelector('main') || doc.body];
    const inner = Array.from(panel.querySelectorAll('iframe')).filter(available).flatMap(frame => {
      try {
        return frame.contentDocument?.querySelector('main') || frame.contentDocument?.body || [];
      } catch (_) {
        return [];
      }
    });
    return [panel, ...inner];
  }

  function currentSettingDocument() {
    return topDocument();
  }

  const buttonSelector = 'button, [role="button"], [role="tab"], summary, input[type="button"], input[type="submit"], input[type="reset"], input[type="checkbox"], input[type="radio"], a[href], a[id][download]';
  const buttonKey = value => settingName(value?.replace(/\s*·\s*\d+\s*$/, ''));

  function buttonScopes(doc) {
    const modal = modalFor(doc);
    if (modal) {
      const child = modal.matches('.storylens-voice-workspace') && modal.querySelector('iframe')?.contentDocument;
      return child ? [...buttonScopes(child), modal] : [modal];
    }
    const main = doc.querySelector('.panel[data-mode]');
    const scopes = main ? settingScopes(doc) : [];
    const context = scopes[0] !== main ? scopes[0] : null;
    return main ? [context, doc.querySelector('.topbar'), ...scopes.slice(1), main,
      doc.querySelector('.modes'), doc.querySelector('.assistant-panel'), doc.querySelector('.chat-history'),
      doc.querySelector('#storylens-call-panel[open]'), doc.querySelector('.support-call-dock')] : [doc.body];
  }

  function namedButtons(doc, scopes = buttonScopes(doc)) {
    const buttons = [...new Set(scopes.filter(Boolean)
      .flatMap(scope => Array.from(scope.querySelectorAll(buttonSelector))))];
    return buttons.filter(present).flatMap(field => {
      if (field.matches('a[href]') && !field.matches('[download], .topbar a, .publishing-link, .connection-action, .profile-dialog a') &&
          !['/finance.html', '/ai-agents.html', '/creator-analytics.html', '/prepare-post.html'].includes(field.ownerDocument.location.pathname)) return [];

      const label = field.matches('button.mode') ? field.querySelector('b') :
        field.id === 'run' ? field.querySelector('#runText') : null;
      let visible = (field.matches('#outputSettings > summary') ? 'Output settings' :
        labelText(label || field)).replace(/\s+/g, ' ');
      const caption = field.matches('button[data-style]') &&
        visible.match(/Caption \d+\s*-\s*.+|Typography \d+|Kinetic Documentary|Documentary Outline|Documentary Echo|Cinematic Script Mix|Cinematic Clean Reveal/);
      if (caption) visible = caption[0];
      if (field.dataset.gradeMode) visible = field.dataset.gradeMode === 'realfilm' ? 'Color Grade 1' : 'Color Grade 2';
      if (field.matches('.chat-history-item')) visible = field.querySelector('strong')?.textContent || visible;
      if (field.closest('.scheduled-platforms, .scheduled-channels') || field.matches('.scheduled-toggle')) {
        visible = visible.replace(/\s*·\s*\d+\s*$/, '');
      }
      if (field.matches('.profile-trigger')) visible = 'Profile';
      if (field.matches('.chat-history-toggle')) visible = 'Chats';
      if (field.matches('[data-call-expand], [data-call-restore], [data-call-dock-pause], [data-call-close]')) {
        visible = field.getAttribute('aria-label');
      }
      const qualified = field.dataset.voiceLabel;
      const names = [...new Set([qualified, visible.replace(/^←\s*/, ''), ...labels(field), field.title, field.value && field.tagName === 'INPUT' && field.value]
        .filter(value => typeof value === 'string' && buttonKey(value)))];
      return names.length ? [{ field, names }] : [];
    });
  }

  const buttonFamilies = [
    ['button.caption-card, button[data-reference], button[data-style]', 'caption-style'],
    ['button[data-family]', 'caption-family'],
    ['button[data-variant]', 'caption-variant'],
    ['button[data-draft]', 'intro-draft'],
    ['.chat-history-item', 'saved-chat'],
    ['.scheduled-card', 'scheduled-item'],
    ['.call-row', 'call-qa-entry'],
    ['.time-button', 'call-evidence'],
    ['#assistantPending button[aria-label^="Remove "]', 'attachment-remove'],
    ['#presetSection .workspace-tab', 'preset-category'],
    ['.quick-motion-card .effect-preview', 'motion-preset'],
    ['.documentary-card .effect-preview', 'template-pack'],
    ['#presetSection .effect-scene .effect-preview', 'template-scene'],
    ['.preset-external-row button', 'template-file'],
  ];

  window.storylensVoiceControls = () => {
    const rows = [];
    let encoded = '';
    for (const { field, names } of namedButtons(document)) {
      const name = names[0].slice(0, 90);
      const family = buttonFamilies.find(([selector]) => field.matches(selector))?.[1];
      rows.push(family ? [name, available(field), family] : [name, available(field)]);
      const candidate = btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify(rows))));
      if (candidate.length > 4000 || rows.length > 100) break;
      encoded = candidate;
    }
    return encoded;
  };

  window.storylensVoiceFields = () => {
    const rows = [];
    let encoded = '';
    const scopes = settingScopes(currentSettingDocument());
    if (typeof document !== 'undefined') scopes.push(document.querySelector('#storylens-call-panel[open]'));
    const fields = [...new Set(scopes.filter(Boolean)
      .flatMap(scope => Array.from(scope.querySelectorAll('select'))))];
    for (const field of fields) {
      if (!present(field) || field.multiple) continue;
      const name = labels(field)[0];
      if (!name || /credential|token|password|api key|secret|connection code/i.test(name)) continue;
      const options = Array.from(field.options).filter(option => !option.hidden && option.value)
        .slice(0, 80).map(option => ({ value: option.value.slice(0, 120), label: option.label.slice(0, 120),
          disabled: !!(option.disabled || option.closest('optgroup:disabled')) }));
      const row = { id: field.id.slice(0, 100), label: name.slice(0, 120), value: field.value.slice(0, 120),
        disabled: !available(field), options };
      const candidate = btoa(String.fromCharCode(...new TextEncoder().encode(JSON.stringify([...rows, row]))));
      if (candidate.length > 12000) continue;
      rows.push(row);
      encoded = candidate;
      if (rows.length >= 40) break;
    }
    return encoded;
  };

  function requiresReview(field, name) {
    const command = [name, field.dataset.action, field.id].map(settingName);
    if (field.matches('#connections, [data-tab], [data-platform], .scheduled-toggle')) return false;
    return field.matches('.scheduled-dialog [data-action], [data-voice-review]') || command.some(label =>
      /^(?:post now|publish now|publish|schedule|postclips|scheduleclips|longpost|longschedule|cancel schedule|cancel unstarted post|delete|remove local data|remove recording|send|send reply|approve reply|run replies now|enable chrome replies|connect|reconnect|disconnect|read instagram in chrome|open google|sign in|activate|purchase|pay)(?: |$)/.test(label)
    );
  }

  async function chooseLocalSource(field, signal) {
    const doc = field.ownerDocument;
    const editor = doc.defaultView.editorAssist;
    if (!editor || editor.busy() || doc.defaultView.assistantBusy) throw new Error('Finish the current edit before choosing another source.');
    const mode = doc.querySelector('.panel')?.dataset.mode;
    const kind = field.id === 'browseFolder' ? 'folder' : 'videos';
    const result = await doc.defaultView.storylensFetch('/api/pick?kind=' + kind, {
      signal, headers: { 'X-Hinglish-Token': doc.documentElement.dataset.token },
    });
    const data = await doc.defaultView.storylensResponse(result);
    signal?.throwIfAborted();
    if (!result.ok) throw new Error(data.error || 'The Windows picker could not open.');
    if (!data.path) return 'Selection cancelled; the previous source is unchanged.';
    if (editor.busy() || doc.defaultView.assistantBusy || doc.querySelector('.panel')?.dataset.mode !== mode) {
      throw new Error('The tool changed while selecting files. Choose the source again in the intended tool.');
    }
    if (kind === 'videos') {
      const paths = [...new Set(data.path.split(/\r?\n/).filter(Boolean))];
      if (!paths.length || paths.some(path => !/^[a-z]:[\\/]/i.test(path) || !/\.(mp4|mov|mxf|mkv|avi|mts|m2ts|webm)$/i.test(path))) {
        throw new Error('Choose supported local video files.');
      }
      editor.useSources(paths);
      const display = doc.getElementById('selectedFiles');
      if (display) { display.textContent = paths.map(path => path.split(/[\\/]/).pop()).join(' • '); display.classList.remove('hidden'); }
      reveal(doc.getElementById('inputPath'));
      return 'Selected ' + paths.length + ' video' + (paths.length === 1 ? '.' : 's.');
    }
    if (!/^[a-z]:[\\/]/i.test(data.path)) throw new Error('Choose a local folder.');
    editor.useSources([]);
    applyInput(doc.getElementById('inputPath'), data.path);
    doc.getElementById('selectedFiles')?.classList.add('hidden');
    reveal(doc.getElementById('inputPath'));
    return 'Selected the footage folder.';
  }

  async function pressButton(doc, action, signal) {
    const label = typeof action.label === 'string' && action.label.length <= 160 && buttonKey(action.label);
    if (!label) throw new Error('Say the exact name of the button.');
    let scope = topDocument(doc);
    const active = window.storylensVoiceTool();
    const headers = !action.tool && !modalFor(scope) && scope === doc;
    if ((headers || !action.tool && !namedButtons(scope).some(({ names }) => names.some(name => buttonKey(name) === label))) &&
        (headerActions.has(label) || label === 'analytics')) {
      return window.storylensApplyVoiceAction(headerActions.get(label) || { type: 'open_tool', tool: 'analytics' }, { signal });
    }
    if (action.tool === 'scheduledPosts' && active !== 'scheduledPosts') {
      await window.storylensApplyVoiceAction({ type: 'open_schedule' }, { signal });
      scope = topDocument();
    } else if (action.tool === 'preparePost' && !scope.querySelector('#connectionPanel')) {
      await window.storylensApplyVoiceAction({ type: 'open_publishing' }, { signal });
      scope = topDocument();
    } else if (Object.hasOwn(standalone, action.tool) && active !== action.tool) {
      await openStandalone(action.tool, signal);
      scope = topDocument();
    } else if (['assistant', 'chatHistory', 'profiles'].includes(action.tool) && active !== action.tool) {
      await window.storylensApplyVoiceAction({ type: 'open_tool', tool: action.tool }, { signal });
      scope = topDocument();
    } else if (action.tool && Object.hasOwn(tools, aliases.get(action.tool) || action.tool)) {
      scope = await workspace(signal);
      const tool = normalizedTool(action.tool);
      const current = scope.querySelector('.panel[data-mode]');
      const panel = current?.dataset.mode === tool ? current : await openTool(scope, tool, signal);
      await waitFor(() => {
        const frame = [...panel.querySelectorAll('iframe')].find(present);
        return !frame || frame.contentDocument?.readyState === 'complete' &&
          frame.contentDocument?.location.href !== 'about:blank';
      }, 'That tool opens in a separate service or its controls are still loading.', signal);
    }
    if (scope.location.pathname === '/ai-agents.html') {
      await waitFor(() => scope.querySelector('#agents .card'), 'AI Agents is still loading.', signal);
      const developer = scope.getElementById('developer-agents');
      if (developer?.hidden && [...developer.querySelectorAll('[data-voice-label], button')].some(button =>
        buttonKey(button.dataset.voiceLabel || button.textContent) === label && label !== 'open')) {
        scope.getElementById('developer-toggle').click();
      }
    }
    if (window.storylensVoiceTool() === 'scheduledPosts') {
      const platform = { youtube: 'youtube', instagram: 'instagram', 'failed attempts': 'failed' }[label];
      if (platform) return schedulePlatform(scope, platform, signal);
      if (['cricket', 'gaming', 'other', 'other channels'].includes(label)) {
        await waitFor(() => scope.querySelector('.scheduled-channels button'),
          'The channel filters did not finish loading.', signal);
      }
    }
    if (scope.location.pathname === '/finance.html' && label === 'refresh') {
      return financeCommand(scope, 'refresh', '', signal);
    }
    const voiceScopes = [document.querySelector('#storylens-call-panel[open]'), document.querySelector('.support-call-dock:not([hidden])')];
    const scopes = action.tool === 'storylensCall' ? voiceScopes : [...buttonScopes(scope), ...voiceScopes];
    const rows = namedButtons(scope, scopes);
    const preferred = rows.filter(({ names }) => buttonKey(names[0]) === label);
    const matches = preferred.length ? preferred : rows.filter(({ names }) => names.some(name => buttonKey(name) === label));
    if (matches.length === 1 && matches[0].field.matches('.segmented [data-mode], .segmented [data-profile]') &&
        !available(matches[0].field)) {
      await waitFor(() => available(matches[0].field), matches[0].names[0] + ' is currently disabled.', signal);
    }
    const enabled = matches.filter(({ field }) => available(field));
    if (enabled.length > 1) throw new Error('More than one button is named ' + action.label + '. Open the specific item or panel first.');
    if (!enabled.length) throw new Error(matches.length ? matches[0].names[0] + ' is currently disabled.' :
      'I couldn’t find ' + action.label + ' on this screen. Open its tool or expand the section and try again.');
    const { field, names } = enabled[0];
    if (field.matches('.scheduled-platforms button[data-platform]')) {
      return schedulePlatform(field.ownerDocument, field.dataset.platform, signal);
    }
    if (requiresReview(field, names[0])) throw new Error('Review the current item and press ' + names[0] + ' in Storylens to confirm.');
    if (field.id === 'channelPublish') return window.storylensApplyVoiceAction({ type: 'open_publishing' }, { signal });
    if (field.matches('a[href]')) {
      const target = new URL(field.href);
      if (target.origin === location.origin && ['/', '/index.html'].includes(target.pathname) &&
          field.ownerDocument !== document && !target.search && !target.hash) {
        closeOtherWorkspaces();
        return 'Returned to the StoryLens editor.';
      }
      if (target.origin !== location.origin && !field.target && target.protocol === 'http:' &&
          ['127.0.0.1:4310', '127.0.0.1:43820'].includes(target.host)) {
        field.target = '_blank';
        field.rel = 'noopener noreferrer';
      }
    }
    signal?.throwIfAborted();
    for (let details = field.closest('details:not([open])'); details; details = details.parentElement?.closest('details:not([open])')) {
      if (field.parentElement !== details || field.tagName !== 'SUMMARY') details.open = true;
    }
    if (field.matches('#browse, #browseFolder') && field.ownerDocument.defaultView.editorAssist) {
      return chooseLocalSource(field, signal);
    }
    reveal(field);
    field.click();
    if (field.matches('#connections, #developer-toggle')) {
      const target = field.ownerDocument.getElementById(field.getAttribute('aria-controls'));
      if (target && (field.getAttribute('aria-expanded') === 'true') === target.hidden) {
        throw new Error(names[0] + ' did not change.');
      }
    }
    if (field.matches('.scheduled-channels button, .segmented button[data-profile], .segmented button[data-mode], .channel-cards button, [data-scope]')) {
      const group = field.parentElement;
      await waitFor(() => [...group.querySelectorAll('button[aria-pressed="true"]')].some(button =>
        buttonKey(labelText(button)) === buttonKey(labelText(field))),
      'The requested selection did not change. Check the current screen.', signal);
    }
    if (field.matches('#agents button, #developer-agents button')) {
      const source = field.ownerDocument;
      const opened = () => !source.getElementById('suite')?.hidden || !source.getElementById('comments')?.hidden;
      await waitFor(() => opened() || !field.disabled, names[0] + ' did not open.', signal);
      if (!opened()) throw new Error(source.getElementById('status')?.textContent || names[0] + ' did not open.');
    }
    return 'Pressed ' + names[0] + '.';
  }

  async function schedulePlatform(doc, platform, signal) {
    const names = new Map([['youtube', 'YouTube'], ['instagram', 'Instagram'], ['failed', 'Failed attempts']]);
    if (!names.has(platform)) throw new Error('Choose YouTube, Instagram, or Failed attempts.');
    if (!doc.querySelector('.scheduled-dialog[open]')) {
      const button = await waitFor(() => doc.querySelector('button.scheduled-toggle'), 'Scheduled posts is unavailable here.', signal);
      signal?.throwIfAborted();
      button.click();
    }
    const dialog = doc.querySelector('.scheduled-dialog[open]');
    if (!dialog) throw new Error('Scheduled posts did not open.');
    const selector = '.scheduled-platforms button[data-platform="' + platform + '"]';
    const button = await waitFor(() => dialog.querySelector(selector), 'The platform filters did not finish loading.', signal);
    signal?.throwIfAborted();
    if (button.getAttribute('aria-pressed') !== 'true') button.click();
    const selected = dialog.querySelector(selector);
    if (selected?.getAttribute('aria-pressed') !== 'true') {
      throw new Error(dialog.querySelector('.scheduled-note')?.textContent.trim() || 'Scheduled posts could not switch platforms.');
    }
    reveal(selected);
    return 'Showing ' + names.get(platform) + ' in Scheduled posts.';
  }

  function financeCommand(doc, operation, value, signal) {
    const frame = doc.querySelector('iframe[title="Freelancer Finance"]');
    const origin = 'http://127.0.0.1:43822';
    if (!frame?.contentWindow || new URL(frame.src).origin !== origin) {
      throw new Error('The Finance summary is unavailable.');
    }
    const id = crypto.randomUUID();
    const deadline = AbortSignal.any([AbortSignal.timeout(3500), ...(signal ? [signal] : [])]);
    return new Promise((resolve, reject) => {
      const subscription = new AbortController();
      deadline.addEventListener('abort', () => {
        subscription.abort();
        reject(signal?.reason || new Error('The Finance summary did not respond.'));
      }, { once: true, signal: subscription.signal });
      window.addEventListener('message', event => {
        if (event.origin !== origin || event.source !== frame.contentWindow || event.data?.financeVoiceResult !== id) return;
        subscription.abort();
        if (event.data.ok !== true) return reject(new Error('Choose a month in YYYY-MM format.'));
        resolve(operation === 'refresh' ? 'Refreshing the Finance summary.' : 'Showing Finance for ' + value + '.');
      }, { signal: subscription.signal });
      frame.contentWindow.postMessage({ financeVoice: id, operation, value }, origin);
    });
  }

  async function setControl(doc, action, signal) {
    if (typeof action.label !== 'string' || typeof action.value !== 'string' ||
        action.label.length > 200 || !action.value.trim() || action.value.length > 1200) {
      throw new Error('Say the name of a setting and its new value.');
    }
    const label = settingName(action.label);
    if (doc.location?.pathname === '/finance.html' && label === 'month') {
      return financeCommand(doc, 'month', action.value, signal);
    }
    const fieldId = typeof action.field_id === 'string' && action.field_id.length <= 100 ? action.field_id : '';
    const voicePanel = (action.tool === 'storylensCall' || label === 'voice language') &&
      typeof document !== 'undefined' && document.querySelector('#storylens-call-panel[open]');
    const scopes = voicePanel ? [voicePanel] : settingScopes(doc);
    const matched = [];
    const fields = scopes.flatMap(scope => Array.from(scope.querySelectorAll(
      'select, textarea, input[type="checkbox"], input[type="number"], input[type="range"], input[type="radio"], input[type="text"], input:not([type]), input[type="date"], input[type="time"], input[type="datetime-local"], input[type="color"], input[type="month"], input[type="search"]'
    )));
    for (const field of fields) {
      if (!available(field)) continue;
      // IDs identify a grounded dropdown, never an arbitrary document-wide target.
      if (fieldId && (field.tagName !== 'SELECT' || field.id !== fieldId)) continue;
      const names = labels(field);
      // File paths and credentials keep their existing verified pickers and connections.
      if (!names.length || /(?:path|source|credential|token|password|api key|secret|connection code)/i.test(names.join(' ')) &&
          ['text','textarea'].includes(field.type)) continue;
      if (field.type === 'radio') {
        const legend = field.closest('fieldset')?.querySelector('legend')?.textContent;
        const group = field.closest('[role="radiogroup"]')?.getAttribute('aria-label');
        const score = matchScore([legend, group].filter(Boolean), label);
        if (score && matchScore([...names, field.value], action.value)) matched.push({ field, names: [legend || group], score });
        continue;
      }
      if (label) {
        const score = matchScore(names, label);
        if (score) matched.push({ field, names, score });
      } else if (field.tagName === 'SELECT' && optionFor(field, action.value) &&
                 (!action.from || optionFor(field, action.from)?.selected || optionFor(field, action.value)?.selected)) {
        matched.push({ field, names, score: 1 });
      }
    }
    // Existing segmented groups carry their own active state and normal click handlers.
    for (const scope of fieldId ? [] : scopes) {
      for (const group of scope.querySelectorAll('[role="group"][aria-label], nav[aria-label]')) {
        const name = group.getAttribute('aria-label');
        const aliases = { 'creator channels': ['channel', 'profile', 'creator channel'],
                          'video format': ['format'], 'platforms': ['platform'] };
        const score = matchScore([name, ...(aliases[settingName(name)] || [])], label);
        if (!score) continue;
        for (const field of group.querySelectorAll('button[aria-pressed]')) {
          const label = field.textContent.replace(/\s*·\s*\d+\s*$/, '');
          if (available(field) && matchScore([label], action.value)) matched.push({ field, names: [name], score, group });
        }
      }
    }
    const best = Math.max(0, ...matched.map(result => result.score));
    const choices = matched.filter(result => result.score === best);
    if (choices.length !== 1) {
      throw new Error(choices.length ? 'More than one control matches. Say the exact setting name.' :
        'I couldn’t find that setting on this screen. Open its tool and say the label you see.');
    }
    const { field, names, group } = choices[0];
    if (field.matches?.('[data-voice-review]')) {
      throw new Error('Review and change ' + names[0] + ' directly in StoryLens.');
    }
    const name = names[0];
    signal?.throwIfAborted();
    for (let details = field.closest('details:not([open])'); details; details = details.parentElement?.closest('details:not([open])')) {
      details.open = true;
    }
    let expected;
    let displayValue = action.value;
    let checked = null;
    if (field.tagName === 'SELECT') {
      const option = optionFor(field, action.value);
      if (!option) throw new Error('Choose an available value for ' + name + '.');
      const previous = action.from && optionFor(field, action.from);
      if (previous && !previous.selected && !option.selected) {
        throw new Error(name + ' is currently set to ' + (field.selectedOptions[0]?.label || 'another value') + '.');
      }
      expected = option.value;
      displayValue = option.label;
    } else if (field.tagName === 'BUTTON') {
      if (field.getAttribute('aria-pressed') !== 'true') field.click();
      const notice = group.closest('.scheduled-dialog')?.querySelector('.scheduled-note')?.textContent.trim();
      if (notice?.startsWith('Save your changes')) throw new Error(notice);
      const replacement = await waitFor(() => [...group.querySelectorAll('button[aria-pressed="true"]')].find(button =>
        matchScore([button.textContent.replace(/\s*·\s*\d+\s*$/, '')], action.value)),
        name + ' did not change. Check the current screen.', signal);
      reveal(replacement);
      return 'Selected ' + displayValue + ' for ' + name + '.';
    } else if (field.type === 'checkbox' || field.type === 'radio') {
      const value = settingName(action.value);
      checked = field.type === 'radio' || ['on','yes','true','enabled','checked','चालू','हाँ'].includes(value);
      if (field.type === 'checkbox' && !checked && !['off','no','false','disabled','unchecked','बंद','नहीं'].includes(value)) {
        throw new Error('Say on or off for ' + name + '.');
      }
      if (field.checked !== checked) field.click();
      if (field.checked !== checked) throw new Error(name + ' did not change.');
      displayValue = field.type === 'radio' ? action.value : checked ? 'On' : 'Off';
    } else {
      expected = ['number','range'].includes(field.type) ? (numberWords[settingName(action.value)] ?? action.value.trim()) : action.value;
      if (['number','range'].includes(field.type) && (!/^-?\d+(?:\.\d+)?$/.test(expected) ||
          (field.min !== '' && Number(expected) < Number(field.min)) ||
          (field.max !== '' && Number(expected) > Number(field.max)))) {
        throw new Error('Give a number within the available range for ' + name + '.');
      }
      if (field.maxLength >= 0 && expected.length > field.maxLength) {
        throw new Error(name + ' accepts up to ' + field.maxLength + ' characters.');
      }
      displayValue = expected;
    }
    if (expected !== undefined && field.value !== expected) {
      const previous = field.value;
      field.value = expected;
      if (!field.checkValidity() || (!['number','range'].includes(field.type) && field.value !== expected) ||
          (['number','range'].includes(field.type) && Number(field.value) !== Number(expected))) {
        field.value = previous;
        throw new Error('That value is invalid for ' + name + '.');
      }
      const Event = field.ownerDocument.defaultView.Event;
      field.dispatchEvent(new Event('input', { bubbles: true }));
      field.dispatchEvent(new Event('change', { bubbles: true }));
      if (field.value !== expected && !(['number','range'].includes(field.type) && Number(field.value) === Number(expected))) {
        throw new Error(name + ' did not keep the requested value.');
      }
    }
    reveal(field);
    return 'Set ' + name + ' to ' + displayValue + '.';
  }

  window.storylensApplyVoiceAction = async (action, { signal, callId } = {}) => {
    signal?.throwIfAborted();
    if (!action || typeof action !== 'object' || Array.isArray(action)) {
      throw new Error('Storylens did not receive an action.');
    }
    if (action.type === 'click_button') return pressButton(document, action, signal);
    if (action.type === 'open_tool' && action.tool === 'support') {
      const doc = await workspace(signal);
      const link = doc.querySelector('.topbar a.support-link');
      if (!link) throw new Error('Support is unavailable here.');
      link.click();
      return 'Opened the Support email draft.';
    }
    if (action.type === 'open_tool' && ['assistant', 'chatHistory', 'profiles', 'results', 'storylensCall'].includes(action.tool)) {
      if (action.tool === 'results') return window.storylensApplyVoiceAction({ type: 'navigate', target: 'result' }, { signal, callId });
      if (action.tool === 'storylensCall') {
        const restore = document.querySelector('.support-call-dock:not([hidden]) [data-call-restore]');
        restore?.click();
        reveal(document.querySelector('#storylens-call-panel[open]'));
        return 'Opened Cortana AI.';
      }
      const doc = await workspace(signal);
      if (doc === document) closeOtherWorkspaces();
      sidebar = action.tool === 'profiles' ? '' : action.tool;
      const config = {
        assistant: ['.assistant-toggle:not(.chat-history-toggle)', 'assistant-open', 'Ask the editor'],
        chatHistory: ['.chat-history-toggle', 'chat-history-open', 'Chats'],
        profiles: ['.profile-trigger', '', 'Creator profiles'],
      }[action.tool];
      const button = doc.querySelector(config[0]);
      if (!button) throw new Error(config[2] + ' is unavailable here.');
      if (config[1] ? !doc.body.classList.contains(config[1]) : !doc.querySelector('.profile-dialog[open]')) button.click();
      const opened = config[1] ? doc.body.classList.contains(config[1]) : doc.querySelector('.profile-dialog[open]');
      if (!opened) throw new Error(config[2] + ' did not open.');
      return 'Opened ' + config[2] + '.';
    }
    if (action.type === 'open_tool' && Object.hasOwn(standalone, action.tool)) {
      return openStandalone(action.tool, signal);
    }
    if (action.type === 'schedule_platform' || action.type === 'set_control') {
      if (action.type === 'set_control' && action.tool) {
        const active = window.storylensVoiceTool() || currentSettingDocument().querySelector('.panel[data-mode]')?.dataset.mode;
        if (active !== action.tool && action.tool !== 'storylensCall') await window.storylensApplyVoiceAction(
          action.tool === 'preparePost' ? { type: 'open_publishing' } :
          action.tool === 'scheduledPosts' ? { type: 'open_schedule' } :
          { type: 'open_tool', tool: action.tool }, { signal, callId });
      }
      let doc = currentSettingDocument();
      if (doc === document && !doc.querySelector('.panel, #connectionPanel, .scheduled-dialog[open]') &&
          !Object.values(standalone).some(([, path]) => path === doc.location.pathname)) {
        doc = await workspace(signal);
      }
      if (action.type === 'schedule_platform') return schedulePlatform(doc, action.platform, signal);
      return setControl(doc, action, signal);
    }
    if (action.type === 'open_publishing') {
      const profile = document.body.dataset.creatorProfile || window.creatorProfile?.value;
      const query = ['cricket', 'gaming'].includes(profile) ? '?profile=' + profile : '';
      const frame = overlay('publishing', 'Publishing Studio', '/prepare-post.html' + query);
      await waitFor(() => frame.contentDocument?.getElementById('connectionPanel'), 'Publishing Studio did not finish opening.', signal);
      return 'Opened Publishing Studio.';
    }
    if (!['open_schedule', 'navigate', 'open_tool', 'prepare_tool', 'run_prepared'].includes(action.type)) {
      throw new Error('That Storylens action is unavailable.');
    }
    const doc = await workspace(signal);
    signal?.throwIfAborted();
    if (action.type === 'open_schedule') {
      if (doc === document && !doc.querySelector('.scheduled-dialog[open]')) closeOtherWorkspaces();
      if (!doc.querySelector('.scheduled-dialog[open]')) {
        const button = await waitFor(() => doc.querySelector('button.scheduled-toggle'), 'Scheduled posts is unavailable here.', signal);
        signal?.throwIfAborted();
        button.click();
      }
      if (!doc.querySelector('.scheduled-dialog[open]')) throw new Error('Scheduled posts did not open.');
      return 'Opened Scheduled posts.';
    }
    if (action.type === 'navigate') {
      if (!['result', 'export'].includes(action.target)) throw new Error('That Storylens control is unavailable.');
      const result = doc.getElementById('result');
      if (!result || result.classList.contains('is-pending')) throw new Error('The active tool has no finished result yet.');
      const target = action.target === 'export' ? doc.getElementById('editorExports') : result;
      if (!target || (action.target === 'export' && !target.children.length)) throw new Error('This result has no editor export controls.');
      reveal(target);
      return action.target === 'export' ? 'Opened the export controls.' : 'Opened the finished result controls.';
    }
    if (action.type === 'run_prepared') {
      if (!prepared || prepared.callId !== callId || (action.tool && normalizedTool(action.tool) !== prepared.tool)) {
        throw new Error('Ask Storylens to select the source for this tool first.');
      }
      const { tool, path } = prepared;
      const options = { run: true, reuse: true };
      const run = mainInputs.has(tool) ? prepareMain : prepareEmbedded;
      const result = await run(doc, options, tool, path, signal);
      prepared = null;
      return result;
    }
    const tool = normalizedTool(action.tool);
    if (action.type === 'open_tool') {
      await openTool(doc, tool, signal);
      return 'Opened ' + tools[tool] + '.';
    }
    if (typeof action.run !== 'boolean') throw new Error('The tool action must specify whether to run.');
    if (!mainInputs.has(tool) && !embeddedInputs.has(tool)) {
      throw new Error(tools[tool] + ' needs its own source controls. Ask me to open the tool.');
    }
    const path = source(action, tool);
    prepared = null;
    const run = mainInputs.has(tool) ? prepareMain : prepareEmbedded;
    const result = await run(doc, action, tool, path, signal);
    signal?.throwIfAborted();
    if (!action.run) prepared = { tool, path, callId };
    return result;
  };
})();
