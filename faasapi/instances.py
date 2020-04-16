import logging.config
import requests
from httpclient.client import Client
from settings import LOGGING


class FaaS:

    def __init__(self, osm_host):
        """Constructor

        Args:
            osm_host (str): the host of the OSM (and the FaaS API)
        """
        self.__client = Client()
        self.osm_host = "{}".format(osm_host)
        self.faas_polling_host = self.osm_host
        self.faas_polling_ip = '5001'
        self.ns_instances = []

    def set_ns_instances(self):
        """ Fetch the NN instances in FaaS VIM

        Returns:
            list: the NS instances
        """
        endpoint = 'http://{}:{}/osm/instances_all'.format(self.faas_polling_host,
                                                           self.faas_polling_ip)
        request = self.__client.get(endpoint)
        data = request.json()
        self.ns_instances = data

    def search_vnf(self, container_id):
        """ Search information about a serverless VNF

        Args:
            container_id:

        Returns:
            dict: The NS uuid and name in RO and the vnf name (vnfd name plus vnf index)
        """
        result = {'ro_ns_uuid': None, 'ns_name': None, 'vnf_name': None}

        try:
            for ns in self.ns_instances:
                for vnf in ns['vnfs']:
                    vim_info = vnf.get('vim_info', {})

                    if 'vim-id' not in vim_info.keys():
                        # On-demand serverless VNFs
                        records = vim_info.get('records', [])
                        if len(records) == 0:
                            continue
                        for record in records:
                            if 'vim-id' in record.keys() and record['vim-id'] == container_id:
                                return {'ro_ns_uuid': ns['uuid'], 'ns_name': ns['name'],
                                        'vnf_name': vnf['vnf_name']}
                    else:
                        # core serverless VNFs
                        vim_id = vim_info.get('vim-id', None)
                        if vim_id == container_id:
                            return {'ro_ns_uuid': ns['uuid'], 'ns_name': ns['name'],
                                    'vnf_name': vnf['vnf_name']}
            raise Exception('No match found for container with id {}'.format(container_id))
        except Exception as ex:
            return result
