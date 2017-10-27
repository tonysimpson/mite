import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from re import compile as re_compile, IGNORECASE, escape
from mite import MiteError, ensure_fixed_seperation
import mite_http


class OptionError(MiteError):
    def __init__(self, value):
        super().__init__("Attempted to set a value not in options", value=value)


class ElementNotFoundError(MiteError):
    def __init__(self, **kwargs):
        super().__init__("Could not find element in page with search terms", **kwargs)


def url_builder(base_url, *args, **kwargs):
    new_args = []
    if args:
        url = base_url[:-1] if base_url.endswith('/') else base_url
        for arg in args:
            if arg.endswith('/') and arg != args[-1]:
                arg = arg[:-1]
            if not arg.startswith('/'):
                arg = ''.join(['/', arg])
            new_args.append(arg)
        url = ''.join([url, ''.join(new_args)])
    else:
        url = base_url
    if kwargs:
        url = ''.join([url, '?', urlencode(kwargs)])
    return url


def browser_decorator(separation=0):
    def wrapper_factory(func):
        async def wrapper(context, *args, **kwargs):
            async with mite_http.get_session_pool().session_context(context):
                context.browser = Browser(context.http)
                async with ensure_fixed_seperation(separation):
                    result = await func(context, *args, **kwargs)
                del context.browser
                return result
        return wrapper
    return wrapper_factory


class Browser:
    """Browser abstraction wraps a session and provides some behaviour that is closer to a real browser."""
    def __init__(self, session, embedded_res=False):
        self._session = session
        self._embedded_res = embedded_res

    async def _download_resource(self, url, page, type):
        """Download a resource and then register it with the page it came from."""
        resource = await self._session.request('GET', url)
        page._register_resource(resource, type)

    async def _download_resources(self, page):
        """Downloads embedded resources, will do this recursively when content like iframes are present"""
        await asyncio.gather(*[self._download_resource(url, page, rtype)
            for url, rtype in page._extract_embeded_urls()])
        await asyncio.gather(*[self._download_resources(subpage) for subpage in page.resources_with_embedabbles])

    async def request(self, method, url, *args, **kwargs):
        """Perform a request and return a page object"""
        # Wrap everything in page object
        embedded_res = kwargs.pop("embedded_res", self._embedded_res)
        resp = await self._session.request(method, url, *args, **kwargs)
        page = Page(resp, self)
        if embedded_res:
            await self._download_resources(page)
        return page

    @property
    def headers(self):
        return self._session.headers

    async def get(self, url, *args, **kwargs):
        return await self.request("GET", url, *args, **kwargs)

    async def post(self, url, *args, **kwargs):
        return await self.request("POST", url, *args, **kwargs)

    async def erase_all_cookies(self):
        await self._session.erase_all_cookies()

    async def erase_session_cookies(self):
        await self._session.erase_session_cookies()

    async def get_cookie_list(self):
        return await self._session.get_cookie_list()


class Resource:
    """Base class for web resources"""
    def __init__(self, response, browser):
        self.response = response
        self.browser = browser


class ContainerMixin:
    """Mixin for things which need to find elements within themselves"""

    @staticmethod
    def _get_element(root_elem, name=None, attrs=None, text=None, recursive=True, **kwargs):
        # Bs4 text doesn't work with other finders according to robobrowser so split off.
        matches = root_elem.find_all(name, attrs, recursive, None, **kwargs)
        if not matches:
            return None
        if not text:
            return matches[0]
        text = re_compile(escape(text), IGNORECASE)
        for match in matches:
            if text.search(match.text):
                return match

    @staticmethod
    def _get_elements(root_elem, name=None, attrs=None, text=None, recursive=True, **kwargs):
        # Bs4 text doesn't work with other finders according to robobrowser so split off.
        matches = root_elem.find_all(name, attrs, recursive, None, **kwargs)
        if not matches:
            return []
        if not text:
            return matches
        text = re_compile(escape(text), IGNORECASE)
        return [match for match in matches if text.search(match.text)]

    def find(self, name=None, attrs={}, recursive=True, text=None,
             **kwargs):
        return self._get_element(self.dom, name=name, attrs=attrs, recursive=recursive, text=text,
                                 **kwargs)

    def find_all(self, name=None, attrs={}, recursive=True, text=None,
                 limit=None, **kwargs):
        return self._get_elements(self.dom, name=name, attrs=attrs, recursive=recursive, text=text,
                                  limit=limit, **kwargs)


