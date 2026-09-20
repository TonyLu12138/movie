'use strict';

const $ = selector => document.querySelector(selector);
const state = { movies: [], filter: 'all', editingId: null, detailId: null, detailToken: 0, editorBaseline: '', returnToDetails: false, editorBusy: false, notesBusy: false };
const editor = $('#editor');
const details = $('#details');
const form = $('#movieForm');
const placeholder = '/static/poster-placeholder.png';
let toastTimer;

function icons() { window.lucide?.createIcons({ attrs: { 'aria-hidden': 'true' } }); }
function field(name) { return form.elements.namedItem(name); }
function movieById(id) { return state.movies.find(movie => movie.id === id); }
function showError(target, message = '') { target.textContent = message; target.hidden = !message; }

async function api(path = '/api/movies', options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 20000);
  try {
    const headers = options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' };
    const response = await fetch(path, { ...options, headers: { ...headers, ...options.headers }, signal: controller.signal });
    if (response.status === 204) return null;
    const data = await response.json().catch(() => null);
    if (!response.ok) throw new Error(data?.error || `请求失败（${response.status}），请重试。`);
    if (data === null) throw new Error('服务器返回的数据无效。');
    return data;
  } catch (error) {
    if (error.name === 'AbortError') throw new Error('请求超时，请确认服务器状态后重试。');
    if (error instanceof TypeError) throw new Error('无法连接服务器，请检查网络后重试。');
    throw error;
  } finally { clearTimeout(timer); }
}

function toast(message, error = false) {
  const target = $('#toast');
  clearTimeout(toastTimer);
  target.textContent = message;
  target.classList.toggle('error', error);
  target.hidden = false;
  toastTimer = setTimeout(() => { target.hidden = true; }, 4500);
}

function setPoster(image, url, title, missingLabel = null) {
  const fallback = () => {
    image.onerror = null;
    image.src = placeholder;
    image.alt = `${title || '电影'}：暂无海报`;
    image.parentElement.classList.add('missing');
    if (missingLabel) missingLabel.hidden = false;
  };
  image.parentElement.classList.remove('missing');
  if (missingLabel) missingLabel.hidden = Boolean(url);
  if (!url) { fallback(); return; }
  image.onerror = fallback;
  image.alt = `${title || '电影'}海报`;
  image.src = url;
}

function filteredMovies() {
  const query = $('#search').value.trim().toLocaleLowerCase();
  const result = state.movies.filter(movie =>
    (state.filter === 'all' || movie.watched === (state.filter === 'watched')) &&
    [movie.title, movie.rating, movie.notes, movie.synopsis].join(' ').toLocaleLowerCase().includes(query));
  if ($('#sort').value === 'title') result.sort((a, b) => a.title.localeCompare(b.title, 'zh-CN'));
  if ($('#sort').value === 'updated') result.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
  return result;
}

function render() {
  const watched = state.movies.filter(movie => movie.watched).length;
  $('#summary').textContent = `共 ${state.movies.length} 部电影 · 已看 ${watched} 部 · 未看 ${state.movies.length - watched} 部`;
  $('#countAll').textContent = state.movies.length;
  $('#countWatched').textContent = watched;
  $('#countUnwatched').textContent = state.movies.length - watched;
  $('#footerCount').textContent = `${state.movies.length} 部电影，${watched} 段观影记忆`;
  $('#viewTitle').textContent = { all: '全部电影', watched: '已看电影', unwatched: '待看片单' }[state.filter];
  document.querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === state.filter)));
  const movies = filteredMovies();
  $('#resultCount').textContent = `${movies.length} 部`;
  $('#emptyState').hidden = movies.length > 0;
  const fragment = document.createDocumentFragment();
  for (const movie of movies) {
    const card = $('#movieTemplate').content.firstElementChild.cloneNode(true);
    card.dataset.movieId = movie.id;
    card.querySelector('.movie-title').textContent = movie.title;
    card.querySelector('.movie-title').title = movie.title;
    const status = card.querySelector('.status');
    status.textContent = movie.watched ? '已看' : '未看';
    status.classList.toggle('watched', movie.watched);
    const rating = card.querySelector('.rating');
    rating.textContent = movie.rating || '暂无评价';
    rating.classList.toggle('no-rating', !movie.rating);
    card.querySelector('.notes-preview').textContent = movie.notes || '暂无备注';
    setPoster(card.querySelector('img'), movie.poster_url, movie.title, card.querySelector('.poster-missing'));
    const open = card.querySelector('.card-open');
    open.setAttribute('aria-label', `查看${movie.title}的详情`);
    open.addEventListener('click', () => openDetails(movie.id));
    card.querySelector('.edit').addEventListener('click', () => openEditor(movieById(movie.id)));
    const toggle = card.querySelector('.watch-toggle');
    toggle.querySelector('span').textContent = movie.watched ? '标为未看' : '标为已看';
    toggle.setAttribute('aria-pressed', String(movie.watched));
    toggle.addEventListener('click', async () => {
      toggle.disabled = true;
      try {
        await saveMovie({ watched: !movieById(movie.id).watched }, movie.id);
        focusMovie(movie.id, '.watch-toggle');
      } catch (error) { toast(error.message, true); }
      finally { toggle.disabled = false; }
    });
    card.querySelector('.delete').addEventListener('click', async event => {
      if (!window.confirm(`确定删除《${movie.title.replace(/^《|》$/g, '')}》？删除后无法恢复。`)) return;
      const button = event.currentTarget;
      button.disabled = true;
      try {
        await api(`/api/movies/${encodeURIComponent(movie.id)}`, { method: 'DELETE' });
        state.movies = state.movies.filter(item => item.id !== movie.id);
        render();
        toast('电影已删除');
        $('#newMovie').focus({ preventScroll: true });
      } catch (error) { toast(error.message, true); }
      finally { button.disabled = false; }
    });
    fragment.append(card);
  }
  $('#movies').replaceChildren(fragment);
  icons();
}

