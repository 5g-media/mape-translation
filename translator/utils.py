import copy
import logging
from datetime import datetime
from influxdb import InfluxDBClient

from nbiapi.identity import bearer_token
from nbiapi.ns import Ns
from nbiapi.vnf import Vnf
from nbiapi.vnfd import Vnfd
from nbiapi.vim_account import VimAccount

from translator.exceptions import VduWithIpNotFound, VduNotFound, VnfNotFound
from settings import METRICS_WHITE_LIST, OSM_ADMIN_CREDENTIALS, LOGGING, INFLUX_DATABASES

logging.config.dictConfig(LOGGING)
logger = logging.getLogger("translator")


def consume_metric_or_not(vim_type, metric_type):
    """Detect if the incoming type of metric should be considered for the MAPR loop

    Args:
        vim_type (str): The type of the VIM i.e: openstack, vmware etc
        metric_type (str): The type of the metric, i.e.: cpu_util

    Returns:
        bool: True if the metric is taken into account. Otherwise, False.

    Examples:
        >>> vim_type = 'openstack'
        >>> metric_type = 'cpu_util'
        >>> decision = consume_metric_or_not(vim_type, metric_type)
        >>> print(decision)
        True
    """
    return metric_type in METRICS_WHITE_LIST.get(vim_type, [])


def yield_memory_metrics_from_flavor_openstack(memory_usage):
    """Get the memory usage metric in case of Openstack/ceilometer and generate the memory metric in MB

    Args:
        memory_usage (dict): The memory_usage metric (see samples/output.json)

    Returns:
        list: The memory and memory_util metrics
    """
    memory_metrics = []
    try:
        memory = copy.deepcopy(memory_usage)
        memory_util = copy.deepcopy(memory_usage)

        flavor = memory_usage.get('mano', {}).get('vdu', {}).get('flavor', {})
        total_memory = flavor.get('ram', None)
        utilized_memory = memory_usage.get('metric', {}).get('value', None)
        timestamp = memory_usage.get('metric', {}).get('timestamp', None)

        # get the memory metric based on the flavor
        memory_metric = dict()
        memory_metric['timestamp'] = timestamp
        memory_metric['name'] = 'memory'
        memory_metric['value'] = int(total_memory)
        memory_metric['unit'] = 'MB'
        memory_metric['type'] = 'gauge'
        memory['metric'] = memory_metric
        memory_metrics.append(memory)

        # yield the memory utilization
        memory_util_metric = dict()
        memory_util_metric['timestamp'] = timestamp
        memory_util_metric['name'] = 'memory_util'
        memory_util_metric['value'] = round(float(utilized_memory) / float(total_memory), 2)
        memory_util_metric['unit'] = '%'
        memory_util_metric['type'] = 'gauge'
        memory_util['metric'] = memory_util_metric
        memory_metrics.append(memory_util)
    except Exception as ex:
        logger.exception(ex)
    finally:
        return memory_metrics


def yield_vcpu_metric_from_flavor_openstack(cpu_metric):
    """Get the cpu metric in case of Openstack/ceilometer and generate the vcpu metric

    Args:
        cpu_metric (dict): The cpu metric (see samples/output.json)

    Returns:
        dict: The vcpu metric
    """
    vcpu = copy.deepcopy(cpu_metric)
    try:
        flavor = cpu_metric.get('mano', {}).get('vdu', {}).get('flavor', {})
        timestamp = cpu_metric.get('metric', {}).get('timestamp', None)

        # get the memory metric based on the flavor
        vcpu_metric = dict()
        vcpu_metric['timestamp'] = timestamp
        vcpu_metric['name'] = 'vcpus'
        vcpu_metric['value'] = flavor.get('vcpus', None)
        vcpu_metric['unit'] = 'vcpu'
        vcpu_metric['type'] = 'gauge'
        vcpu['metric'] = vcpu_metric
    except Exception as ex:
        logger.exception(ex)
    finally:
        return vcpu