class Page(Resource, ContainerMixin):
    """Page object built from a HTML response."""
    def __init__(self, response, browser):
        super().__init__(response, browser)
        self.dom = BeautifulSoup(response.text, "html.parser")
        self.scripts = []
        self.stylesheets = []
        self.resources = []
        self.frames = []

    def assert_element_in(self, name=None, attrs={}, recursive=True, text=None, **kwargs):
        if self.find(name=name, attrs=attrs, recursive=recursive, text=text, **kwargs):
            return True
        else:
            raise ElementNotFoundError(name=name, attrs=attrs, text=text, **kwargs)

    @property
    def cookies(self):
        return self.response.cookies

    @property
    def text(self):
        return self.response.text

    @property
    def headers(self):
        return self.response.headers

    @property
    def status_code(self):
        return self.response.status_code

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
            yield url_builder(base_url, elem.attrs['background']), 'resource'
        for elem in self.dom.find_all(['img', 'embed', 'bgsound'], attrs={'src': True}):
            yield url_builder(base_url, elem.attrs['src']), 'resource'
        for elem in self.dom.find_all(['script'], attrs={'src': True}):
            yield url_builder(base_url, elem.attrs['src']), 'script'
        for elem in self.dom.find_all(['frame', 'iframe'], attrs={'src': True}):
            yield url_builder(base_url, elem.attrs['src']), 'page'
        for elem in self.dom.find_all('link', attrs={'rel': 'stylesheet', 'href': True}):
            yield url_builder(base_url, elem.attrs['href']), 'stylesheet'
        for elem in self.dom.find_all('input', attrs={'type': 'image', 'href': True}):
            yield url_builder(base_url, elem.attrs['href']), 'resource'
        for elem in self.dom.find_all('applet', attrs={'code': True}):
            yield url_builder(base_url, elem.attrs['code']), 'resource'
        for elem in self.dom.find_all('object', attrs={'codebase': True}):
            yield url_builder(base_url, elem.attrs['codebase']), 'resource'
        for elem in self.dom.find_all('object', attrs={'data': True}):
            yield url_builder(base_url, elem.attrs['data']), 'resource'
        for elem in self.dom.find_all(True, attrs={'style': True}):
            yield url_builder(
                base_url, re_compile("url\(\s*[\"'](.*)[\"']\s*\)", IGNORECASE).match(elem.attrs['style'])), 'resource'

    async def on_dom_ready(self):
        # awaitable dom ready
        pass

    def get_form(self, attrs=None, text=None, **kwargs):
        return Form(self._get_element(self.dom, 'form', attrs, text, **kwargs), self)

    async def click_link(self, attrs=None, text=None, **kwargs):
        return await self.browser.get(
            self._get_element(self.dom, 'a', attrs=attrs, text=text, **kwargs).attrs['href'])

    def __repr__(self):
        return str(self.dom)

    def __str__(self):
        return self.__repr__()


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
            yield url_builder(base_url, match)


class Form(ContainerMixin):
    def __init__(self, element, page):
        self._page = page
        self.element = element
        self.method = element.get('method').upper()
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
        """Serializing should get files and data ready for submission. However acurl backend not currently
        supporting files so just data will be submitted.

        TODO: Add file support back in when we have acurl sorted"""
        return {'data': urlencode({name: f.value for name, f in self.fields.items() if not f.disabled})}

    def _extract_fields_as_subtype(self):
        FIELD_TYPES = ['select', 'textarea', 'input']
        fields = self.element.find_all(FIELD_TYPES)
        for field in fields:
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

    def __delitem__(self, item):
        del self.fields[item]

    def __setitem__(self, item, value):
        if item in self.fields:
            self.fields[item].value = value
        elif item in self.files:
            self.files[item].value = value

    async def submit(self, base_url='', embedded_res=False, **kwargs):
        return await self._page.browser.request(
            self.method, url_builder(base_url, self.action), embedded_res=embedded_res, **self._serialize(), **kwargs)


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

    # I want to use this but the existing LR tests are posting values not in the dropdown
    #@BaseFormField.value.setter
    #def value(self, value):
    #    if value in self.options:
    #        self._value = value
    #    else:
    #        raise OptionError(value)


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
        self._disabled = bool(elements[0].get('disabled'))

    @property
    def disabled(self):
        return self._disabled

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

