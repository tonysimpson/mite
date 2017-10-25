from collections import namedtuple


class KeyedMetricsCounter:
    def __init__(self):
        self._metrics = {}
    
    def inc(self, key):
        if key not in self._metrics:
            self._metrics[key] = 1
        else:
            self._metrics[key] += 1

    def iter_counts(self):
        for key, value in sorted(self._metrics.items()):
            yield key, value


class KeyedMetricsSumCounter:
    def __init__(self):
        self._metrics = {}
    
    def add(self, key, value):
        if key not in self._metrics:
            self._metrics[key] = value
        else:
            self._metrics[key] += value

    def iter_counts(self):
        for key, value in sorted(self._metrics.items()):
            yield key, value


class KeyedHistogram:
    def __init__(self, bins):
        self._bin_counts = {}
        self._sums = {}
        self._total_counts = {}
        self._bins = bins

    def add(self, key, value):
        if key not in self._bin_counts:
            bins = [0 for _ in self._bins]
            self._bin_counts[key] = bins
            self._sums[key] = value
            self._total_counts[key] = 1
        else:
            bins = self._bin_counts[key]
            self._sums[key] += value
            self._total_counts[key] += 1
        for i, bin_value in enumerate(self._bins):
            if value <= bin_value:
                bins[i] += 1

    def iter_histograms(self):
        for key, bin_counts in sorted(self._bin_counts.items()):
            _sum = self._sums[key]
            _total_count = self._total_counts[key]
            yield key, _sum, _total_count, zip(self._bins, bin_counts)


_response_key = namedtuple('_response_key', 'test journey transaction method code'.split())
_error_key = namedtuple('_error_key', 'test journey transaction'.split())


class MetricsProcessor:
    def __init__(self):
        self._error_counter = KeyedMetricsCounter()
        self._response_counter = KeyedMetricsCounter()
        self._dns_time_sum_counter = KeyedMetricsSumCounter()
        self._connect_time_sum_counter = KeyedMetricsSumCounter()
        self._tls_time_sum_counter = KeyedMetricsSumCounter()
        self._response_histogram = KeyedHistogram([0.00001, 0.0001, 0.001,
            0.01, 0.05, 0.1, 0.15, 0.2, 0.4, 0.6, 0.8, 1, 2, 4, 8, 16])

    def process_message(self, msg):
        if 'type' not in msg:
            return
        msg_type = msg['type']
        if msg_type == 'http_curl_metrics':
            key = _response_key(
                msg.get('test', ''),
                msg.get('journey', ''),
                msg.get('transation', ''),
                msg['method'],
                msg['response_code']
            )
            self._response_counter.inc(key)
            self._response_histogram.add(key, msg['total_time'])
            #self._dns_time_sum.add(key, msg['dns_time'])
            #self._connect_time_sum.add(key, msg['connect_time'] - msg['dns_time'])
            #self._tls_time_sum.add(key, msg['tls_time'] - msg['connect_time'])
        elif msg_type == 'exception' or msg_type == 'error':
            key = _error_key(
                msg.get('test', ''),
                msg.get('journey', ''),
                msg.get('transation', ''),
            )
            self._error_counter.inc(key)

    def prometheus_metrics(self):
        def format_dict(d):
            return ','.join(['%s="%s"' % (k,v) for k,v in d.items()])
        lines = []
        lines.append('# TYPE mite_http_response_total counter')
        for key, value in self._response_counter.iter_counts():
            lines.append('mite_http_response_total {%s} %s' % (format_dict(key._asdict()), value))
        lines.append('')
        lines.append('# TYPE mite_journey_error_total counter')
        for key, value in self._error_counter.iter_counts():
            lines.append('mite_journey_error_total {%s} %s' % (format_dict(key._asdict()), value))
        lines.append('')
        lines.append('# TYPE mite_http_response_time_seconds histogram')
        for key, _sum, _total_count, bin_counts in  self._response_histogram.iter_histograms():
            labels = format_dict(key._asdict())
            for bin_value, bin_count in bin_counts:
                lines.append('mite_http_response_time_seconds_bucket{%s,le="%.6f"} %d' % (labels, bin_value, bin_count))
            lines.append('mite_http_response_time_seconds_bucket{%s,le="+Inf"} %d' % (labels, _total_count))
            lines.append('mite_http_response_time_seconds_sum{%s} %.6f' % (labels, _sum))
            lines.append('mite_http_response_time_seconds_count{%s} %d' % (labels, _total_count))
        lines.append('')
        return '\n'.join(lines)


