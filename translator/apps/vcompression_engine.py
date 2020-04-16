from translator.basemetric import BaseMetric
from translator.utils import get_vdu_details, vce_metrics, convert_unix_timestamp_to_datetime_str
from translator.exceptions import OsmInfoNotFound
from numbers import Number


class Metric(BaseMetric):
    """Constructor"""

    def __init__(self, record, source="vce"):
        self.source = source
        self.record = record
        self.supported_metrics = vce_metrics()
        super().__init__()

    def get_metrics(self):
        """Format the metric data

        Returns:
            list: the list of adapted metrics including the name, type, unit, timestamp and value
        """
        metrics = []
        allowed_fields = self.supported_metrics.keys()
        timestamp = self.get_metric_timestamp(self.record['utc_time'])

        for metric_name in self.record.keys():
            if metric_name not in allowed_fields:
                continue
            metrics.append({
                "name": metric_name.lower(),
                "type": self.get_metric_type(metric_name),
                "value": self.record[metric_name],
                "unit": self.get_metric_unit(metric_name),
                "timestamp": timestamp
            })
        return metrics

    def get_translation(self, vdu_uuid):
        """Generate and return a common data model for each type of metric.

        Args:
            vdu_uuid (str): The VNF uuid

        Returns:
            dict: A common data model for each type of metric.
        """
        record = {}
        return get_vdu_details(vdu_uuid, record, source=self.source)

    @staticmethod
    def get_metric_timestamp(unix_timestamp):
        """ Convert the unix timestamp in ISO 8601, UTC timezone

        Args:
            unix_timestamp (str, float, int):

        Returns:
            str: the timestamp in UTC
        """
        unix_time_len = 10

        if isinstance(unix_timestamp, Number):
            tm_str = str(unix_timestamp)
        elif isinstance(unix_timestamp, str):
            tm_str = unix_timestamp.split(".")[0]
        else:
            return None

        tm = tm_str[:unix_time_len]
        return convert_unix_timestamp_to_datetime_str(int(tm))

    def get_metric_unit(self, metric_name):
        """ Get the unit of the metric

        Args:
            metric_name (str): The name of the metric

        Returns:
            str: get the metric's unit
        """
        if metric_name in self.supported_metrics:
            return self.supported_metrics[metric_name].get('unit', "")
        return ""

    def get_metric_type(self, metric_name):
        """ Get the type of the metric

        Args:
            metric_name (str): The name of the metric

        Returns:
            str: get the metric's type
        """
        if metric_name in self.supported_metrics:
            return self.supported_metrics[metric_name].get('type', "gauge")
        return ""
