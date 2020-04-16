from translator.basemetric import BaseMetric
from translator.utils import convert_unix_timestamp_to_datetime_str, get_vdu_details, \
    convert_bytes_psec_to_mbits_psec
from translator.exceptions import OsmInfoNotFound
from translator.utils import vcache_metrics


class Metric(BaseMetric):
    def __init__(self, source="telegraf"):
        self.raw_metric = {}
        self.source = source
        self.supported_metrics = vcache_metrics()
        super().__init__()

    def get_metrics(self, data):
        """Format the metric data.

        data (list): The payload as it is provided from telegraf (vCache)
        metric_name (str): The type of the metric

        Returns:
            list: the metrics including the name, type, unit, timestamp and value
        """
        metrics = []

        # Convert the timestamp
        timestamp = convert_unix_timestamp_to_datetime_str(data.get("timestamp", None))

        raw_metrics = data.get("fields", {})
        for metric_name, value in raw_metrics.items():
            metric_unit = self.get_metric_unit(metric_name)
            metric_type = self.get_metric_type(metric_name)

            # transform value if needed
            if metric_name in ['bytes_recv', 'bytes_sent']:
                value = convert_bytes_psec_to_mbits_psec(value)
                metric_unit = "Mbps"

            # Add the metric raw in list
            metrics.append(
                {"name": metric_name, "type": metric_type, "value": value, "unit": metric_unit,
                 "timestamp": timestamp})

        return metrics

    def get_translation(self, vdu_uuid):
        """Generate and return a common data model for each type of metric.

        Args:
            vdu_uuid (str): The vdu uuid

        Returns:
            dict: A common data model for each type of metric.
        """
        return get_vdu_details(vdu_uuid, self.raw_metric, source=self.source)

    def get_metric_unit(self, metric_name):
        """ Get the unit of the metric by given metric name

        Args:
            metric_name (str): The name of the metric

        Returns:
            str: the unit. If metric is not supported, empty string is returned
        """
        if metric_name in self.supported_metrics.keys():
            return self.supported_metrics.get(metric_name, {}).get('unit', "")
        return ""

    def get_metric_type(self, metric_name):
        """ Get the type of the metric by given metric name

        Args:
            metric_name (str): The name of the metric

        Returns:
            str: the unit. If metric is not supported, empty string is returned
        """
        if metric_name in self.supported_metrics.keys():
            return self.supported_metrics.get(metric_name, {}).get('type', "")
        return ""
