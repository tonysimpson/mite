import pycurl
import asyncio
import time
import logging
from human_curl import Request
import weakref


logger = logging.getLogger(__name__)


def get_metrics(creq):
    return {
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
        'primary_ip': creq.getinfo(pycurl.PRIMARY_IP),
    }


class BaseProfile:
    connections_per_host = 6
    max_connections = None
    connection_timeout = 60
    user_agent = None
    dns_servers = None


class RequestError(Exception):
    pass


_PYCURL_ERROR_CODES = {getattr(pycurl, name): name[2:] for name in dir(pycurl) if name.startswith('E_') and not name.startswith('E_MULTI_')}



class WeakRefUnboundMethodProxy:
    def __init__(self, proxied_self, unbound_method):
        self.proxied_self_ref = weakref.ref(proxied_self)
        self.unbound_method = unbound_method

    def __call__(self, *args, **kwargs):
        return self.unbound_method(self.proxied_self_ref(), *args, **kwargs)


class Session:
    def __init__(self, headers=None, cookies=None, user_agent=None, dns_servers=None, profile=None, metrics_callback=None, loop=None,):
        if headers is None:
            headers = {}
        self.headers = headers
        if cookies is None:
            cookies = {}
        self.cookies = cookies
        self.dns_servers = dns_servers
        self.user_agent = user_agent
        if loop is None:
            loop = asyncio.get_event_loop()
        self._loop = loop
        self._metrics_callback = metrics_callback
        self._futures = {}
        self._done = None
        self._timeout_handle = None
        self._multi = pycurl.CurlMulti()
        self._multi.setopt(pycurl.M_SOCKETFUNCTION, WeakRefUnboundMethodProxy(self, Session._socket_call_back))
        self._multi.setopt(pycurl.M_TIMERFUNCTION, WeakRefUnboundMethodProxy(self, Session._timer_call_back))
        self._working = False
        self._shared_handle = pycurl.CurlShare()
        self._shared_handle.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_COOKIE)
        self._shared_handle.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_DNS)
        self._num_handles = 0

    def done(self):
        return self._done is None or self._done.done()

    async def wait_for_done(self):
        if not self.done():
            await self._done

    async def request(self, method, url, **kwargs):
        headers =  dict(self.headers)
        headers.update(kwargs.get('headers', {}))
        if self.user_agent is not None:
            headers['User-Agent'] = self.user_agent
        if headers:
            kwargs['headers'] = headers
        cookies = dict(self.cookies)
        cookies.update(kwargs.get('cookies', {}))
        if cookies:
            kwargs['cookies'] = cookies
        request = Request(method, url, **kwargs)
        if self._metrics_callback is not None:
            metrics = {'time': time.time(), 'method': method, 'url': url}
        opener = pycurl.Curl()
        if self.dns_servers is not None:
            opener.setopt(pycurl.DNS_SERVERS, self.dns_servers)
        opener.setopt(pycurl.SHARE, self._shared_handle)
        creq = request.build_opener(opener)
        await self._perform(creq)
        if self._metrics_callback is not None:
            metrics.update(get_metrics(creq))
            self._metrics_callback(metrics)
        return request.make_response()

    def _shutdown(self):
        self._done.set_result(None)
        if self._timeout_handle is not None:
            self._timeout_handle.cancel()
            self._timeout_handle = None
        self._working = False

    def _socket_action(self, fd, bitmask):
        code, num_handles = self._multi.socket_action(fd, bitmask)
        if self._num_handles > num_handles:
            self._finish()
        self._num_handles = num_handles
        if num_handles == 0:
            self._shutdown()

    def _finish(self):
        num_msgs, successes, errors = self._multi.info_read()
        for success in successes:
            future = self._futures.pop(success)
            future.set_result(success)
            self._multi.remove_handle(success)
        for errored, error_num, error_msg in errors:
            future = self._futures.pop(errored)
            future.set_exception(RequestError("Error for %r - %r" % (errored, _PYCURL_ERROR_CODES[error_num])))
            errored.close()
            self._multi.remove_handle(errored)

    def _socket_call_back(self, event, socket, multi, data):
        if event == pycurl.POLL_IN:
            self._loop.add_reader(socket, self._socket_action, socket, pycurl.CSELECT_IN)
        elif event == pycurl.POLL_OUT:
            self._loop.add_writer(socket, self._socket_action, socket, pycurl.CSELECT_OUT)
        elif event == pycurl.POLL_INOUT:
            self._loop.add_reader(socket, self._socket_action, socket, pycurl.CSELECT_IN)
            self._loop.add_writer(socket, self._socket_action, socket, pycurl.CSELECT_OUT)
        elif event == pycurl.POLL_REMOVE:
            self._loop.remove_reader(socket)
            self._loop.remove_writer(socket)
        else:
            raise AssertionError("unhandled event type %r" % event)

    def _timeout(self):
        self._socket_action(pycurl.SOCKET_TIMEOUT, 0)

    def _timer_call_back(self, milliseconds):
        if self._timeout_handle is not None:
            self._timeout_handle.cancel()
            self._timeout_handle = None
        if milliseconds >= 0:
            self._timeout_handle = self._loop.call_later(milliseconds / 1000, self._timeout)

    def _perform(self, handle):
        future = asyncio.Future()
        self._futures[handle] = future
        self._multi.add_handle(handle)
        self._num_handles += 1
        if self.done():
            self._done = asyncio.Future()
            self._timeout()
        return future
