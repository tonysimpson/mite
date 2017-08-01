import datetime


def can_cache(request, response):
    if 'Cache-Control' in request.headers:
        if 'no-store' in request.headers['Cache-Control']:
            return False
    if 'Cache-Control' in response.headers:
        if 'no-store' in response.headers:
            return False
    return True




def calculate_expires(response, time_now):

        





class Cache:
    MISSING_STATUS = 1
    FRESH_STATUS   = 2
    STALE_STATUS   = 3

    def cache_status(self, request, time_now):
        if request.method not in self._cachable_methods:
            return Cache.MISSING_STATUS
        else:
            return self._get_cache_status(request, time_now)

    def add_conditional_headers(self, request):
        

    def get_response(self, request):
        entry = self._get_entry(request)
        return entry.response
    
    def possibly_cache(self, request, response, time_now):
        pass

    def _get_entry(self, request):
        key = (request.method, request.url)
        entry = self._entries.get(key)
        if entry is not None and entry.varies is not None:
            key = self._varies_key(entry.varies, request)
            entry = self._entries.get(key)
	return entry

    def _get_cache_status(self, request, time_now):
        entry = self._get_entry(request)
        if entry is None:
            return Cache.MISSING_STATUS
        if entry.expires_time < time_now:
            return Cache.STALE_STATUS
        elif entry.no_cache:
            return Cache.STALE_STATUS
        else:
            return Cache.FRESH





