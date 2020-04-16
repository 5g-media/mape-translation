from translator.basemetric import BaseMetric
from translator.exceptions import OsmInfoNotFound
from translator.utils import get_vdu_details, get_faas_vdu_details
from faasapi.instances import FaaS
from settings import OSM_IP


class Metric(BaseMetric):
    def __init__(self, raw_metric, source="kubernetes"):
        self.source = source
        self.raw_metric = raw_metric
        self.__faas = FaaS(OSM_IP)

        super().__init__()

    def get_metric(self):
        """Format the metric data.

        Note: In case of kubernetes, the structure is already the proper.
        Thus, no transformation is needed.

        Returns:
            dict: the metric including the name, type, unit, timestamp and value
        """
        return self.raw_metric

    def get_translation(self, vdu_uuid=None):
        """Generate and return a common data model for each type of metric.

        Args:
            vdu_uuid (str): The vdu uuid. Actually, it maps to the container ID

        Returns:
            dict: A common data model for each type of metric.
        """
        return get_vdu_details(vdu_uuid, self.raw_metric, source=self.source)

    def get_translation_vnf_on_demand(self, vdu_uuid):
        self.__faas.set_ns_instances()
        data = self.__faas.search_vnf(vdu_uuid)
        return get_faas_vdu_details(vdu_uuid, data['ro_ns_uuid'], data['vnf_name'])
