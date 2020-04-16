from translator.basemetric import BaseMetric
from translator.utils import get_vnf_details, convert_unix_timestamp_to_datetime_str
from translator.exceptions import OsmInfoNotFound


class Metric(BaseMetric):
    """Constructor"""

    def __init__(self, client_id, group_id, timestamp, quality_id, metrics, source="vtranscoder3d"):
        """ Init the Metric class

        Args:
            client_id (str): The identifier of the spectator
            group_id (str): The group in which client is member
            timestamp (int): The metrics timestamp in unix time
            quality_id (int): The current quality index of the client
            metrics (list): The list of the metrics as these derived
            source (str): The origin of the metrics
        """
        self.source = source
        self.client_id = client_id
        self.group_id = group_id
        self.quality_id = quality_id
        self.timestamp = convert_unix_timestamp_to_datetime_str(timestamp)
        self.metrics = metrics
        super().__init__()

    def get_metrics(self):
        """Format the metric data

        Returns:
            list: the list of adapted metrics including the name, type (quality), unit, timestamp and value
        """
        final_metrics = []
        for metric in self.metrics:
            new_name = self.set_metric_name(metric['name'].lower(), metric['state'])
            # Append the regular metrics
            final_metrics.append(
                {"name": new_name, "type": metric['state'], "value": metric['value'],
                 "unit": metric['unit'], "timestamp": self.timestamp})
        # Add the quality index
        final_metrics.append(
            {"name": "quality", "type": "gauge", "value": self.quality_id, "unit": "number",
             "timestamp": self.timestamp})
        return final_metrics

    @staticmethod
    def set_metric_name(name, mtype):
        """ Rename the metric if needed

        Args:
            name (str): The name of the metric
            mtype (str): The type of the metric

        Returns:
            str: the name of the metric
        """
        if name == "bitrate":
            return "bitrate_on" if mtype == "on" else "bitrate_aggr"
        elif name == "framerate":
            return "framerate_on" if mtype == "on" else "framerate_aggr"
        elif name == "latency":
            return "latency_on" if mtype == "on" else "latency_aggr"
        else:
            return name

    def get_translation(self, vnf_uuid):
        """ Generate and return a common data model for each type of metric.

        Args:
            vnf_uuid (str): The VNF uuid

        Returns:
            dict: A common data model for each type of metric. See more in the `samples/output.json` file.
        """
        record = {}
        return get_vnf_details(vnf_uuid, record, source=self.source)
