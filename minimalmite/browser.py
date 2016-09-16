from .session import SessionController
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from re import compile as re_compile, IGNORECASE
import asyncio


class BrowserController(SessionController):
    """Thin wrapper around a Session controller, provides a method to spin up browsers."""
    def __init__(self):
        super().__init__()

    def create_new_browser(self, profile=None, metrics_callback=None):
        return Browser(self.create_new_session(profile=profile, metrics_callback=metrics_callback))


class Browser:
    """Browser abstraction wraps a session and provides some behaviour that is closer to a real browser."""
    def __init__(self, session):
        self._session = session

    async def _download_resource(self, url, page, type):
        """Download a resource and then register it with the page it came from."""
        resource = await self._session.request('GET', url)
        page._register_resource(resource, type)

    async def _download_resources(self, page):
        """Downloads embedded resources, will do this recursively when content like iframes are present"""
        await asyncio.gather(*[self._download_resource(url, page, rtype)
            for url, rtype in page._extract_embeded_urls()])
        await asyncio.gather(*[self._download_resources(subpage) for subpage in page.resources_with_embedabbles])

    async def request(self, method, url, embedded_res=False, *args, **kwargs):
        """Perform a request and return a page object"""
        # Wrap everything in page object
        resp = await self._session.request(method, url, *args, **kwargs)
        page = Page(resp)
        if embedded_res:
            await self._download_resources(page)
        return page


class Resource:
    """Base class for web resources. Doesn't do much right now."""
    def __init__(self, response):
        self.response = response


class Page(Resource):
    """Page object built from a HTML response."""
    def __init__(self, response):
        super().__init__(response)
        self.dom = BeautifulSoup(response.text, "html.parser")
        self.scripts = []
        self.stylesheets = []
        self.resources = []
        self.frames = []

    @property
    def resources_with_embedabbles(self):
        """Any sub-resources of a page which might also contain their own embedded resources"""
        return self.frames + self.stylesheets

    def _register_resource(self, response, rtype):
        if rtype == 'resource':
            self.resources.append(Resource(response))
        elif rtype == 'script':
            self.scripts.append(Script(response))
        elif rtype == 'stylesheet':
            self.stylesheets.append(Stylesheet(response))
        elif rtype == 'page':
            self.frames.append(Page(response))

    def _extract_embeded_urls(self):
        """Extracts all embedded resources from a page"""
        base_url = self.response.url
        for burl in self.dom.find_all('base', {'href': True}):
            base_url = burl.attrs['href'] # reset the base url to the one in the page
        for elem in self.dom.find_all(True, attrs={'background': True}):
            yield urljoin(base_url, elem.attrs['background']), 'resource'
        for elem in self.dom.find_all(['img', 'embed', 'bgsound'], attrs={'src': True}):
            yield urljoin(base_url, elem.attrs['src']), 'resource'
        for elem in self.dom.find_all(['script'], attrs={'src': True}):
            yield urljoin(base_url, elem.attrs['src']), 'script'
        for elem in self.dom.find_all(['frame', 'iframe'], attrs={'src': True}):
            yield urljoin(base_url, elem.attrs['src']), 'page'
        for elem in self.dom.find_all('link', attrs={'rel': 'stylesheet', 'href': True}):
            yield urljoin(base_url, elem.attrs['href']), 'stylesheet'
        for elem in self.dom.find_all('input', attrs={'type': 'image', 'href': True}):
            yield urljoin(base_url, elem.attrs['href']), 'resource'
        for elem in self.dom.find_all('applet', attrs={'code': True}):
            yield urljoin(base_url, elem.attrs['code']), 'resource'
        for elem in self.dom.find_all('object', attrs={'codebase': True}):
            yield urljoin(base_url, elem.attrs['codebase']), 'resource'
        for elem in self.dom.find_all('object', attrs={'data': True}):
            yield urljoin(base_url, elem.attrs['data']), 'resource'
        for elem in self.dom.find_all(True, attrs={'style': True}):
            yield urljoin(
                base_url, re_compile("url\(\s*[\"'](.*)[\"']\s*\)", IGNORECASE).match(elem.attrs['style'])), 'resource'

    async def on_dom_ready(self):
        pass

    # Page load
    # Form filling
    # Link following
    # Add classes for different resources
    # awaitable dom ready


class Script(Resource):
    def __init__(self, response):
        super().__init__(response)


class Stylesheet(Resource):
    """Stylesheet object"""
    def __init__(self, response):
        super().__init__(response)
        self.resources = []

    def _extract_embedded_urls(self):
        """Extracts embedded resources from a stylesheet"""
        base_url = self.response.url
        for match in re_compile("url\(\s*[\"'](.*)[\"']\s*\)", IGNORECASE).finditer(self.response.text):
            yield urljoin(base_url, match)


class Form:
    pass