def get_vdu_details(vdu_uuid, raw_metric, source="openstack"):
    """Append MANO (OSM) details (ns, vnf and vdu) by given VDU uuid

    Args:
        vdu_uuid (str): The uuid of the VDU (VM)
        raw_metric (dict): The original metric as it is sent from monitoring metrics generator
        source (str): The NFVI or application ref. It could be "openstack", "telegraf" etc..

    Returns:
        dict: osm info for the given vdu
    """
    mano = {}
    token = bearer_token(OSM_ADMIN_CREDENTIALS.get('username'),
                         OSM_ADMIN_CREDENTIALS.get('password'))
    vnfr = Vnf(token)
    vnf_response = vnfr.get_list()
    vnf_records = vnf_response.json()

    for vnf_record in vnf_records:
        # Get NS details
        ns_id = vnf_record.get("nsr-id-ref", None)
        ns = Ns(token)
        ns_response = ns.get(ns_uuid=ns_id)
        nsr = ns_response.json()

        # VNFd info
        vnfd = vnf_record.get("vnfd-id", None)

        # VDUs info
        vdu_records = vnf_record.get('vdur', [])
        # Number of VDU per VNFd
        vdus_count = len(vdu_records)

        for vdu_record in vdu_records:
            if vdu_record.get("vim-id", None) == vdu_uuid:
                # mano = {}
                try:
                    # Find the VDU info
                    vdu_metadata = raw_metric.get("resource_metadata", {})

                    # If the data coming from VNFs, discover in different way the VDU info
                    if source in ["telegraf", "vtranscoder3d", "vtranscoder3d_spectators", "vce",
                                  "kubernetes", "opennebula"]:
                        vdu_metadata["instance_id"] = vdu_uuid
                        vdu_metadata["flavor"] = {}
                        if vdus_count:
                            # TODO: what about the IPs if exists VNF with multiple VDUs?
                            vdu_metadata["state"] = vdu_record.get('status', "")
                            vdu_metadata['name'] = vdu_record.get('name', "")
                            vdu_metadata["flavor"]["ram"] = None
                            vdu_metadata["flavor"]["vcpus"] = None
                            vdu_metadata["flavor"]["disk"] = None

                    # elif source in ["kubernetes", "opennebula"]:
                    #     vdu_metadata["instance_id"] = vdu_record.get('vim-id', None)
                    #     vdu_metadata["flavor"] = {}
                    #     if vdus_count:
                    #         # TODO: what about the IPs if exists VNF with multiple VDUs?
                    #         vdu_metadata["state"] = vdu_record.get('status', None)
                    #         vdu_metadata['name'] = vdu_record.get('name', None)
                    #         vdu_metadata["flavor"]["ram"] = None
                    #         vdu_metadata["flavor"]["vcpus"] = None
                    #         vdu_metadata["flavor"]["disk"] = None

                    elif source == "openstack":
                        """By default, OpenStack (ceilometer) provides us the following info: vcpus, ram, 
                        ephemeral, swap, disk, name, id
                        """
                        pass

                    # Get IP per VDU
                    vdu_metadata['ip_address'] = vdu_record.get("ip-address", None)

                    # Get the VIM account Info
                    vim_account = VimAccount(token)
                    vim_response = vim_account.get(vim_account_uuid=nsr.get('datacenter', None))
                    vimr = vim_response.json()

                    # Get the NSd uuid
                    nsd_id = nsr.get('nsdId', None)
                    if nsd_id is None:
                        nsd_id = nsr.get('instantiate_params', {}).get('nsdId', None)

                    mano = {
                        "ns": {
                            "id": ns_id,
                            "name": nsr.get('name-ref', None),
                            "nsd_id": nsd_id,
                            "nsd_name": nsr.get('nsd-name-ref', None)
                        },
                        "vnf": {
                            "id": vnf_record.get("id", None),
                            "name": vnf_record.get("name", None),
                            # not in osm r5: it could be <vnfd_name>_<index>
                            "index": vnf_record.get("member-vnf-index-ref", 0),
                            "short_name": vnf_record.get("short-name", None),  # not in osm r5
                            "vnfd_id": vnf_record.get("vnfd-id", None),
                            "vnfd_name": vnf_record.get('vnfd-ref', None)
                        },
                        "vdu": {
                            "id": vdu_metadata.get("instance_id", None),
                            "name": vdu_metadata.get("name", None),
                            "image_id": vdu_metadata.get("image", {}).get("id", None),
                            "flavor": vdu_metadata.get("flavor", {}),
                            "status": vdu_metadata.get("state", None),
                            "ip_address": vdu_metadata['ip_address'],
                            "mgmt-interface": None  # future usage
                        },
                        "vim": {
                            "uuid": vimr.get('_id', None),
                            "name": vimr.get('name', None),
                            "type": vimr.get('vim_type', None),
                            "url": vimr.get('vim_url', None),
                            "tag": source
                        }
                    }
                    logger.debug(mano)
                    # return mano
                except Exception as ex:
                    logger.exception(ex)
                finally:
                    return mano

    # if vdus_count > 0:
    # raise VduNotFound("Not found VDU with given UUID: {}".format(vdu_uuid))
    return mano


