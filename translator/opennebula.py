from translator.basemetric import BaseMetric
from translator.exceptions import OsmInfoNotFound
from translator.utils import get_vdu_details, opennebula_metrics
import copy


class Metric(BaseMetric):
    def __init__(self, raw_metric, source="opennebula"):
        self.source = source
        self.raw_metric = raw_metric
        self.supported_metrics = opennebula_metrics()
        super().__init__()

    def get_metric(self):
        """Format the metric data.

        Note: In case of OpenNebula, the structure is already the proper.
        Thus, no transformation is needed.

        Returns:
            dict: the metric including the name, type, unit, timestamp and value
        """
        new_metric = copy.deepcopy(self.raw_metric)
        if 'vdu_uuid' in new_metric.keys():
            del new_metric['vdu_uuid']
        new_metric['name'] = new_metric['type']
        new_metric['type'] = self.get_metric_type()
        return new_metric

    def get_metric_type(self):
        """Get the type of the metric

        Returns:
            str: the type of the metric
        """
        search_for_metric = self.raw_metric['type']
        if search_for_metric in self.supported_metrics.keys():
            return self.supported_metrics[search_for_metric].get('type', "gauge")
        return "unknown"

    def get_translation(self, vdu_uuid=None):
        """Generate and return a common data model for each type of metric.

        Args:
            vdu_uuid (str): The vdu uuid. Actually, it maps to the container ID

        Returns:
            dict: A common data model for each type of metric.
        """
        return get_vdu_details(vdu_uuid, self.raw_metric, source=self.source)
