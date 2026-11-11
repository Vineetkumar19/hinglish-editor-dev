// The normal studio owns every edit. This only labels and selects the sample.
(() => {
  if (!project.demo || project.script_preview) return;
  if (project.demo_background !== demoBackground) downloadVideo.classList.add('disabled');
  paintStudioBackground();

  // Each sample has its own phrase groups. Reusing another sample's cues gives
  // different entrances from that template's approved narrated demonstration.
  let opening = false;
  document.querySelector('.template-list')?.addEventListener('click', async event => {
    const card = event.target.closest('.template-card');
    if (!card || card.dataset.style === project.style) return;
    if (card.dataset.style.startsWith('cinematic_') && templates[card.dataset.style]?.layout === 'cinematic_reference') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (opening || studioSaving) return;
    opening = true;
    persistStudio();
    try {
      const response = await (window.storylensFetch || fetch)('/caption-demos.json', {cache: 'no-store'});
      const catalog = await (window.storylensResponse ? window.storylensResponse(response) : response.json());
      const target = catalog.templates?.[card.dataset.style]?.url;
      if (!response.ok || !target?.startsWith('/caption-output/template-demos/')) {
        throw new Error('This caption demo could not be opened. Refresh the editor and try again.');
      }
      location.assign(target + '?demo_style=' + encodeURIComponent(card.dataset.style) + '&background=' + demoBackground);
    } catch (error) {
      studioStatus.textContent = window.storylensError ? window.storylensError(error) : 'The caption demo could not be opened. Refresh the editor and try again.';
    } finally { opening = false; }
  }, true);
  const requestedBackground = new URLSearchParams(location.search).get('background');
  if (['black', 'white'].includes(requestedBackground) && requestedBackground !== demoBackground) {
    demoBackground = requestedBackground;
    dirtyStudio();
    draw();
  }
  const selected = new URLSearchParams(location.search).get('demo_style') || currentStyle;
  if (selected && templates[selected] && (selected !== currentStyle || selected !== project.style)) {
    const card = Array.from(document.querySelectorAll('.template-card'))
      .find(button => button.dataset.style === selected);
    card?.click();
  }
})();
