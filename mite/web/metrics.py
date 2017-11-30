from collections import namedtuple
import time


class Counter:
    def __init__(self, labels):
        self._labels = labels
        self._metrics = {}
    
    def inc(self, key):
        if key not in self._metrics:
            self._metrics[key] = 1
        else:
            self._metrics[key] += 1

    def iter_counts(self):
        for key, value in sorted(self._metrics.items()):
            yield dict(zip(self._labels, key)), value


class Gauge:
    def __init__(self, labels):
        self._labels = labels
        self._metrics = {}
    
    def change_by(self, key, value):
        if key not in self._metrics:
            self._metrics[key] = value
        else:
            self._metrics[key] += value
    
    def set(self, key, value):
        self._metrics[key] = value

    def iter_counts(self):
        for key, value in sorted(self._metrics.items()):
            yield dict(zip(self._labels, key)), value


class Histogram:
    def __init__(self, labels, bins):
        self._labels = labels
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
            yield dict(zip(self._labels, key)), _sum, _total_count, zip(self._bins, bin_counts)

class MetricsProcessor:
    def __init__(self):
        self._error_counter = Counter('test journey transaction location message'.split())
        transaction_key = 'test journey transaction'.split()
        self._transaction_start_counter = Counter(transaction_key)
        self._transaction_end_counter = Counter(transaction_key)
        self._transaction_count_gauge = Gauge(transaction_key)
        self._response_counter = Counter('test journey transaction method code'.split())
        self._response_histogram = Histogram('transaction'.split(), [0.0001, 0.001,
            0.01, 0.05, 0.1, 0.2, 0.4, 0.8, 1, 2, 4, 8, 16, 32, 64])
        self._msg_delay = 0
        volume_key = 'test scenario_id'.split()
        self._actual = Gauge(volume_key)
        self._required = Gauge(volume_key)
        self._num_runners = Gauge(['test'])

    def process_message(self, msg):
        if 'type' not in msg:
            return
        if 'time' in msg:
            self._msg_delay = time.time() - msg['time']
        msg_type = msg['type']
        if msg_type == 'http_curl_metrics':
            transaction = msg.get('transaction', '')
            key = (
                msg.get('test', ''),
                msg.get('journey', ''),
                transaction,
                msg['method'],
                msg['response_code']
            )
            self._response_counter.inc(key)
            self._response_histogram.add((transaction,), msg['total_time'])
        elif msg_type == 'exception' or msg_type == 'error':
            key = (
                msg.get('test', ''),
                msg.get('journey', ''),
                msg.get('transaction', ''),
                msg.get('location', ''),
                msg.get('message', ''),
            )
            self._error_counter.inc(key)
        elif msg_type == 'start':
            key = (
                msg.get('test', ''),
                msg.get('journey', ''),
                msg.get('transaction', ''),
            )
            self._transaction_start_counter.inc(key)
            self._transaction_count_gauge.change_by(key, 1)
        elif msg_type == 'end':
            key = (
                msg.get('test', ''),
                msg.get('journey', ''),
                msg.get('transaction', ''),
            )
            self._transaction_end_counter.inc(key)
            self._transaction_count_gauge.change_by(key, -1)
        elif msg_type == 'controller_report':
            test = msg['test']
            self._num_runners.set((test,), msg['num_runners'])
            for scenario_id, value in msg['actual'].items():
                self._actual.set((test, scenario_id), value)
            for scenario_id, value in msg['required'].items():
                self._required.set((test, scenario_id), value)

    def prometheus_metrics(self):
        def format_dict(d):
            return ','.join(['%s="%s"' % (k,v) for k,v in d.items()])
        lines = []
        lines.append('# TYPE mite_message_delay gauge')
        lines.append('mite_message_delay {} %s' % (self._msg_delay,))
        lines.append('')
        lines.append('# TYPE mite_http_response_total counter')
        for labels, value in self._response_counter.iter_counts():
            lines.append('mite_http_response_total {%s} %s' % (format_dict(labels), value))
        lines.append('')
        lines.append('# TYPE mite_transaction_count gauge')
        for labels, value in self._transaction_count_gauge.iter_counts():
            lines.append('mite_transaction_count {%s} %s' % (format_dict(labels), value))
        lines.append('')
        lines.append('# TYPE mite_runner_count gauge')
        for labels, value in self._num_runners.iter_counts():
            lines.append('mite_runner_count {%s} %s' % (format_dict(labels), value))
        lines.append('')
        lines.append('# TYPE mite_actual_count gauge')
        for labels, value in self._actual.iter_counts():
            lines.append('mite_actual_count {%s} %s' % (format_dict(labels), value))
        lines.append('')
        lines.append('# TYPE mite_requird_count gauge')
        for labels, value in self._required.iter_counts():
            lines.append('mite_required_count {%s} %s' % (format_dict(labels), value))
        lines.append('')
        lines.append('# TYPE mite_journey_error_total counter')
        for labels, value in self._error_counter.iter_counts():
            lines.append('mite_journey_error_total {%s} %s' % (format_dict(labels), value))
        lines.append('')
        lines.append('# TYPE mite_transaction_start_total counter')
        for labels, value in self._transaction_start_counter.iter_counts():
            lines.append('mite_transaction_start_total {%s} %s' % (format_dict(labels), value))
        lines.append('')
        lines.append('# TYPE mite_transaction_end_total counter')
        for labels, value in self._transaction_end_counter.iter_counts():
            lines.append('mite_transaction_end_total {%s} %s' % (format_dict(labels), value))
        lines.append('')
        lines.append('# TYPE mite_http_response_time_seconds histogram')
        for labels, _sum, _total_count, bin_counts in  self._response_histogram.iter_histograms():
            formatted_labels = format_dict(labels)
            for bin_value, bin_count in bin_counts:
                lines.append('mite_http_response_time_seconds_bucket{%s,le="%.6f"} %d' % (formatted_labels, bin_value, bin_count))
            lines.append('mite_http_response_time_seconds_bucket{%s,le="+Inf"} %d' % (formatted_labels, _total_count))
            lines.append('mite_http_response_time_seconds_sum{%s} %.6f' % (formatted_labels, _sum))
            lines.append('mite_http_response_time_seconds_count{%s} %d' % (formatted_labels, _total_count))
        lines.append('')
        return '\n'.join(lines)


