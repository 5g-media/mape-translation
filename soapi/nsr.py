import logging.config
from settings import OSM_COMPONENTS, LOGGING
from httpclient.client import Client

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class Nsr(object):
    """Description of Nsr class"""

    def __init__(self, token):
        """Constructor of Nsr class"""
        self.__client = Client(verify_ssl_cert=False)
        self.basic_token = token

    def get_list(self):
        """Get the list of the NS records from the SO-ub container

        Returns:
            obj: a requests object

        Examples:
            >>> from soapi.nsr import Nsr
            >>> from soapi.identity import basic_token
            >>> from settings import OSM_ADMIN_CREDENTIALS
            >>> token = basic_token(OSM_ADMIN_CREDENTIALS.get('username'), OSM_ADMIN_CREDENTIALS.get('username'))
            >>> ns = Nsr(token)
            >>> ns_records = ns.get_list()
            >>> print(int(ns_records.status_code))
            200
        """
        endpoint = '{}/api/running/project/default/ns-instance-config'.format(OSM_COMPONENTS.get('SO-API'))
        headers = {"Authorization": "Basic {}".format(self.basic_token), "Accept": "application/json"}
        response = self.__client.get(endpoint, headers)
        return response

    def get(self, ns_uuid):
        """Get details for a NS record from the SO-ub container

        Args:
            ns_uuid (str): The ID of the network service

        Returns:
            obj: a requests object

        Examples:
            >>> from soapi.nsr import Nsr
            >>> from soapi.identity import basic_token
            >>> from settings import OSM_ADMIN_CREDENTIALS
            >>> token = basic_token(OSM_ADMIN_CREDENTIALS.get('username'), OSM_ADMIN_CREDENTIALS.get('username'))
            >>> ns = Nsr(token)
            >>> ns_record = ns.get('xxx')
            >>> print(int(ns_record.status_code))
            200
        """
        endpoint = '{}/api/operational/project/default/ns-instance-opdata/nsr/{}?deep'.format(
            OSM_COMPONENTS.get('SO-API'), ns_uuid)
        headers = {"Authorization": "Basic {}".format(self.basic_token), "Accept": "application/json"}
        response = self.__client.get(endpoint, headers)
        return response
