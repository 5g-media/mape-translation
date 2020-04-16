from settings import OSM_COMPONENTS, LOGGING
from httpclient.client import Client
import logging.config

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class Vnfr(object):
    """Description of Vnfr class"""

    def __init__(self, token):
        """Constructor of Vnfr class"""
        self.__client = Client(verify_ssl_cert=False)
        self.basic_token = token

    def get_list(self):
        """Get the list of the VNF records from the SO-ub container

        Returns:
            obj: a requests object

        Examples:
            >>> from soapi.vnfr import Vnfr
            >>> from soapi.identity import basic_token
            >>> from settings import OSM_ADMIN_CREDENTIALS
            >>> token = basic_token(OSM_ADMIN_CREDENTIALS.get('username'), OSM_ADMIN_CREDENTIALS.get('username'))
            >>> vnfr = Vnfr(token)
            >>> vnfrs = vnfr.get_list()
            >>> print(int(vnfrs.status_code))
            200
        """
        endpoint = '{}/v1/api/operational/project/default/vnfr-catalog/vnfr'.format(OSM_COMPONENTS.get('SO-API'))
        headers = {"Authorization": "Basic {}".format(self.basic_token), "Accept": "application/json"}
        response = self.__client.get(endpoint, headers)
        return response