def get_faas_vdu_details(vdu_uuid, ro_ns_uuid, vnf_name):
    mano = {}
    nsr = {}
    vnfd = {}

    token = bearer_token(OSM_ADMIN_CREDENTIALS.get('username'),
                         OSM_ADMIN_CREDENTIALS.get('password'))

    try:
        if ro_ns_uuid is None or vnf_name is None:
            raise Exception('Empty input')
        vnf_name = vnf_name.split('.')
        vnfd_name = vnf_name[0]
        vnf_index = vnf_name[1]

        # search for ro_ns_uuid in NSs list
        ns = Ns(token)
        ns_response = ns.get_list()
        ns_list = ns_response.json()

        for instance in ns_list:
            # Ensure that RO data are available
            openmano_deployment = instance['_admin'].get('deployed', {}).get('RO', {})
            if len(openmano_deployment.keys()) == 0:
                continue
            # Compare the container id with the current NS record uuid
            nsr_id = openmano_deployment.get('nsr_id', None)
            if nsr_id is None or nsr_id != ro_ns_uuid:
                continue
            nsr = instance
            break

        # Get the NSd uuid
        nsd_id = nsr.get('nsdId', None)
        if nsd_id is None:
            nsd_id = nsr.get('instantiate_params', {}).get('nsdId', None)

        # Get the VIM account Info
        datacenter = nsr.get('datacenter', None)
        vim_account = VimAccount(token)
        vim_response = vim_account.get(vim_account_uuid=datacenter)
        vimr = vim_response.json()

        # Get vnfd info
        vnf_descriptor = Vnfd(token)
        vnfd_req = vnf_descriptor.get_list()
        vnfd_list = vnfd_req.json()
        for descriptor in vnfd_list:
            if 'id' in descriptor.keys() and descriptor['id'] == vnfd_name:
                vnfd = descriptor
                break

        mano = {
            "ns": {
                "id": nsr['id'],
                "name": nsr.get('name-ref', None),
                "nsd_id": nsd_id,
                "nsd_name": nsr.get('nsd-name-ref', None)
            },
            "vnf": {
                "id": '{}-{}-{}'.format(vdu_uuid, vnfd_name, vnf_index),
                "name": '{}.{}'.format(vnfd_name, vnf_index),
                "index": vnf_index,
                "short_name": None,
                "vnfd_id": vnfd['_id'],
                "vnfd_name": vnfd_name
            },
            "vdu": {
                "id": vdu_uuid,
                "name": vnfd_name,
                "image_id": vnfd_name,
                "flavor": {},
                "status": 'running',
                "ip_address": '0.0.0.0',
                "mgmt-interface": None  # future usage
            },
            "vim": {
                "uuid": vimr.get('_id', None),
                "name": vimr.get('name', None),
                "type": vimr.get('vim_type', None),
                "url": vimr.get('vim_url', None),
                "tag": 'kubernetes'
            }
        }
    except Exception as ex:
        logger.exception(ex)
    finally:
        return mano


