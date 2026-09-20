import json
from threading import Thread

import pytest
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server

from movie_app import ROOT
from movie_app.extensions import db
from movie_app.services import import_movies

pytestmark = pytest.mark.browser
ARTIFACTS = ROOT / "test-results"


@pytest.fixture(scope="module")
def browser(request):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=request.config.getoption("--browser-channel"), headless=True)
        yield browser
        browser.close()


@pytest.fixture
def live_url(app):
    # Keep UI tests independent of optional third-party artwork and the network.
    with (ROOT / "movie_app" / "static" / "poster-placeholder.png").open("rb") as image:
        response = app.test_client().post("/api/posters", data={"file": (image, "fixture.png")})
    assert response.status_code == 201
    with app.app_context():
        catalog = json.loads((ROOT / "movie_app" / "catalog.json").read_text(encoding="utf-8"))
        for metadata in catalog.values():
            metadata["poster_url"] = response.json["poster_url"]
        import_movies(ROOT / "films.json", catalog=catalog)
        db.session.commit()
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join(timeout=5)


def assert_layout(page):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    for dialog in page.locator('dialog[open]').all():
        assert dialog.evaluate("el => el.scrollWidth <= el.clientWidth + 1")
        bounds = dialog.bounding_box()
        assert bounds["x"] >= 0 and bounds["y"] >= 0
        assert bounds["x"] + bounds["width"] <= page.viewport_size["width"] + 1


