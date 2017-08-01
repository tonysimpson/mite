#!/usr/bin/env python
# -*- coding:  utf-8 -*-
"""
human_curl.core
~~~~~~~~~~~~~~~

Heart of human_curl library


:copyright: Copyright 2011 - 2012 by Alexandr Lispython (alex@obout.ru).
:license: BSD, see LICENSE for more details.
"""

import time
from os.path import exists as file_exists
from logging import getLogger
from re import compile as re_compile
from itertools import chain
from http.cookiejar import CookieJar
from http.cookies import SimpleCookie, CookieError
from urllib.parse import urlparse, urljoin, urlunparse, parse_qsl, urlencode, quote_plus
from bs4 import BeautifulSoup
import pycurl
import chardet
from . import get_version
from .compat import json
from .exceptions import (InvalidMethod, CurlError, InterfaceError)
from .utils import (decode_gzip, CaseInsensitiveDict, to_cookiejar,
                    morsel_to_cookie, data_wrapper, make_curl_post_files,
                    to_unicode, logger_debug, urlnoencode)
from .auth import AuthManager, BasicAuth

from io import BytesIO

try:
    import platform
    if platform.system().lower() != 'windows':
        import signal
        from threading import current_thread
        if current_thread().name == 'MainThread':
            signal.signal(signal.SIGPIPE, signal.SIG_IGN)
except ImportError:
    pass


__all__ = ("Request", "Response", "HTTPError", "InvalidMethod", "CurlError", "CURL_INFO_MAP")

logger = getLogger("human_curl.core")

# DEFAULTS
DEFAULT_TIME_OUT = 15.0
STATUSES_WITH_LOCATION = (301, 302, 303, 305, 307)
PYCURL_VERSION_INFO = pycurl.version_info()
HTTP_GENERAL_RESPONSE_HEADER = re_compile(r"(?P<version>HTTP\/.*?)\s+(?P<code>\d{3})\s+(?P<message>.*)")

try:
    CURL_VERSION = PYCURL_VERSION_INFO[1]
except IndexError as e:
    CURL_VERSION = ""
    logger.warn("Unknown pycURL / cURL version")


PROXIES_TYPES_MAP = {
    'socks5': pycurl.PROXYTYPE_SOCKS5,
    'socks4': pycurl.PROXYTYPE_SOCKS4,
    'http': pycurl.PROXYTYPE_HTTP,
    'https': pycurl.PROXYTYPE_HTTP}




def get_code_by_name(name):
    """Returns proxy type code
    """
    return PROXIES_TYPES_MAP[name]


