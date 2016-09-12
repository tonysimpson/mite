import pycurl
import asyncio
import urllib
from io import BytesIO
import time
import logging
from functools import partial
import select
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
    }



class session:
    def __init__(self, controller, multi, profile, metrics_callback=None):
        self._shared_handle = pycurl.CurlShare()
        self._shared_handle.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_COOKIE)
        self._shared_handle.setopt(pycurl.SH_SHARE, pycurl.LOCK_DATA_DNS)
        self._metrics_callback = metrics_callback
        self._profile = profile
        self._controller = controller
        self._multi = multi

    async def request(self, method, url, *args, **kwargs):
        request = Request(method, url, *args, **kwargs)
        if self._metrics_callback is not None:
            metrics = {'time': time.time(), 'method': method, 'url': url}
        opener = pycurl.Curl()
        opener.setopt(pycurl.SHARE, self._shared_handle)
        creq = request.build_opener(opener)
        await self._controller.perform(self._multi, creq)
        if self._metrics_callback is not None:
            metrics.update(get_metrics(creq))
            self._metrics_callback(metrics)
        return request.make_response()

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


class BaseProfile:
    connections_per_host = 6
    max_connections = None
    connection_timeout = 60
    user_agent = None


class RequestError(Exception):
    pass


class SessionController:
    def __init__(self):
        self._epoll = asyncio.selectors.EpollSelector()
        self._registered = set()
        self._socket_multi_map = {}
        self._perform_running = False
        self._futures = {}
        self._loop = asyncio.get_event_loop()

    def _socket_poll_register_or_modify(self, socket, multi, mask):
        if socket in self._registered:
            self._epoll.modify(socket, mask)
        else:
            self._epoll.register(socket, mask)
            self._registered.add(socket)
            self._socket_multi_map[socket] = multi
        if not self._perform_running:
            asyncio.ensure_future(self._perform())

    def _socket_poll_none(self, multi, socket):
        self._epoll.register(socket)
        self._registered.add(socket)
        self._socket_multi_map[socket] = multi
        if not self._perform_running:
            asyncio.ensure_future(self._perform())

    def _socket_poll_in(self, multi, socket):
        self._socket_poll_register_or_modify(socket, multi, select.EPOLLIN)

    def _socket_poll_out(self, multi, socket):
        self._socket_poll_register_or_modify(socket, multi, select.EPOLLOUT)

    def _socket_poll_in_out(self, multi, socket):
        self._socket_poll_register_or_modify(socket, multi,
                                             select.EPOLLIN |
                                             select.EPOLLOUT)

    def _socket_poll_remove(self, multi, socket):
        self._epoll.unregister(socket)
        self._registered.remove(socket)
        del self._socket_multi_map[socket]

    def _socket_call_back(self, event, socket, multi, data):
        if event == pycurl.POLL_NONE:
            self._socket_poll_none(multi, socket)
        elif event == pycurl.POLL_IN:
            self._socket_poll_in(multi, socket)
        elif event == pycurl.POLL_OUT:
            self._socket_poll_out(multi, socket)
        elif event == pycurl.POLL_INOUT:
            self._socket_poll_in_out(multi, socket)
        elif event == pycurl.POLL_REMOVE:
            self._socket_poll_remove(multi, socket)
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
            future.set_exception(RequestError(error_msg))
            errored.close()
            multi.remove_handle(errored)

    async def _perform(self):
        assert not self._perform_running
        self._perform_running = True
        while self._registered:
            multis_to_finish = set()
            for fd, event in self._epoll.select():
                multi = self._socket_multi_map[fd.fd]
                ev_bitmask = 0
                if event & select.EPOLLIN:
                    ev_bitmask |= pycurl.CSELECT_IN
                if event & select.EPOLLOUT:
                    ev_bitmask |= pycurl.CSELECT_OUT
                if event & select.EPOLLERR:
                    ev_bitmask |= pycurl.CSELECT_ERR
                code, remaining = multi.socket_action(fd.fd, ev_bitmask)
                multis_to_finish.add(multi)
            for multi in multis_to_finish:
                self._finish(multi)
        self._perform_running = False

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

