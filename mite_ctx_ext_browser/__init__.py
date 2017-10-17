import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from re import compile as re_compile, IGNORECASE, escape
from mite import MiteError


class OptionError(MiteError):
    def __init__(self, value):
        super().__init__()
        self.message = "Attempted to set a value not in options".format(value)


def add_mixin(context):
    context.browser = Browser(context.http)


def get_ext():
    return add_mixin, None, ['http']


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
        page = Page(resp, self)
        if embedded_res:
            await self._download_resources(page)
        return page


class Resource:
    """Base class for web resources"""
    def __init__(self, response, browser):
        self.response = response
        self.browser = browser


class ContainerMixin:
    """Mixin for things which need to find elements within themselves"""

    @staticmethod
    def _get_element(root_elem, name=None, attrs=None, text=None, **kwargs):
        # Bs4 text doesn't work with other finders according to robobrowser so split off.
        matches = root_elem.find_all(name, attrs, True, None, **kwargs)
        if not text:
            return matches[0]
        text = re_compile(escape(text), IGNORECASE)
        for match in matches:
            if text.search(match.text):
                return match


class Page(Resource, ContainerMixin):
    """Page object built from a HTML response."""
    def __init__(self, response, browser):
        super().__init__(response, browser)
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
        # TODO: Look into prerender and whether we should be getting these resources.
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
        # awaitable dom ready
        pass

    def get_form(self, attrs=None, text=None, **kwargs):
        return Form(self._get_element(self.dom, 'form', attrs, text, **kwargs), self)

    async def click_link(self, attrs=None, text=None, **kwargs):
        return await self.browser.request('GET', self._get_element(
            self.dom, 'a', attrs=attrs, text=text, **kwargs).attrs['href'])


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


class Form(ContainerMixin):
    def __init__(self, element, page):
        self._page = page
        self.element = element
        self.method = element.get('method')
        self.action = element.get('action')
        self.fields = {}
        self.files = {}
        self._set_fields()

    def _set_fields(self):
        for f in self._extract_fields_as_subtype():
            if isinstance(f, FileInputField):
                self.files[f.name] = f
            else:
                self.fields[f.name] = f

    def _serialize(self):
        return {'data': {name: f.value for name, f in self.fields.items() if not f.disabled},
                'files': [(name, v) for name, f in self.files.items() for v in f.value if not f.disabled]}

    def _extract_fields_as_subtype(self):
        fields = self.element.find_all(['select', 'textarea', 'input'])
        while fields:
            field = fields.pop()
            if field.name == 'select':
                yield SelectField(field)
            elif field.name == 'textarea':
                yield BaseFormField(field)
            elif field.name == 'input':
                if field.attrs['type'] in ['reset', 'submit']:
                    continue
                elif field.attrs['type'] == 'file':
                    yield FileInputField(field)
                elif field.attrs['type'] == 'radio':
                    radios = [f for f in fields[:] if f.attrs['name'] == field.attrs['name']]
                    for r in radios:
                        fields.remove(r)
                    yield RadioField(radios)
                elif field.attrs['type'] == 'checkbox':
                    yield CheckboxField(field)
                else:
                    yield BaseFormField(field)

    def __getitem__(self, item):
        result = self.fields.get(item) or self.files.get(item)
        if result:
            return result
        else:
            raise KeyError("{} not in form fields".format(item))

    def __setitem__(self, item, value):
        if item in self.fields:
            self.fields[item].value = value
        elif item in self.files:
            self.files[item].value = value
        else:
            raise KeyError("{} not in form fields".format(item))

    async def submit(self, embedded_res=False):
        return await self._page.browser.request(self.method, self.action, embedded_res=embedded_res, **self._serialize())


class BaseFormField:
    def __init__(self, element):
        self.element = element
        self.name = element.attrs.get('name')
        self._value = element.attrs.get('value')
        self._disabled = bool(element.get('disabled'))

    @property
    def disabled(self):
        return self._disabled

    def enable(self):
        self._disabled = False

    def disable(self):
        self._disabled = True

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value


class SelectField(BaseFormField):
    def __init__(self, element):
        super().__init__(element)
        self.options = element.find_all('option')

    def _get_options(self):
        if not self.options[-1].value:
            return [o.text for o in self.options]
        else:
            return [o.value for o in self.options]

    @BaseFormField.value.setter
    def value(self, value):
        if value in self.options:
            self._value = value
        else:
            raise OptionError(value)


class CheckboxField(BaseFormField):
    def __init__(self, element):
        super().__init__(element)
        self._checked = False

    def toggle(self):
        self._checked = not self._checked
        return self._checked

    @property
    def disabled(self):
        return self._disabled and (not self._checked)


class RadioField:
    """Radio fields are made up of multiple inputs with the same name but submit only one value."""
    def __init__(self, elements):
        self.elements = elements
        self.name = elements[0].attrs.get('name')
        self._value = elements[0].attrs.get('value')

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if value in [e.get('value') for e in self.elements]:
            self._value = value
        else:
            raise OptionError(value)


class FileInputField(BaseFormField):
    def __init__(self, element):
        super().__init__(element)
        self._value = []

    @BaseFormField.value.setter
    def value(self, file):
        self._value.append(file)