def get_vnf_details(vnf_uuid, record, source="vtranscoder3d"):
    """ Append MANO (OSM) details (ns, vnf and vdu) by given VNF uuid

    Args:
        vnf_uuid (str): The uuid of the VNF
        record (dict): The original metric as it is sent from monitoring metrics generator
        source (str): The NFVI or application ref. It could be "vtranscoder3d" etc..

    Returns:
        dict: osm info for the given vdu
    """
    mano = {}
    token = bearer_token(OSM_ADMIN_CREDENTIALS.get('username'),
                         OSM_ADMIN_CREDENTIALS.get('password'))
    vnfr = Vnf(token)
    vnf_response = vnfr.get(vnf_uuid=vnf_uuid)
    vnf_record = vnf_response.json()

    # Get NS details
    ns_id = vnf_record.get("nsr-id-ref", None)
    ns = Ns(token)
    ns_response = ns.get(ns_uuid=ns_id)
    nsr = ns_response.json()

    # VNFd info
    vnfd = vnf_record.get("vnfd-id", None)

    # VDUs info
    vdu_records = vnf_record.get('vdur', [])
    # Number of VDU per VNFd
    vdus_count = len(vdu_records)
    if vdus_count > 1:
        logger.critical("{} VDUs were found for the VNF with uuid: {}".format(vdus_count, vnf_uuid))

    vdu_record = vdu_records[0]
    try:
        # Find the VDU info
        vdu_metadata = record.get("resource_metadata", {})

        # If the data coming from VNFs, discover in different way the VDU info
        if source in ["telegraf", "vtranscoder3d", "vce", "kubernetes", "opennebula",
                      "vtranscoder3d_spectators"]:
            vdu_metadata["instance_id"] = vdu_record.get('vim-id', None)
            vdu_metadata["flavor"] = {}
            if vdus_count:
                # TODO: what about the IPs if exists VNF with multiple VDUs?
                vdu_metadata["state"] = vdu_record.get('status', "")
                vdu_metadata['name'] = vdu_record.get('name', "")
                vdu_metadata["flavor"]["ram"] = None
                vdu_metadata["flavor"]["vcpus"] = None
                vdu_metadata["flavor"]["disk"] = None

        elif source == "openstack":
            """By default, OpenStack (ceilometer) provides us the following info: vcpus, ram, 
            ephemeral, swap, disk, name, id
            """
            pass

        # Get IP per VDU
        vdu_metadata['ip_address'] = vdu_record.get("ip-address", None)

        # Get the VIM account Info
        vim_account = VimAccount(token)
        vim_response = vim_account.get(vim_account_uuid=nsr.get('datacenter', None))
        vimr = vim_response.json()

        # Get the NSd uuid
        nsd_id = nsr.get('nsdId', None)
        if nsd_id is None:
            nsd_id = nsr.get('instantiate_params', {}).get('nsdId', None)

        mano = {
            "ns": {
                "id": ns_id,
                "name": nsr.get('name-ref', None),
                "nsd_id": nsd_id,
                "nsd_name": nsr.get('nsd-name-ref', None)
            },
            "vnf": {
                "id": vnf_record.get("id", None),
                "name": vnf_record.get("name", None),
                # not in osm r5: it could be <vnfd_name>_<index>
                "index": vnf_record.get("member-vnf-index-ref", 0),
                "short_name": vnf_record.get("short-name", None),  # not in osm r5
                "vnfd_id": vnf_record.get("vnfd-id", None),
                "vnfd_name": vnf_record.get('vnfd-ref', None)
            },
            "vdu": {
                "id": vdu_metadata.get("instance_id", None),
                "name": vdu_metadata.get("name", None),
                "image_id": vdu_metadata.get("image", {}).get("id", None),
                "flavor": vdu_metadata.get("flavor", {}),
                "status": vdu_metadata.get("state", None),
                "ip_address": vdu_metadata['ip_address'],
                "mgmt-interface": None  # future usage
            },
            "vim": {
                "uuid": vimr.get('_id', None),
                "name": vimr.get('name', None),
                "type": vimr.get('vim_type', None),
                "url": vimr.get('vim_url', None),
                "tag": source
            }
        }
        logger.debug(mano)
    except Exception as ex:
        logger.exception(ex)
    finally:
        # TODO: Since we don't know the VDU uuid, the 1st VDU will be used since 1 VDU is used for the VNF (UC1).
        return mano


def discover_vdu_uuid_by_vnf_index(vnf_index):
    """ Discover the VDU uuid by given the vnf index

    Args:
        vnf_index (str): The VNF index

    Returns:
        str: the vdu uuid

    """
    token = bearer_token(OSM_ADMIN_CREDENTIALS.get('username'),
                         OSM_ADMIN_CREDENTIALS.get('username'))

    # Get the UUIDs of the running NSs
    ns = Ns(token)
    request = ns.get_list()
    nss_response = request.json()
    ns_uuids = [ns.get('id') for ns in nss_response]

    # TODO: what if more than one NSs are running
    # if len(ns_uuids):
    #     raise Exception("More that one NSs are running...")

    vdu_uuid = None

    for ns_uuid in ns_uuids:
        vnf = Vnf(token)
        request = vnf.get_list_by_ns(ns_uuid=ns_uuid)
        vnfs = request.json()
        for i in vnfs:
            if vnf_index in i.get("member-vnf-index-ref"):
                for vdur in i.get("vdur"):
                    vdu_uuid = vdur.get("vim-id")
                    return vdu_uuid

    return vdu_uuid


