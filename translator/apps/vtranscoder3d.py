from translator.basemetric import BaseMetric
from translator.utils import get_vdu_details, vtranscoder3d_metrics
from translator.exceptions import OsmInfoNotFound
from datetime import datetime


class Metric(BaseMetric):
    """Constructor"""

    def __init__(self, record, source="vtranscoder3d"):
        self.source = source
        self.record = record
        self.supported_metrics = vtranscoder3d_metrics()
        self.now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        super().__init__()

    def get_metrics(self):
        """Format the metric data

        Returns:
            list: the list of adapted metrics including the name, type (quality), unit, timestamp and value
        """
        metrics = []
        allowed_fields = self.supported_metrics.keys()

        for metric_name in self.record.keys():
            if metric_name not in allowed_fields:
                continue
            metrics.append({
                "name": metric_name.lower(),
                "type": self.get_metric_type(metric_name),
                "value": self.record[metric_name],
                "unit": self.get_metric_unit(metric_name),
                "timestamp": self.now
            })
        return metrics

    def get_translation(self, vdu_uuid):
        """Generate and return a common data model for each type of metric.

        Args:
            vdu_uuid (str): The VNF uuid

        Returns:
            dict: A common data model for each type of metric. See more in the `samples/output.json` file.
        """
        record = {}
        return get_vdu_details(vdu_uuid, record, source=self.source)

    def get_metric_unit(self, metric_name):
        """ Get the unit of the metric

        Args:
            metric_name (str): The name of the metric

        Returns:
            str: get the metric's unit
        """
        if metric_name in self.supported_metrics.keys():
            return self.supported_metrics[metric_name].get('unit', "")
        return ""

    def get_metric_type(self, metric_name):
        """ Get the type of the metric

        Args:
            metric_name (str): The name of the metric

        Returns:
            str: get the metric's type
        """
        if metric_name in self.supported_metrics.keys():
            return self.supported_metrics[metric_name].get('type', "gauge")
        return ""
