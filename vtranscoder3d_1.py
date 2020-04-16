import json
import logging.config
import redis
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from settings import KAFKA_SERVER, KAFKA_CLIENT_ID, KAFKA_API_VERSION, KAFKA_MONITORING_TOPICS, \
    LOGGING, KAFKA_GROUP_ID, KAFKA_TRANSLATION_TOPIC, REDIS_HOST, REDIS_PORT, REDIS_NFVI_DB, \
    KAFKA_TIMEOUT, REDIS_EXPIRATION_SECONDS
from translator.utils import compose_redis_key, convert_bytes_to_str, discover_vdu_uuid_by_vnf_index
from translator.exceptions import VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist, \
    VnfIndexInvalid, VduUuidMissRedis
from translator.apps import vtranscoder3d

NFVI_OR_APP = "vtranscoder3d"

logging.config.dictConfig(LOGGING)
logger = logging.getLogger(NFVI_OR_APP)


def init_consumer(scope=None):
    """ Init the Kafka consumer

    # See more: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaConsumer.html

    Args:
        scope (str): The origin of the metrics

    Returns:
        Iterator: The kafka consumer
    """
    consumer = KafkaConsumer(bootstrap_servers=KAFKA_SERVER,
                             client_id=KAFKA_CLIENT_ID,
                             enable_auto_commit=True,
                             api_version=KAFKA_API_VERSION,
                             group_id="MAPE_VTRANSCODER_1_METRICS_CG")
    return consumer


def init_redis_connection():
    """ Init the connection with Redis

    # See more: https://redis-py.readthedocs.io/en/latest/

    Returns:
        object
    """
    redis_conn = redis.Redis(host=REDIS_HOST,
                             port=REDIS_PORT,
                             db=REDIS_NFVI_DB)
    return redis_conn


def main():
    """ Main process """
    consumer = init_consumer()
    consumer.subscribe("1_metrics")
    redis_conn = init_redis_connection()

    # Consume the metrics coming from the cTranscoder3D in the UC1.
    # See Also: samples/uc1-vTranscoder3D/input/multiple_transcoder_qualities.json
    for msg in consumer:
        try:
            topic = msg.topic
            # Process the message
            metric = json.loads(msg.value.decode('utf-8', 'ignore'))

            # Retrieve the VDU uuid
            # The vTranscoder metric includes the vnf_index as vdu_uuid. Not so safe.
            # TODO: What if we have more that NS?
            vdu_uuid = get_vdu(redis_conn, topic, metric)

            # Init the app translator
            translator = vtranscoder3d.Metric(record=metric, source=NFVI_OR_APP)

            # Retrieve information related to the MANO including VIM, NS, VNF, VDU.
            # A request will be performed in the Redis using the concatenation of topic,
            # vdu_uuid as key. In case that no entry exists in the Redis, a request will
            # be done in the OSM NBI API. After the successful retrieval, the MANO data
            # are stored in the Redis for future usage.
            mano_data = generate_payload(translator, redis_conn, topic, vdu_uuid)

            # Publish the value(s) in the Kafka bus, in translation-specific-topic
            metrics = translator.get_metrics()
            publish_messages(metrics, mano_data)

        except VduUuidMissRedis as ex:
            logger.info(ex)
        except (VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist, VnfIndexInvalid) as exc:
            logger.warning(exc)
        except json.decoder.JSONDecodeError as je:
            logger.error("JSONDecodeError: {}".format(je))
        except Exception as ex:
            logger.exception(ex)


def get_vdu(redis_connection, topic, metric):
    """ Get the VDU by using the VNF index

    Args:
        redis_connection (object): Teh redis connection object
        topic (str): The kafka topic
        metric (dict): The incoming message

    Returns:
        str: the VDU uuid (aka container id)

    Raises:
        VnfIndexInvalid: if the VNF index is not valid or does not exist
        VduUuidDoesNotExist: if the VDU uuid does not exist
    """
    vdu_uuid = None
    vnf_index = metric.get("vdu_uuid", None)
    if vnf_index is None or int(vnf_index) == 0:
        raise VnfIndexInvalid('Invalid vnf_index value. Its value is {}'.format(vnf_index))

    # Discover the vdu given the vnf index
    search_for_vnf_index = "{}:vnf_index_{}".format(topic, vnf_index)
    cached_vdu_uuid_bytes = redis_connection.get(name=search_for_vnf_index)

    if cached_vdu_uuid_bytes is not None:
        vdu_uuid = convert_bytes_to_str(cached_vdu_uuid_bytes)
    else:
        vdu_uuid = discover_vdu_uuid_by_vnf_index(vnf_index)
        if vdu_uuid is None:
            raise VduUuidDoesNotExist('The VDU uuid for does not exist in the consumed message')

        redis_connection.set(name=search_for_vnf_index, value="{}".format(vdu_uuid),
                             ex=300)  # 5 minutes

    logger.debug("VDU uuid is {} for id {}".format(vdu_uuid, vnf_index))
    return vdu_uuid


def generate_payload(translator, redis_connection, topic, vdu_uuid):
    """ Get the OSM related data

    Args:
        translator (object): The translator object
        redis_connection (object): The redis connection object
        topic (str): The kafka topic
        vdu_uuid (str): The VDU uuid in OpenStack

    Returns:
        dict: The mano-related data

    Raises:
        OsmInfoNotFound: if VDU uuid does not exist in OSM records
    """
    redis_key = compose_redis_key(topic, vdu_uuid, identifier_type='vdu')
    cached_value_bytes = redis_connection.get(name=redis_key)

    if cached_value_bytes is not None:
        # Load the relevant OSM-info entry from the redis
        record = json.loads(convert_bytes_to_str(cached_value_bytes))
        if record.get('status', 404) == 404:
            raise VduUuidMissRedis(
                "OSM data not found in Redis for the VDU uuid: `{}`".format(vdu_uuid))
        mano_data = record.get('mano')
        logger.debug("Load OSM entry for vTranscoder3D VDU uuid: `{}` from Redis".format(vdu_uuid))
    else:
        # Generate a standard structure for each metric
        mano_data = translator.get_translation(vdu_uuid)
        mano_data_len = len(mano_data)

        # Keep status in redis to highlight if a VDU record exists in OSM or not.
        # If VDU does not exist use status 404 and ignore it in the next redis read.
        if not mano_data_len:
            redis_record = {"status": 404}  # 404 means means that VDU uuid does not exist in OSM
        else:
            redis_record = {"status": 200, "mano": mano_data}  # 200 means VDU uuid exists in OSM
            logger.info("Load OSM data for vTranscoder3D VDU uuid: `{}` from OSM ".format(vdu_uuid))

        # Save the entry in the Redis
        redis_connection.set(name=redis_key, value=json.dumps(redis_record),
                             ex=REDIS_EXPIRATION_SECONDS)

        if not mano_data_len:
            raise OsmInfoNotFound(
                "OSM data not found in OSM API for the VDU uuid: `{}`".format(vdu_uuid))

    return mano_data


def publish_messages(metrics, osm_data):
    """ Send the translated metrics in Kafka bus

    Args:
        metrics (list): The metric after the translation
        osm_data (dict): The OSM details for the given VNF
    """
    producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER, api_version=KAFKA_API_VERSION,
                             value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    for metric in metrics:
        t = producer.send(KAFKA_TRANSLATION_TOPIC, {"metric": metric, "mano": osm_data})
        # Block for 'synchronous' sends for X seconds
        try:
            t.get(timeout=KAFKA_TIMEOUT)
        except KafkaError as ke:
            logger.error(ke)
            pass

    producer.close()


if __name__ == '__main__':
    main()