function focusMovie(id, selector = '.card-open') {
  const card = Array.from(document.querySelectorAll('.movie-card')).find(item => item.dataset.movieId === id);
  card?.querySelector(selector)?.focus({ preventScroll: true });
}

function upsert(movie) {
  const index = state.movies.findIndex(item => item.id === movie.id);
  if (index >= 0) state.movies[index] = movie;
  else state.movies.unshift(movie);
}

async function saveMovie(payload, id = null) {
  const saved = await api(id ? `/api/movies/${encodeURIComponent(id)}` : '/api/movies', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(payload) });
  upsert(saved);
  render();
  return saved;
}

function notesChanged() { return details.open && $('#detailNotes').value !== (movieById(state.detailId)?.notes || ''); }
function updateNotesStatus(message) {
  $('#notesCount').textContent = `${$('#detailNotes').value.length} / 5000`;
  $('#notesStatus').textContent = message ?? (notesChanged() ? '有未保存的修改' : '');
}

function populateDetails(movie) {
  $('#detailTitle').textContent = movie.title;
  $('#detailStatus').textContent = movie.watched ? '已看' : '未看';
  $('#detailStatus').classList.toggle('watched', movie.watched);
  $('#detailRating').textContent = movie.rating || '暂无评价';
  $('#detailSynopsis').textContent = movie.synopsis || '暂无剧情简介';
  $('#detailNotes').value = movie.notes;
  setPoster($('#detailPoster'), movie.poster_url, movie.title, $('#detailPosterMissing'));
  updateNotesStatus('');
}

function detailControlsDisabled(disabled) {
  $('#detailNotes').disabled = disabled;
  $('#saveNotes').disabled = disabled;
  $('#editFromDetails').disabled = disabled;
}

async function openDetails(id) {
  const movie = movieById(id);
  if (!movie) return;
  state.detailId = id;
  const token = ++state.detailToken;
  showError($('#detailError'));
  populateDetails(movie);
  detailControlsDisabled(true);
  details.showModal();
  details.scrollTop = 0;
  try {
    const fresh = await api(`/api/movies/${encodeURIComponent(id)}`);
    if (state.detailToken !== token || !details.open) return;
    upsert(fresh);
    populateDetails(fresh);
    detailControlsDisabled(false);
  } catch (error) {
    if (state.detailToken !== token || !details.open) return;
    showError($('#detailError'), `${error.message} 请关闭后重新打开。`);
  }
}

function closeDetails() {
  if (state.notesBusy) return false;
  if (notesChanged() && !window.confirm('备注尚未保存，确定放弃修改？')) return false;
  const id = state.detailId;
  state.detailToken++;
  details.close();
  state.detailId = null;
  focusMovie(id);
  return true;
}

$('#notesForm').addEventListener('submit', async event => {
  event.preventDefault();
  if (state.notesBusy || !state.detailId) return;
  state.notesBusy = true;
  detailControlsDisabled(true);
  showError($('#detailError'));
  updateNotesStatus('正在保存…');
  try {
    await saveMovie({ notes: $('#detailNotes').value }, state.detailId);
    updateNotesStatus('备注已保存');
  } catch (error) {
    showError($('#detailError'), error.message);
    updateNotesStatus('保存失败，内容已保留');
  } finally { state.notesBusy = false; detailControlsDisabled(false); }
});

function editorPayload() {
  return { title: field('title').value.trim(), rating: field('rating').value.trim(), watched: field('watched').checked, notes: field('notes').value, synopsis: field('synopsis').value.trim(), poster_url: field('poster_url').value.trim() };
}
function editorChanged() { return editor.open && JSON.stringify(editorPayload()) !== state.editorBaseline; }
function setEditorBusy(busy) {
  state.editorBusy = busy;
  form.querySelectorAll('input, textarea, button').forEach(control => { control.disabled = busy; });
}