def discover_vnf_uuid_by_vnfd_name_index(vnfd_name_index):
    """ Discover the VDU uuid by given the vnfd name and index

    Args:
        vnfd_name_index (str): The VNFd name & index

    Returns:
        str: the vnf uuid

    """
    token = bearer_token(OSM_ADMIN_CREDENTIALS.get('username'),
                         OSM_ADMIN_CREDENTIALS.get('username'))

    # Get the UUIDs of the running NSs
    ns = Ns(token)
    request = ns.get_list()
    nss_response = request.json()
    ns_uuids = [ns.get('id') for ns in nss_response]

    # TODO: what if more than one NSs are running
    # if len(ns_uuids):
    #     raise Exception("More that one NSs are running...")

    vnf_uuid = None

    for ns_uuid in ns_uuids:
        vnf = Vnf(token)
        request = vnf.get_list_by_ns(ns_uuid=ns_uuid)
        vnfs = request.json()
        for i in vnfs:
            cur_vnfd_name_index = "{}.{}".format(i.get("vnfd-ref"), i.get("member-vnf-index-ref"), )
            if vnfd_name_index == cur_vnfd_name_index:
                return i.get("id")

    return vnf_uuid


def discover_vnfr_using_ip(ip_address=None):
    """Discover the VNF based on the assigned IP

    Args:
        ip_address (str): The assigned IP in VM

    Returns:
        dict: The VNF

    Raises:
        NotFoundVnfWithGivenIP: in case that there is no VNF/VDU having the given IP
    """
    token = bearer_token(OSM_ADMIN_CREDENTIALS.get('username'),
                         OSM_ADMIN_CREDENTIALS.get('username'))
    vnfr = Vnf(token)
    vnfrs = vnfr.get_list()
    vnf_records = vnfrs.json()

    for vnf_record in vnf_records:
        # todo: improve it in case of multiple VDUs per VNF
        vnf_ip_address = vnf_record.get('ip-address', None)
        if vnf_ip_address is not None and vnf_ip_address == ip_address:
            return vnf_record
    raise VduWithIpNotFound("Not found VDU with given IP: {}".format(ip_address))


def convert_unix_timestamp_to_datetime_str(unix_ts):
    """Convert a unix timestamp in stringify datetime (UTC)

    Args:
        unix_ts (int): The timestamp in unix

    Returns:
        str: The datetime in str (UTC)

    Example:
        >>> from datetime import datetime
        >>> from translator.utils import convert_unix_timestamp_to_datetime_str
        >>> unix_ts = 1527165350
        >>> dt_str = convert_unix_timestamp_to_datetime_str(unix_ts)
        >>> print(dt_str)
        2018-05-24T12:35:50.000000Z
    """
    dt = datetime.utcfromtimestamp(unix_ts)
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')


def convert_bytes_psec_to_mbits_psec(value):
    """Convert bytes/sec to megabits/sec

    Args:
        value (float): bytes per sec

    Returns:
        float: megabits per sec
    """
    return round(8 * value / pow(10, 6), 3)


def fetch_vdu_metric_record_from_influx(vdu_uuid, metric_type):
    """Fetch the record for a vdu by given the metric type

    Args:
        vdu_uuid (str): The VDU uuid
        metric_type (str): The metric type

    Returns:
        dcit: the keys-values of the record if selector exists.
    """
    influx_client = InfluxDBClient(host=INFLUX_DATABASES['default']['HOST'],
                                   port=INFLUX_DATABASES['default']['PORT'],
                                   username=INFLUX_DATABASES['default']['USERNAME'],
                                   password=INFLUX_DATABASES['default']['PASSWORD'],
                                   database=INFLUX_DATABASES['default']['NAME'], )

    selector = "select * from \"{}\" order by time desc limit 1500".format(metric_type)
    # selector = "select * from \"{}\"".format(metric_type)
    rs = influx_client.query(selector)
    records = list(rs.get_points(tags={"vdu_uuid": vdu_uuid}))
    return records[0]


