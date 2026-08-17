const state = { movies: [], editingId: null };
const $ = (selector) => document.querySelector(selector);
const dialog = $('#editor');
const form = $('#movieForm');

async function api(path = '', options = {}) {
  const response = await fetch(`/api/movies${path}`, { headers: { 'Content-Type': 'application/json' }, ...options });
  if (!response.ok && response.status !== 204) throw new Error('保存失败，请重试。');
  return response.status === 204 ? null : response.json();
}
function esc(text = '') { const node = document.createElement('span'); node.textContent = text; return node.innerHTML; }
function filteredMovies() {
  const query = $('#search').value.trim().toLowerCase(); const filter = $('#filter').value;
  return state.movies.filter(movie => (filter === 'all' || (filter === 'watched') === movie.watched) && [movie.title, movie.rating, movie.notes].join(' ').toLowerCase().includes(query));
}
function render() {
  const movies = filteredMovies(); const grid = $('#movies'); grid.innerHTML = '';
  $('#summary').textContent = `共 ${state.movies.length} 部电影 · 已看 ${state.movies.filter(m => m.watched).length} 部`;
  if (!movies.length) { grid.innerHTML = '<p class="empty">没有符合条件的电影</p>'; return; }
  const template = $('#movieTemplate');
  movies.forEach(movie => {
    const card = template.content.firstElementChild.cloneNode(true); const status = card.querySelector('.status');
    status.textContent = movie.watched ? '● 已看' : '○ 未看'; status.classList.toggle('watched', movie.watched);
    card.querySelector('h2').innerHTML = esc(movie.title); card.querySelector('.rating').innerHTML = movie.rating ? esc(movie.rating) : '暂无评价'; card.querySelector('.notes').innerHTML = movie.notes ? esc(movie.notes) : '暂无备注';
    const toggle = card.querySelector('.watch-toggle'); toggle.textContent = movie.watched ? '标为未看' : '标为已看';
    toggle.onclick = () => save({ ...movie, watched: !movie.watched, status: !movie.watched ? '已看' : '未看' });
    card.querySelector('.edit').onclick = () => openEditor(movie); card.querySelector('.delete').onclick = async () => { if (confirm(`删除《${movie.title}》？`)) { await api(`/${movie.id}`, { method: 'DELETE' }); state.movies = state.movies.filter(m => m.id !== movie.id); render(); } };
    grid.append(card);
  });
}
function openEditor(movie = null) { state.editingId = movie?.id ?? null; $('#dialogTitle').textContent = movie ? '编辑电影' : '添加电影'; form.title.value = movie?.title ?? ''; form.rating.value = movie?.rating ?? ''; form.watched.value = String(movie?.watched ?? false); form.notes.value = movie?.notes ?? ''; dialog.showModal(); }
async function save(movie) { const saved = await api(movie.id && state.movies.some(m => m.id === movie.id) ? `/${movie.id}` : '', { method: movie.id && state.movies.some(m => m.id === movie.id) ? 'PUT' : 'POST', body: JSON.stringify(movie) }); const index = state.movies.findIndex(m => m.id === saved.id); if (index >= 0) state.movies[index] = saved; else state.movies.unshift(saved); render(); }
form.addEventListener('submit', async event => { event.preventDefault(); const existing = state.movies.find(m => m.id === state.editingId); const watched = form.watched.value === 'true'; await save({ id: existing?.id ?? crypto.randomUUID(), title: form.title.value.trim(), rating: form.rating.value.trim(), watched, status: watched ? '已看' : '未看', notes: form.notes.value.trim() }); dialog.close(); });
$('#newMovie').onclick = () => openEditor(); $('#closeDialog').onclick = $('#cancel').onclick = () => dialog.close(); $('#search').oninput = $('#filter').onchange = render;
api().then(movies => { state.movies = movies; render(); }).catch(() => { $('#summary').textContent = '读取数据失败，请确认已通过 app.py 启动。'; });