function openEditor(movie = null, returnToDetails = false) {
  state.editingId = movie?.id || null;
  state.returnToDetails = returnToDetails;
  $('#dialogTitle').textContent = movie ? '编辑电影' : '添加电影';
  for (const name of ['title', 'rating', 'notes', 'synopsis', 'poster_url']) field(name).value = movie?.[name] || '';
  field('watched').checked = movie?.watched || false;
  $('#posterFile').value = '';
  $('#uploadStatus').textContent = '';
  setPoster($('#posterPreview'), movie?.poster_url, movie?.title);
  showError($('#editorError'));
  setEditorBusy(false);
  state.editorBaseline = JSON.stringify(editorPayload());
  editor.showModal();
  editor.scrollTop = 0;
  field('title').focus();
}

function closeEditor() {
  if (state.editorBusy) return;
  if (editorChanged() && !window.confirm('电影资料尚未保存，确定放弃修改？')) return;
  const id = state.editingId;
  editor.close();
  if (state.returnToDetails && id) openDetails(id);
  else focusMovie(id);
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (state.editorBusy || !form.reportValidity()) return;
  const payload = editorPayload();
  if (!payload.title) { showError($('#editorError'), '电影名称不能为空。'); return; }
  setEditorBusy(true);
  showError($('#editorError'));
  try {
    const saved = await saveMovie(payload, state.editingId);
    state.editorBaseline = JSON.stringify(payload);
    editor.close();
    if (state.returnToDetails) openDetails(saved.id);
    else { focusMovie(saved.id); toast('电影已保存'); }
  } catch (error) { showError($('#editorError'), error.message); }
  finally { setEditorBusy(false); }
});

$('#uploadPoster').addEventListener('click', () => $('#posterFile').click());
$('#posterFile').addEventListener('change', async event => {
  const file = event.target.files[0];
  if (!file) return;
  showError($('#editorError'));
  if (file.size > 5 * 1024 * 1024) { showError($('#editorError'), '海报大小不能超过 5 MB。'); event.target.value = ''; return; }
  const body = new FormData();
  body.append('file', file);
  setEditorBusy(true);
  $('#uploadStatus').textContent = '正在上传…';
  try {
    const result = await api('/api/posters', { method: 'POST', body });
    field('poster_url').value = result.poster_url;
    setPoster($('#posterPreview'), result.poster_url, field('title').value);
    $('#uploadStatus').textContent = '海报已上传';
  } catch (error) { showError($('#editorError'), error.message); $('#uploadStatus').textContent = '上传失败'; }
  finally { setEditorBusy(false); event.target.value = ''; }
});
$('#posterUrl').addEventListener('change', () => setPoster($('#posterPreview'), field('poster_url').value.trim(), field('title').value));
$('#clearPoster').addEventListener('click', () => { field('poster_url').value = ''; setPoster($('#posterPreview'), '', ''); $('#uploadStatus').textContent = ''; });

$('#editFromDetails').addEventListener('click', () => {
  const movie = movieById(state.detailId);
  if (closeDetails()) openEditor(movie, true);
});
$('#detailNotes').addEventListener('input', () => updateNotesStatus());
$('#closeDetails').addEventListener('click', closeDetails);
$('#closeEditor').addEventListener('click', closeEditor);
$('#cancelEditor').addEventListener('click', closeEditor);
$('#newMovie').addEventListener('click', () => openEditor());
for (const [dialog, close] of [[details, closeDetails], [editor, closeEditor]]) {
  dialog.addEventListener('cancel', event => { event.preventDefault(); close(); });
  dialog.addEventListener('click', event => {
    const rect = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom)) close();
  });
}
document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => { state.filter = button.dataset.filter; render(); }));
$('#search').addEventListener('input', render);
$('#sort').addEventListener('change', render);
$('#resetFilters').addEventListener('click', () => { $('#search').value = ''; state.filter = 'all'; render(); });
window.addEventListener('beforeunload', event => {
  if (notesChanged() || editorChanged() || state.editorBusy || state.notesBusy) { event.preventDefault(); event.returnValue = ''; }
});

async function loadMovies() {
  $('#movies').setAttribute('aria-busy', 'true');
  $('#loadState').hidden = false;
  try {
    state.movies = await api();
    render();
    $('#loadState').hidden = true;
  } catch (error) {
    $('#summary').textContent = '片单暂时无法读取';
    const message = document.createElement('p');
    message.textContent = error.message;
    const retry = document.createElement('button');
    retry.textContent = '重新加载';
    retry.className = 'secondary';
    retry.addEventListener('click', () => { retry.disabled = true; loadMovies(); });
    $('#loadState').replaceChildren(message, retry);
  } finally { $('#movies').setAttribute('aria-busy', 'false'); }
}
icons();
loadMovies();