def format_influx_measurement_record(record):
    """Format the record from Influx in proper manner for the insertion in Kafka bus

    Args:
        record (dict): The measurement record after query in influxDB

    Returns:
        dict: OSM-related information
    """
    flavor = {
        "vcpus": record.get("vdu_flavor_vcpus", None),
        "disk": record.get("vdu_flavor_disk", None),
        "ram": record.get("vdu_flavor_ram", None)
    }
    return {
        "ns": {
            "id": record.get('ns_uuid', None),
            "name": record.get('ns_name', None),
            "nsd_id": record.get('nsd_id', None),
            "nsd_name": record.get('nsd_name', None)
        },
        "vnf": {
            "id": record.get("vnf_uuid", None),
            "name": record.get("vnf_name", None),
            "short_name": record.get("vnf_short_name", None),
            "vnfd_id": record.get('vnfd_id', None),
            "vnfd_name": record.get('vnfd_name', None)
        },
        "vdu": {
            "id": record.get("vdu_uuid", None),
            "image_id": record.get("vdu_image_uuid", None),
            "flavor": flavor,
            "status": record.get("vdu_state", None),
            "ip_address": record.get("ip_address", None),
            "mgmt-interface": record.get("mgmt-interface", None)
        }
    }


def count_running_ns():
    """Find the number of the instantiated NSs in OSM r4
    """
    running_ns = 0
    token = bearer_token(OSM_ADMIN_CREDENTIALS.get('username'),
                         OSM_ADMIN_CREDENTIALS.get('username'))

    ns = Ns(token)
    request = ns.get_list()
    ns_list = request.json()

    for i in ns_list:
        if i.get("operational-status") == "running":
            running_ns += 1
    return running_ns


def compose_redis_key(vim_name, identifier, identifier_type="vdu"):
    """Compose the key for redis given vim name and vdu uuid

    Args:
        vim_name (str): The VIM name
        identifier (str): The VDU or VNF uuid (NFVI based)
        identifier_type (str): the identifier type. Default type is vdu. Also vnf is supported.

    Returns:
        str: the key for redis
    """
    if identifier_type == "vnf":
        return "{}:vnf#{}".format(vim_name.lower(), identifier)
    else:
        return "{}:{}".format(vim_name.lower(), identifier)


def convert_bytes_to_str(message):
    """Convert bytes to str phrase
    """
    return message.decode('utf8', 'ignore')


def vtranscoder3d_metrics():
    """Details about the UC1/vTranscoder3D (multiple qualities)

    Returns:
        dict: the metrics info
    """
    # For single quality, add the following metrics:
    # --------------------
    # "output_mesh_quality": {"unit": "", "type": "gauge"},
    # "output_mesh_number_of_vertices": {"unit": "counter", "type": "gauge"},
    # "output_mesh_bits_per_vertex": {"unit": "bpv", "type": "gauge"},
    # "output_mesh_encoding_time_ms": {"unit": "ms", "type": "gauge"},
    # "output_mesh_size_bytes": {"unit": "bytes", "type": "gauge"},
    # "input_textures_processing_unit": {"unit": "GPU ", "type": "gauge"},
    # "input_textures_decoding_time_ms": {"unit": "ms", "type": "gauge"},
    # "output_textures_type": {"unit": "", "type": "gauge"},
    # "output_textures_processing_unit": {"unit": "", "type": "gauge"},
    # "output_textures_quality": {"unit": "", "type": "gauge"},
    # "output_textures_width_pixels": {"unit": 'pixels', "type": "gauge"},
    # "output_textures_height_pixels": {"unit": 'pixels', "type": "gauge"},
    # "output_textures_bits_per_pixel": {"unit": "bpp", "type": "gauge"},
    # "output_textures_encoding_time_ms": {"unit": "ms", "type": "gauge"},
    # "output_textures_size_bytes": {"unit": "bytes", "type": "gauge"},

    return {
        "transcoder_engine": {"unit": "v", "type": "gauge"},
        "frame_count": {"unit": "counter", "type": "gauge"},
        "working_fps": {"unit": "fps", "type": "gauge"},
        "no_of_profiles_produced": {"unit": "number", "type": "gauge"},
        "total_transcoding_time_ms": {"unit": "ms", "type": "gauge"},
        "theoretic_load_percentage": {"unit": "%", "type": "gauge"},
        "input_data_bytes": {"unit": "bytes", "type": "gauge"},
        "output_data_bytes": {"unit": "bytes", "type": "gauge"},
        "input_mesh_codec": {"unit": "", "type": "gauge"},
        "input_mesh_decoding_time_ms": {"unit": "ms", "type": "gauge"},
        "output_mesh_codec": {"unit": "", "type": "gauge"},
        "no_of_input_textures": {"unit": "counter", "type": "gauge"},
    }