class Request(object):
    r"""A single HTTP / HTTPS requests

    Usage:

    >>> request = Request("GET", "http://google.com")
    >>> print(repr(request))
    <Request: GET [ http://google.com ]>
    >>> request.send()
    >>> response = requests.response
    """

    SUPPORTED_METHODS = ("GET", "HEAD", "POST", "DELETE", "PUT", "OPTIONS")

    def __init__(self, method, url, params=None, data=None, headers=None, cookies=None,
                 files=None, timeout=None, connection_timeout=None, allow_redirects=True,
                 max_redirects=30, proxy=None, auth=None, network_interface=None, use_gzip=None,
                 validate_cert=False, ca_certs=None, cert=None, debug=False, user_agent=None,
                 ip_v6=False, options=None, netrc=False, netrc_file=None, encode_query=None, **kwargs):
        """A single HTTP / HTTPS request

        Arguments:
        - `url`: (string) resource url
        - `method`: (string) one of `self.SUPPORTED_METHODS`
        - `data`: (dict, duple, string) data to send as Content-Disposition form-data
        - `params`: (dict, tuple) of GET params (?param1=value1&param2=value2)
        - `headers`: (dict, tuple) of request headers
        - `cookies`: (dict, tuple or CookieJar) of cookies
        - `files`: (dict, tuple or list) of files
           Example:
               (('field_file_name', '/path/to/file.txt'),
               ('field_file_name', open('/path/to/file.txt')),
               ('multiple_files_field', (open("/path/to/file.1.txt"), open("/path/to/file.1.txt"))),
               ('multiple_files_field', ("/path/to/file.1.txt", "/path/to/file.1.txt")))
        - `timeout`: (float) connection time out
        - `connection_timeout`: (float)
        - `allow_redirects`: (bool) follow redirects parametr
        - `proxy`: (dict, tuple or list) of proxies
           Examples:
               ('http', ('127.0.0.1', 9050))
               ('http', ('127.0.0.1', 9050, ('username', 'password')))
        - `auth`: (dict, tuple or list) for resource base auth
        - `network_interface`: (str) Pepform an operation using a specified interface.
           You can enter interface name, IP address or host name.
        - `use_gzip`: (bool) accept gzipped data
        - `validate_cert`: (bool) validate server certificate
        - `ca_certs`: tells curl to use the specified certificate file to verify the peer.
        - `cert`: (string) tells curl to use the specified certificate file
           when getting a file with HTTPS.
        - `debug`: (bool) use for `pycurl.DEBUGFUNCTION`
        - `user_agent`: (string) user agent
        - `ip_v6`: (bool) use ipv6 protocol
        - `options`: (tuple, list) low level pycurl options using
        """
        self._url = url
        if not method or not isinstance(method, str):
            raise InterfaceError("method argument must be string")

        if method.upper() not in self.SUPPORTED_METHODS:
            raise InvalidMethod("cURL do not support %s method" % method.upper())

        self._method = method.upper()

        self._user_agent = user_agent

        self._headers = data_wrapper(headers)

        if files is not None:
            self._files = make_curl_post_files(files)
        else:
            self._files = None

        self._params = data_wrapper(params)

        # String, dict, tuple, list
        if isinstance(data, (str, bytes)) or data is None:
            self._data = data
        else:
            self._data = data_wrapper(data)

        if isinstance(cookies, CookieJar):
            self._cookies = cookies
        elif isinstance(cookies, (tuple, dict)):
            self._cookies = to_cookiejar(cookies)
        else:
            self._cookies = None

        if proxy is None:
            self._proxy = proxy
        elif isinstance(proxy, tuple):
            if len(proxy) != 2 or not isinstance(proxy[1], tuple):
                raise InterfaceError('Proxy must be a tuple object')
            else:
                self._proxy = proxy

        if not isinstance(network_interface, str) and network_interface is not None:
            raise InterfaceError("Network interface argument must be string or None got %r" % type(network_interface))

        self._network_interface = network_interface

        if isinstance(auth, AuthManager):
            self._auth = auth
        elif isinstance(auth, tuple):
            self._auth = BasicAuth(*auth)
        elif auth is None:
            self._auth = None
        else:
            raise ValueError("auth must be list, tuple or dict, not %s" % type(auth))

        # follow by location header field
        self._allow_redirects = allow_redirects
        self._max_redirects = max_redirects

        self._timeout = int(timeout or DEFAULT_TIME_OUT)
        self._connection_timeout = connection_timeout

        self._use_gzip = use_gzip

        # Certificates
        self._validate_cert = validate_cert
        self._ca_certs = ca_certs
        self._cert = cert
        self._start_time = time.time()
        self._debug_curl = debug
        self._ip_v6 = ip_v6

        self.response = None

        if options is None:
            self._options = None
        elif isinstance(options, (list, tuple)):
            self._options = data_wrapper(options)
        else:
            raise InterfaceError("options must be None, list or tuple")

        self._curl = None

        self.body_output = BytesIO()
        self.headers_output = BytesIO()

        self._netrc = netrc
        self._netrc_file = None

        self._encode_query = encode_query

    def __repr__(self, ):
        # TODO: collect `Request` settings into representation string
        return "<%s: %s [ %s ]>" % (self.__class__.__name__, self._method, self._url)

    @property
    def user_agent(self):
        if not self._user_agent:
            self._user_agent = "Mozilla/5.0 (compatible; human_curl; {0}; +http://h.wrttn.me/human_curl)".format(get_version())
        return self._user_agent

    @property
    def url(self):
        if not self._url:
            self._url = self._build_url()
        return self._url

    def _build_url(self):
        url = self._url
        if(self,_params):
            params = '&'.join('%s=%s' % (key, value) for key, value in self._params.items())
            url = ''.join([url, '?', params])
        self._url = quote(url)


    def send(self):
        """Send request to self.url resource

        :return: `Response` object
        """

        try:
            opener = self.build_opener()
            opener.perform()
            # if close before getinfo, raises pycurl.error can't invote getinfo()
        except pycurl.error as e:
            raise CurlError(e.args[0], e.args[1])
        else:
            self.response = self.make_response()

        return self.response

    def make_response(self):
        """Make response from finished opener

        :return response: :class:`Response` object
        """
        response = Response(url=self.url, curl_opener=self._opener,
                            body_output=self.body_output,
                            headers_output=self.headers_output, request=self,
                            cookies=self._cookies)
        return response

    def setup_netrc(self, opener):
        """Setup netrc file

        :paramt opener: :class:`pycurl.Curl` object
        """
        if self._netrc:
            opener.setopt(pycurl.NETRC, 1)

        if self._netrc_file and file_exists(self._netrc_file):
            opener.setopt(pycurl.NETRC_FILE, self._netrc_file)


    @staticmethod
    def clean_opener(opener):
        """Reset opener options

        :param opener: :class:`pycurl.Curl` object
        :return opener: clean :`pycurl.Curl` object
        """
        opener.reset()
        return opener

    def build_opener(self, opener=None):
        """Compile pycurl.Curl instance

        Compile `pycurl.Curl` instance with given instance settings
        and return `pycurl.Curl` configured instance, Writable file like
        instances of body_output and headers_output

        :param url: resource url
        :return: an ``(opener, body_output, headers_output)`` tuple.
        """
        # http://curl.haxx.se/mail/curlpython-2005-06/0004.html
        # http://curl.haxx.se/mail/lib-2010-03/0114.html
        opener = opener or pycurl.Curl()
        url = self.url

        if getattr(opener, "dirty", True):
            opener = self.clean_opener(opener)

        opener.setopt(pycurl.URL, url)
        opener.setopt(pycurl.NOSIGNAL, 1)


        if isinstance(self._auth, AuthManager):
            self._auth.setup_request(self)
            self._auth.setup(opener)
        elif self._netrc:
            self.setup_netrc(opener)
        else:
            opener.unsetopt(pycurl.USERPWD)

        if self._headers:
            opener.setopt(pycurl.HTTPHEADER, ["%s: %s" % (f, v) for f, v
                                              in CaseInsensitiveDict(self._headers).items()])

        # Option -L  Follow  "Location: "  hints
        if self._allow_redirects is True:
            opener.setopt(pycurl.FOLLOWLOCATION, self._allow_redirects)
            if self._max_redirects:
                opener.setopt(pycurl.MAXREDIRS, self._max_redirects)

        # Set timeout for a retrieving an object
        if self._timeout is not None:
            opener.setopt(pycurl.TIMEOUT, self._timeout)
        if self._connection_timeout is not None:
            opener.setopt(pycurl.CONNECTTIMEOUT, self._connection_timeout)

        # Setup debug output write function
        if callable(self._debug_curl):
            opener.setopt(pycurl.VERBOSE, 1)
            opener.setopt(pycurl.DEBUGFUNCTION, self._debug_curl)
        elif self._debug_curl is True:
            opener.setopt(pycurl.VERBOSE, 1)
            opener.setopt(pycurl.DEBUGFUNCTION, logger_debug)
        else:
            opener.setopt(pycurl.VERBOSE, 0)

        # Send allow gzip encoding header
        if self._use_gzip is not None:
            opener.setopt(pycurl.ENCODING, "gzip,deflate")

        # Specify network interface (ip address) for query
        if self._network_interface is not None:
            opener.setopt(pycurl.INTERFACE, self._network_interface)

        # Setup proxy for request
        if self._proxy is not None:
            if len(self._proxy) > 2:
                proxy_type, proxy_addr, proxy_auth = self._proxy
            else:
                proxy_type, proxy_addr = self._proxy
                proxy_auth = None

            opener.setopt(pycurl.PROXY, proxy_addr[0])
            opener.setopt(pycurl.PROXYPORT, proxy_addr[1])
            opener.setopt(pycurl.PROXYTYPE, get_code_by_name(proxy_type))

            if proxy_type.upper() in ("CONNECT", "SSL", "HTTPS"):
                # if CONNECT proxy, need use HTTPPROXYTINNEL
                opener.setopt(pycurl.HTTPPROXYTUNNEL, 1)
            if proxy_auth:
                if len(proxy_auth) == 2:
                    opener.setopt(pycurl.PROXYUSERPWD, "%s:%s" % proxy_auth)
                else:
                    raise InterfaceError("Proxy auth data must be tuple")

        opener.setopt(pycurl.USERAGENT, self.user_agent)

        if self._validate_cert not in (None, False):
            # Verify that we've got the right site; harmless on a non-SSL connect.
            opener.setopt(pycurl.SSL_VERIFYPEER, 1)
            opener.setopt(pycurl.SSL_VERIFYHOST, 2)
        else:
            opener.setopt(pycurl.SSL_VERIFYPEER, 0)
            opener.setopt(pycurl.SSL_VERIFYHOST, 0)

        if self._ca_certs is not None:
            logger.debug("Use ca cert %s" % self._ca_certs)
            if file_exists(self._ca_certs):
                opener.setopt(pycurl.CAINFO, self._ca_certs)

        ## (HTTPS) Tells curl to use the specified certificate file when getting a
        ## file with HTTPS. The certificate must be in PEM format.
        ## If the optional password isn't specified, it will be queried for on the terminal.
        ## Note that this certificate is the private key and the private certificate concatenated!
        ## If this option is used several times, the last one will be used.
        if self._cert:
            opener.setopt(pycurl.SSLCERT, self._cert)

        if self._ip_v6:
            opener.setopt(pycurl.IPRESOLVE, pycurl.IPRESOLVE_WHATEVER)
        else:
            opener.setopt(pycurl.IPRESOLVE, pycurl.IPRESOLVE_V4)

        # opener.setopt(c.NOPROGRESS, 0)
        # opener.setopt(c.PROGRESSFUNCTION, self._progress_callback)

        # Add cookies from self._cookies
        if self._cookies is not None:
            chunks = []
            for cookie in self._cookies:
                name, value = cookie.name, cookie.value
                ## if isinstance(name, unicode):
                ##     name = name.encode("utf-8")
                ## if isinstance(value, unicode):
                ##     value = value.encode("utf-8")
                name = quote_plus(name)
                value = quote_plus(value)
                chunks.append('%s=%s;' % (name, value))
            if chunks:
                opener.setopt(pycurl.COOKIE, ' '.join(chunks))
        else:
            # set empty cookie to activate cURL cookies
            opener.setopt(pycurl.COOKIELIST, '')

        curl_options = {
            "GET": pycurl.HTTPGET,
            "POST": pycurl.POST,
            # "PUT": pycurl.UPLOAD,
            "PUT": pycurl.PUT,
            "HEAD": pycurl.NOBODY}

        if self._method in curl_options.values():
            opener.setopt(curl_options[self._method], True)
        elif self._method in self.SUPPORTED_METHODS:
            opener.setopt(pycurl.CUSTOMREQUEST, self._method)
        else:
            raise InvalidMethod("cURL request do not support %s" %
                                self._method)

        # Responses without body
        if self._method in ("OPTIONS", "HEAD", "DELETE"):
            opener.setopt(pycurl.NOBODY, True)
        if self._method in ("POST", "PUT"):

            if self._files is not None:
                post_params = self._files
                if isinstance(self._data, (tuple, list, dict)):
                    post_params.extend(data_wrapper(self._data))
                opener.setopt(opener.HTTPPOST, post_params)
            else:
                if isinstance(self._data, str):
                    self._data = self._data.encode('utf8')
                if isinstance(self._data, bytes):
                    request_buffer = BytesIO(self._data)

                    # raw data for body request
                    opener.setopt(pycurl.READFUNCTION, request_buffer.read)
                    def ioctl(cmd):
                        logger.debug(("cmd", cmd))
                        if cmd == pycurl.IOCMD_RESTARTREAD:
                            request_buffer.seek(0)

                    opener.setopt(pycurl.IOCTLFUNCTION, ioctl)
                    if self._method == "PUT":
                        opener.setopt(pycurl.PUT, True)
                        opener.setopt(pycurl.INFILESIZE, len(self._data))
                    else:
                        opener.setopt(pycurl.POST, True)
                        opener.setopt(pycurl.POSTFIELDSIZE, len(self._data))
                elif isinstance(self._data, (tuple, list, dict)):
                    headers = dict(self._headers or [])
                    if 'multipart' in headers.get('Content-Type', ''):
                        # use multipart/form-data;
                        opener.setopt(opener.HTTPPOST, data_wrapper(self._data))
                    else:
                        # use postfields to send vars as application/x-www-form-urlencoded
                        encoded_data = urlencode(self._data, doseq=True)
                        opener.setopt(pycurl.POSTFIELDS, encoded_data)

        if isinstance(self._options, (tuple, list)):
            for key, value in self._options:
                opener.setopt(key, value)


        self.body_output = BytesIO()
        self.headers_output = BytesIO()

        opener.setopt(pycurl.HEADERFUNCTION, self.headers_output.write)
        opener.setopt(pycurl.WRITEFUNCTION, self.body_output.write)

        self._opener = opener

        return opener





