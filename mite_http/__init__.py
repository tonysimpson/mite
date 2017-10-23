from collections import deque
from acurl import EventLoop

class _SessionPoolContextManager:
    def __init__(self, session_pool, context):
        self._session_pool = session_pool
        self._context = context

    async def __aenter__(self):
        self._context.http = await self._session_pool._checkout(self._context)
    
    async def __aexit__(self, *args):
        await self._session_pool._checkin(self._context.http)
        del self._context.http


class SessionPool:
    def __init__(self):
        self._el = EventLoop()
        self._pool = deque()

    def session_context(self, context):
        return _SessionPoolContextManager(self, context)

    def decorator(self, func):
        async def wrapper(ctx, *args, **kwargs):
            with self.session_context(ctx):
                return await func(ctx, *args, **kwargs)
        return wrapper

    async def _checkout(self, context):
        if self._pool:
            session = self._pool.pop()
        else:
            session = self._el.session()
            session._real_request = session._request
        async def _wrapped_request(*args, **kwargs):
            r = await session._real_request(*args, **kwargs)
            context.send('http_curl_metrics', 
                time=r.start_time, 
                effective_url=r.url, 
                response_code=r.status_code,
                dns_time=r.namelookup_time,
                connect_time=r.connect_time,
                tls_time=r.appconnect_time,
                transfer_start_time=r.pretransfer_time,
                first_byte_time=r.starttransfer_time,
                total_time=r.total_time,
                primary_ip=r.primary_ip,
                method=r.request.method
            )
            return r
        session._request = _wrapped_request
        return session

    async def _checkin(self, session):
        await session.erase_all_cookies()
        self._pool.append(session)


def get_session_pool():
    if not hasattr(get_session_pool, '_session_pool'):
        get_session_pool._session_pool = SessionPool()
    return get_session_pool._session_pool


