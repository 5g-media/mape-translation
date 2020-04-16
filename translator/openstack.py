from translator.basemetric import BaseMetric
from translator.utils import get_vdu_details
from translator.exceptions import OsmInfoNotFound


class Metric(BaseMetric):
    """Constructor"""

    def __init__(self, raw_metric, source="openstack"):
        self.source = source
        self.raw_metric = raw_metric
        super().__init__()

    def get_metric(self):
        """Format the metric data

        Returns:
            dict: the metric including the name, type, unit, timestamp and value
        """
        timestamp = self.raw_metric.get("timestamp", None)
        if timestamp is not None and not timestamp.endswith('Z'):
            timestamp = "{}Z".format(timestamp)

        metric = {
            "name": self.raw_metric.get("counter_name", None),
            "type": self.raw_metric.get("counter_name", None),
            "value": self.raw_metric.get("counter_volume", None),
            "unit": self.raw_metric.get("counter_unit", None),
            "timestamp": timestamp
        }
        return metric

    def get_translation(self, vdu_uuid):
        """Generate and return a common data model for each type of metric.

        Args:
            vdu_uuid (str): The vdu uuid

        Returns:
            dict: A common data model for each type of metric. See more in the `samples/output.json` file.
        """
        return get_vdu_details(vdu_uuid, self.raw_metric, source=self.source)