class Response(object):
    """Response object
    """

    def __init__(self, url, curl_opener, body_output, headers_output,
                 request=None, cookies=None):
        """
        Arguments:
        :param url: resource url
        :param curl_opener: :class:`pycurl.Curl` object
        :param body_output: BytesIO instance
        :param headers_output: : BytesIO instance
        :param request: :class:`Request` instance
        :param cookies_jar: :class:`CookieJar` instance
        """

        # Requested url
        self._request_url = url
        self._url = None

        # Request object
        self._request = request

        # Response headers
        self._headers = None

        self._text = None
        self._encoding=None

        # Cookies dictionary
        self._cookies = None
        if isinstance(cookies, CookieJar):
            self._cookies_jar = cookies
        elif isinstance(cookies, (tuple, dict)):
            self._cookies_jar = to_cookiejar(cookies)
        else:
            self._cookies_jar = None

        # Seconds from request start to finish
        self.request_time = None
        self._curl_opener = curl_opener

        # BytesIO object for response body
        self._body_otput = body_output
        # BytesIO object for response headers
        self._headers_output = headers_output

        # :Response status code
        self._status_code = None

        # Unziped end decoded response body
        self._content = None

        # Redirects history
        self._history = []

        # list of parsed headers blocks
        self._headers_history = []

        # get data from curl_opener.getinfo before curl_opener.close()
        self._metrics = None


    def __repr__(self):
        return "<%s: %s >" % (self.__class__.__name__, self.status_code)


    def _get_metrics(self):
        creq = self._curl_opener
        self._metrics = {
            'redirect_count': creq.getinfo(pycurl.REDIRECT_COUNT),
            'effective_url': creq.getinfo(pycurl.EFFECTIVE_URL),
            'response_code': creq.getinfo(pycurl.RESPONSE_CODE),
            'dns_time': creq.getinfo(pycurl.NAMELOOKUP_TIME),
            'connect_time': creq.getinfo(pycurl.CONNECT_TIME),
            'tls_time': creq.getinfo(pycurl.APPCONNECT_TIME),
            'transfer_start_time': creq.getinfo(pycurl.PRETRANSFER_TIME),
            'first_byte_time': creq.getinfo(pycurl.STARTTRANSFER_TIME),
            'redirect_time': creq.getinfo(pycurl.REDIRECT_TIME),
            'total_time': creq.getinfo(pycurl.TOTAL_TIME),
        }

    @property
    def metrics(self):
        if self._metrics is None:
            self._get_metrics()
        return self._metrics

    @property
    def request(self):
        return self._request

    @property
    def url(self):
        if not self._url:
            self._url = self._curl_opener.getinfo(pycurl.EFFECTIVE_URL)
        return self._url

    @property
    def status_code(self):
        if not self._status_code:
            self._status_code = int(self._curl_opener.getinfo(pycurl.HTTP_CODE))
        return self._status_code

    @property
    def content(self):
        """Returns decoded self._content
        """
        import zlib
        if not self._content:
            if 'gzip' in self.headers.get('Content-Encoding', '') and \
                   'zlib' not in pycurl.version:
                try:
                    self._content = decode_gzip(self._body_otput.getvalue())
                except zlib.error:
                    pass
            else:
                self._content = self._body_otput.getvalue()
        return self._content

    @property
    def encoding(self):
        if self._encoding is None:
            if 'content-type' in self.headers and 'charset=' in self.headers['content-type']:
                self._encoding = self.headers['content-type'].split('charset=', 1)[1].split(';', 1)[0]
            else:
                self._encoding = chardet.detect(self.content)['encoding']
            if self._encoding is None:
                self._encoding = "utf-8"
        return self._encoding

    @encoding.setter
    def encoding_setter(self, value):
        self._encoding = value

    @property
    def text(self):
        if self._text is None:
            self._text = self.content.decode(self.encoding)
        return self._text

    def json(self):
        """Returns the json-encoded content of a response
        """
        try:
            return json.loads(self.text)
        except ValueError:
            return None

    def _parse_headers_raw(self):
        header_text = self._headers_output.getvalue().decode('ISO-8859-1')
        lines = header_text.split('\r\n')
        headers = []
        for line in lines:
            if line == "":
                if headers:
                    self._headers_history.append(headers)
                headers = []
                continue
            elif line.startswith('HTTP/'):
                continue
            else:
                key, value = line.split(': ', 1)
                if key == 'Location':
                    self._history.append(value)
                headers.append((key, value.strip()))
        self._headers = CaseInsensitiveDict(self._headers_history[-1])

    def _parse_cookies(self):
        if self._cookies is None:
            self._cookies = CookieJar()

        for key, value in self.headers.items():
            if key.lower() == 'set-cookie':
                for morsel in SimpleCookie(value).values():
                    cookie = morsel_to_cookie(morsel)
                    self._cookies.set_cookie(cookie)

    @property
    def headers(self):
        """Returns response headers
        """
        if not self._headers:
            self._parse_headers_raw()
        return self._headers

    @property
    def cookie_jar(self):
        if not self._cookies:
            self._parse_cookies()
        return self._cookies

    @property
    def cookie_list(self):
        return list(self.cookie_jar)

    @property
    def cookies(self):
        return {c.name: c for c in self.cookie_jar}

    @property
    def history(self):
        """Returns redirects history list

        :return: list of `Response` objects
        """
        if not self._history:
            self._parse_headers_raw()
        return self._history

    def _extract_embeded_urls(self):
        soup = BeautifulSoup(self.text)
        urllib.parse.urljoin(resp.url, 'http://test.com/jordan.html')
        base_url = self.url
        for burl in soup.find_all('base', {'href': True}):
            base_url = burl.attrs['href'] # reset the base url to the one in the page
        for elem in soup.find_all(True, attrs={'background': True}):
            yield urljoin(base_url, elem.attrs['background'])
        for elem in soup.find_all(['script', 'img', 'frame', 'iframe', 'embed', 'bgsound'], attrs={'src': True}):
            yield urljoin(base_url, elem.attrs['src'])
        for elem in soup.find_all('link', attrs={'rel': 'stylesheet', 'href': True}):
            yield urljoin(base_url, elem.attrs['href'])
        for elem in soup.find_all('input', attrs={'type': 'image', 'href': True}):
            yield urljoin(base_url, elem.attrs['href'])


"""
        base.href - replaces base url

        body.background
        script.src
        image.src
        applet.code
        object.codebase
        object.data
        input.type == 'image' then input.src
        script.src
        frame.src
        iframe.src
        embed.src
        bgsound.src
        link.rel == 'stylesheet' then link.href
        .background
        .style - extract URL\(["'](.*)\["'])
"""
