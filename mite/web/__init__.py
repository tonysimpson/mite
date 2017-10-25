import sys
from flask import Flask, Response

from .metrics import MetricsProcessor

app = Flask(__name__)

metrics_processor = MetricsProcessor()

@app.route('/metrics')
def metrics():
    text = metrics_processor.prometheus_metrics()
    return Response(text, mimetype='text/plain')


