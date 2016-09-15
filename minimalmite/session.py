import pycurl
import asyncio
import selectors
import urllib
from io import BytesIO
import time
import logging
from functools import partial
from human_curl import Request


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



class session:
    def __init__(self, controller, multi, profile=None, metrics_callback=None):
        self._shared_handle = pycurl.CurlShare()
        self._shared_handle.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_COOKIE)
        self._shared_handle.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_DNS)
        self._metrics_callback = metrics_callback
        if profile is None:
            profile = BaseProfile()
        self._profile = profile
        self._controller = controller
        self._multi = multi

    async def request(self, method, url, *args, **kwargs):
        request = Request(method, url, user_agent=self.user_agent, *args, **kwargs)
        if self._metrics_callback is not None:
            metrics = {'time': time.time(), 'method': method, 'url': url}
        opener = pycurl.Curl()
        if self._profile.dns_servers is not None:
            opener.setopt(pycurl.DNS_SERVERS, self._profile.dns_servers)
        opener.setopt(pycurl.SHARE, self._shared_handle)
        creq = request.build_opener(opener)
        await self._controller.perform(self._multi, creq)
        if self._metrics_callback is not None:
            metrics.update(get_metrics(creq))
            self._metrics_callback(metrics)
        return request.make_response()

    @property
    def user_agent(self):
        return self._profile.user_agent

    @user_agent.setter
    def user_agent_setter(self, value):
        self._profile.user_agent = value

    def _close(self):
        if self._shared_handle is not None:
            self._shared_handle.close()
            self._shared_handle = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self._close()

    def __del__(self):
        self._close()



class RequestError(Exception):
    pass



_PYCURL_ERROR_CODES = {getattr(pycurl, name): name[2:] for name in dir(pycurl) if name.startswith('E_')}


class SessionController:
    def __init__(self):
        self._futures = {}
        self._loop = asyncio.get_event_loop()

    def _socket_event_call_back(self, multi, fd, bitmask):
        code, remaining = multi.socket_action(fd, bitmask)
        self._finish(multi)

    def _socket_call_back(self, event, socket, multi, data):
        if event == pycurl.POLL_NONE:
            print('What do POLL_NONE')
        elif event == pycurl.POLL_IN:
            self._loop.add_reader(socket, self._socket_event_call_back, multi, socket, pycurl.CSELECT_IN)
        elif event == pycurl.POLL_OUT:
            self._loop.add_writer(socket, self._socket_event_call_back, multi, socket, pycurl.CSELECT_OUT)
        elif event == pycurl.POLL_INOUT:
            self._loop.add_reader(socket, self._socket_event_call_back, multi, socket, pycurl.CSELECT_IN)
            self._loop.add_writer(socket, self._socket_event_call_back, multi, socket, pycurl.CSELECT_OUT)
        elif event == pycurl.POLL_REMOVE:
            self._loop.remove_reader(socket)
            self._loop.remove_writer(socket)
        else:
            raise ValueError("unhandled event type %r" % event)
 
    def _finish(self, multi):
        num_msgs, successes, errors = multi.info_read()
        for success in successes:
            future = self._futures.pop(success)
            future.set_result(success)
            multi.remove_handle(success)
        for errored, error_num, error_msg in errors:
            future = self._futures.pop(errored)
            future.set_exception(RequestError("Error for %r - %r" % (errored, _PYCURL_ERROR_CODES[error_num])))
            errored.close()
            multi.remove_handle(errored)

    def _timeout(self, multi):
        ret, num_handles = multi.socket_action(pycurl.SOCKET_TIMEOUT, 0)
        self._finish(multi)

    def _timer_call_back(self, multi, milliseconds):
        if milliseconds >= 0:
            self._loop.call_later(milliseconds / 1000, self._timeout, multi)

    def create_new_session(self, profile=None, metrics_callback=None):
        multi = pycurl.CurlMulti()
        multi.setopt(pycurl.M_SOCKETFUNCTION, self._socket_call_back)
        multi.setopt(pycurl.M_TIMERFUNCTION, partial(self._timer_call_back, multi))
        return session(self, multi, profile, metrics_callback)

    def perform(self, multi, handle):
        future = asyncio.Future()
        self._futures[handle] = future
        multi.add_handle(handle)
        self._timeout(multi)
        return future