def vcache_metrics():
    """ Get the unit and type per metric of UC3/vCache

    Returns:
        dict: the metrics info
    """
    return {
        'bytes_recv': {"unit": "bytes", "type": "gauge"},
        'bytes_sent': {"unit": "bytes", "type": "gauge"},
        "drop_in": {"unit": "number", "type": "gauge"},
        "drop_out": {"unit": "number", "type": "gauge"},
        "err_in": {"unit": "errors", "type": "gauge"},
        "err_out": {"unit": "errors", "type": "gauge"},
        "packets_recv": {"unit": "packets", "type": "gauge"},
        "packets_sent": {"unit": "packets", "type": "gauge"},
        'cache.ram_cache.bytes_used': {"unit": "bytes", "type": "gauge"},
        'hostdb.cache.total_hits': {"unit": "hits", "type": "gauge"},
        'http.completed_requests': {"unit": "requests", "type": "gauge"},
        'http.current_active_client_connections': {"unit": "number", "type": "gauge"},
        'http.current_client_connections': {"unit": "number", "type": "gauge"},
        'http.user_agent_current_connections_count': {"unit": "number", "type": "gauge"},
    }


def vcache_lb_metrics():
    """ Get the unit and type per metric of UC3/vCache + LB

    Returns:
        dict: the metrics info
    """
    return {
        'cache.ram_cache.bytes_used': {"unit": "bytes", "type": "gauge"},
        'hostdb.cache.total_hits': {"unit": "hits", "type": "gauge"},
        'http.completed_requests': {"unit": "requests", "type": "cumulative"},
        'http.current_active_client_connections': {"unit": "number", "type": "gauge"},
        'http.current_client_connections': {"unit": "number", "type": "gauge"},
        'http.user_agent_current_connections_count': {"unit": "number", "type": "gauge"},
    }


def vce_metrics():
    """Details about the UC2/vCE

    Returns:
        dict: the metrics info
    """
    return {
        "pid_cpu": {"unit": "%", "type": "gauge"},
        "pid_ram": {"unit": "bytes", "type": "gauge"},
        "gop_size": {"unit": "number", "type": "gauge"},
        "num_fps": {"unit": "fps", "type": "gauge"},
        "num_frame": {"unit": "frames", "type": "gauge"},
        "enc_quality": {"number": "", "type": "gauge"},
        "enc_dbl_time": {"unit": "seconds", "type": "gauge"},
        "enc_str_time": {"unit": "hh:mm:ss.ms", "type": "gauge"},
        "max_bitrate": {"unit": "kbps", "type": "gauge"},
        "avg_bitrate": {"unit": "kbps", "type": "gauge"},
        "act_bitrate": {"unit": "kbps", "type": "gauge"},
        "enc_speed": {"unit": "kbps", "type": "gauge"}
    }


def opennebula_metrics():
    """Get details for the OpenNebula metrics"""
    return {
        "memory": {"type": "gauge", "unit": "kbytes"},
        "vcpu": {"type": "gauge", "unit": "vcpu"},
        "nettx": {"type": "gauge", "unit": "bytes"},
        "netrx": {"type": "gauge", "unit": "bytes"},
        "diskrdbytes": {"type": "gauge", "unit": "bytes"},
        "diskwrbytes": {"type": "gauge", "unit": "bytes"},
        "diskwriops": {"type": "gauge", "unit": "iops"},
        "diskrdiops": {"type": "gauge", "unit": "iops"},
        "disk_size": {"type": "gauge", "unit": "mbytes"}
    }
