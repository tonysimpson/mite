import logging
import time


class HttpStatsLogger:
    def __init__(self, period=10):
        self._period = period
        self._logger = logging.getLogger('Http Stats')
        self._start_t = None
        self._req_total = 0
        self._req_recent = 0
        self._error_total = 0
        self._error_recent = 0
        self._resp_time_recent = []

    def _pct(self, percentil):
        if not self._resp_time_recent:
            return "None"
        assert 0 <= percentil <= 100
        index = ((percentil/100) * (len(self._resp_time_recent)-1))
        low_index = int(index)
        offset = index % 1
        print(index, low_index, offset, len(self._resp_time_recent))
        if offset == 0:
            return "%.6f" % (self._resp_time_recent[low_index],)
        else:
            a = self._resp_time_recent[low_index]
            b = self._resp_time_recent[low_index + 1]
            iterpalated_amount = (b - a) * offset
            return "%.6f" % (a + iterpalated_amount,)

    def process_message(self, message):
        if 'type' not in message:
            return
        msg_type = message['type']
        t = time.time()
        if self._start_t is None:
            self._start_t = t
        if self._start_t + self._period < t:
            dt = t - self._start_t
            self._resp_time_recent.sort()
            self._logger.info('Total> #Reqs:%d #Errs:%d', self._req_total, self._error_total)
            self._logger.info('Last %d Secs> #Reqs:%d #Errs:%d Req/S:%.6f min:%s 25%%:%s 50%%:%s 75%%:%s 90%%:%s 99%%:%s 99.9%%:%s 99.99%%:%s max:%s',
                self._period,
                self._req_recent, 
                self._error_recent, 
                self._req_recent / dt,
                self._pct(0), 
                self._pct(25),
                self._pct(50),
                self._pct(75),
                self._pct(90),
                self._pct(99),
                self._pct(99.9),
                self._pct(99.99),
                self._pct(100)
            )
            self._start_t = t
            del self._resp_time_recent[:]
            self._req_recent = 0
            self._error_recent = 0
        if msg_type == 'http_curl_metrics':
            self._resp_time_recent.append(message['total_time'])
            self._req_total += 1
            self._req_recent += 1
        elif msg_type in ('error', 'exception'):
            self._error_total += 1
            self._error_recent += 1

            


        