@pytest.mark.parametrize("width,height", [(1366, 900), (390, 844)])
def test_complete_movie_workflow(browser, live_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(live_url)
        expect(page.locator('.movie-card')).to_have_count(166)
        expect(page.locator('#countAll')).to_have_text('166')
        assert_layout(page)
        ARTIFACTS.mkdir(exist_ok=True)
        page.screenshot(path=str(ARTIFACTS / f"catalog-{width}.png"))

        page.locator('#search').fill('1917')
        expect(page.locator('.movie-card')).to_have_count(1)
        page.locator('.card-open').click()
        expect(page.locator('#detailTitle')).to_have_text('\u300a1917\u300b')
        expect(page.locator('#detailNotes')).to_be_enabled()
        assert page.locator('#detailPoster').evaluate('img => img.complete && img.naturalWidth > 0')
        expect(page.locator('#detailPosterMissing')).to_be_hidden()
        assert_layout(page)
        page.screenshot(path=str(ARTIFACTS / f"details-{width}.png"))
        page.locator('#closeDetails').click()
        page.locator('#search').fill('')

        page.locator('#newMovie').click()
        page.locator('#movieTitle').fill('UI test movie')
        page.locator('#movieRating').fill('4.5/5')
        page.locator('#movieSynopsis').fill('A complete synopsis for the new movie.')
        page.locator('#movieNotes').fill('Initial notes')
        page.locator('#posterFile').set_input_files(ROOT / 'movie_app' / 'static' / 'poster-placeholder.png')
        expect(page.locator('#uploadStatus')).to_have_text('\u6d77\u62a5\u5df2\u4e0a\u4f20')
        assert_layout(page)
        page.locator('#saveMovie').click()
        expect(page.locator('#editor')).not_to_be_visible()
        page.locator('#search').fill('UI test movie')
        expect(page.locator('.movie-card')).to_have_count(1)
        page.locator('.card-open').click()
        expect(page.locator('#detailNotes')).to_be_enabled()
        expect(page.locator('#detailSynopsis')).to_have_text('A complete synopsis for the new movie.')
        assert '/media/posters/' in page.locator('#detailPoster').get_attribute('src')
        page.locator('#detailNotes').fill('Persistent note\n\u4e2d\u6587\u5907\u6ce8')
        page.locator('#saveNotes').click()
        expect(page.locator('#notesStatus')).to_have_text('\u5907\u6ce8\u5df2\u4fdd\u5b58')
        page.reload()
        expect(page.locator('.movie-card')).to_have_count(167)
        page.locator('#search').fill('Persistent note')
        expect(page.locator('.movie-card')).to_have_count(1)
        page.locator('.card-open').click()
        expect(page.locator('#detailNotes')).to_have_value('Persistent note\n\u4e2d\u6587\u5907\u6ce8')
        page.locator('#editFromDetails').click()
        page.locator('#movieTitle').fill('Edited UI movie')
        page.locator('#movieSynopsis').fill('Updated synopsis')
        page.locator('#saveMovie').click()
        expect(page.locator('#detailTitle')).to_have_text('Edited UI movie')
        expect(page.locator('#detailNotes')).to_be_enabled()
        expect(page.locator('#detailSynopsis')).to_have_text('Updated synopsis')
        expect(page.locator('#detailNotes')).to_have_value('Persistent note\n\u4e2d\u6587\u5907\u6ce8')
        page.locator('#closeDetails').click()
        page.locator('.watch-toggle').click()
        expect(page.locator('.watch-toggle')).to_have_attribute('aria-pressed', 'true')
        page.locator('[data-filter="unwatched"]').click()
        expect(page.locator('.movie-card')).to_have_count(0)
        expect(page.locator('#emptyState')).to_be_visible()
        page.locator('[data-filter="watched"]').click()
        expect(page.locator('.movie-card')).to_have_count(1)
        page.once('dialog', lambda dialog: dialog.dismiss())
        page.locator('.delete').click()
        expect(page.locator('.movie-card')).to_have_count(1)
        page.once('dialog', lambda dialog: dialog.accept())
        page.locator('.delete').click()
        expect(page.locator('.movie-card')).to_have_count(0)
        page.locator('#resetFilters').click()
        expect(page.locator('.movie-card')).to_have_count(166)
        assert errors == []
    finally:
        context.close()


def test_error_handling_dirty_notes_and_xss(browser, live_url):
    context = browser.new_context(viewport={"width": 390, "height": 844})
    page = context.new_page()
    try:
        page.goto(live_url)
        expect(page.locator('.movie-card')).to_have_count(166)
        page.locator('.card-open').first.click()
        expect(page.locator('#detailNotes')).to_be_enabled()
        expect(page.locator('#detailPosterMissing')).to_be_visible()
        page.locator('#detailNotes').fill('Unsaved note')
        page.once('dialog', lambda dialog: dialog.dismiss())
        page.locator('#closeDetails').click()
        expect(page.locator('#details')).to_be_visible()
        expect(page.locator('#detailNotes')).to_have_value('Unsaved note')
        page.route('**/api/movies/*', lambda route: route.fulfill(status=503, json={"error": "Temporary failure"}) if route.request.method == 'PATCH' else route.continue_())
        page.locator('#saveNotes').click()
        expect(page.locator('#detailError')).to_have_text('Temporary failure')
        expect(page.locator('#detailNotes')).to_have_value('Unsaved note')
        expect(page.locator('#saveNotes')).to_be_enabled()
        page.unroute('**/api/movies/*')
        page.locator('#saveNotes').click()
        expect(page.locator('#notesStatus')).to_have_text('\u5907\u6ce8\u5df2\u4fdd\u5b58')
        page.locator('#closeDetails').click()
        page.locator('#newMovie').click()
        title = '<img src=x onerror=window.__xss=1>'
        page.locator('#movieTitle').fill(title)
        page.locator('#movieSynopsis').fill('<script>window.__xss=1</script>')
        page.locator('#posterUrl').fill(live_url + '/missing-image.jpg')
        page.locator('#saveMovie').click()
        expect(page.locator('#editor')).not_to_be_visible()
        page.locator('#search').fill(title)
        expect(page.locator('.movie-card')).to_have_count(1)
        page.locator('.card-open').click()
        expect(page.locator('#detailNotes')).to_be_enabled()
        expect(page.locator('#detailPosterMissing')).to_be_visible()
        expect(page.locator('#detailTitle')).to_have_text(title)
        assert page.evaluate('window.__xss') is None
        assert_layout(page)
        page.locator('#closeDetails').click()
        page.locator('#newMovie').click()
        page.locator('#movieTitle').fill('Do not lose this title')
        page.route('**/api/movies', lambda route: route.fulfill(status=503, json={"error": "Cannot save"}))
        page.locator('#saveMovie').click()
        expect(page.locator('#editorError')).to_have_text('Cannot save')
        expect(page.locator('#movieTitle')).to_have_value('Do not lose this title')
        expect(page.locator('#saveMovie')).to_be_enabled()
    finally:
        context.close()


@pytest.mark.parametrize("width,height", [(320, 640), (1920, 1080)])
def test_responsive_extremes_and_keyboard(browser, live_url, width, height):
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    try:
        page.goto(live_url)
        expect(page.locator('.movie-card')).to_have_count(166)
        assert_layout(page)
        page.locator('#search').fill('1917')
        page.locator('.card-open').focus()
        page.keyboard.press('Enter')
        expect(page.locator('#detailNotes')).to_be_enabled()
        assert_layout(page)
        page.keyboard.press('Escape')
        expect(page.locator('#details')).not_to_be_visible()
        page.locator('#newMovie').click()
        assert_layout(page)
        ARTIFACTS.mkdir(exist_ok=True)
        page.screenshot(path=str(ARTIFACTS / f"editor-{width}.png"))
        page.keyboard.press('Escape')
        expect(page.locator('#editor')).not_to_be_visible()
    finally:
        context.close()
