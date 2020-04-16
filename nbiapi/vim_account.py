from settings import OSM_COMPONENTS, LOGGING
from httpclient.client import Client
import logging.config
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.config.dictConfig(LOGGING)
logger = logging.getLogger(__name__)


class VimAccount(object):
    """Description of VimAccount class"""

    def __init__(self, token):
        """Constructor of VimAccount class"""
        self.__client = Client(verify_ssl_cert=False)
        self.bearer_token = token

    def get_list(self):
        """Get the list of the registered vim accounts in OSM r4

        Returns:
            obj: a requests object

        Examples:
            >>> from nbiapi.identity import bearer_token
            >>> from nbiapi.vim_account import VimAccount
            >>> from settings import OSM_ADMIN_CREDENTIALS
            >>> token = bearer_token(OSM_ADMIN_CREDENTIALS.get('username'), OSM_ADMIN_CREDENTIALS.get('username'))
            >>> vim_account = VimAccount(token)
            >>> entries = vim_account.get_list()
            >>> print(entries.json())
        """
        endpoint = '{}/osm/admin/v1/vim_accounts'.format(OSM_COMPONENTS.get('NBI-API'))
        headers = {"Authorization": "Bearer {}".format(self.bearer_token), "Accept": "application/json"}
        response = self.__client.get(endpoint, headers)
        return response

    def get(self, vim_account_uuid=None):
        """Get details for a project in OSM r4 by given project ID

        Args:
            vim_account_uuid (str): The Vim Account UUID

        Returns:
            obj: a requests object

        Examples:
            >>> from nbiapi.identity import bearer_token
            >>> from nbiapi.vim_account import VimAccount
            >>> from settings import OSM_ADMIN_CREDENTIALS
            >>> token = bearer_token(OSM_ADMIN_CREDENTIALS.get('username'), OSM_ADMIN_CREDENTIALS.get('username'))
            >>> vim_account = VimAccount(token)
            >>> entry = vim_account.get("66000170-7fe9-4ab0-b113-b60a92ee196c")
            >>> print(entry.json())
        """
        endpoint = '{}/osm/admin/v1/vim_accounts/{}'.format(OSM_COMPONENTS.get('NBI-API'), vim_account_uuid)
        headers = {"Authorization": "Bearer {}".format(self.bearer_token), "Accept": "application/json"}
        response = self.__client.get(endpoint, headers)
        return response
