import json
import logging.config
import redis
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from settings import KAFKA_SERVER, KAFKA_CLIENT_ID, KAFKA_API_VERSION, KAFKA_MONITORING_TOPICS, \
    LOGGING, KAFKA_GROUP_ID, KAFKA_TRANSLATION_TOPIC, REDIS_HOST, REDIS_PORT, REDIS_NFVI_DB, \
    KAFKA_TIMEOUT, REDIS_EXPIRATION_SECONDS
from translator.utils import compose_redis_key, convert_bytes_to_str, \
    discover_vdu_uuid_by_vnf_index, discover_vnf_uuid_by_vnfd_name_index
from translator.exceptions import VnfNotFound, OsmInfoNotFound, InvalidTranscoderId, \
    VduUuidMissRedis
from translator.apps import vtranscoder3d_spectators

NFVI_OR_APP = "vtranscoder3d_spectators"

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
                             group_id=KAFKA_GROUP_ID[scope])
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
    """Main process"""
    kafka_consumer = init_consumer(scope=NFVI_OR_APP)
    kafka_consumer.subscribe(pattern=KAFKA_MONITORING_TOPICS[NFVI_OR_APP])
    redis_conn = init_redis_connection()

    # Consume the metrics coming from the vTranscoder3D spectators in the UC1.
    # See Also: samples/uc1-vTranscoder3D/input/spectators_review.json
    for msg in kafka_consumer:
        topic = msg.topic
        try:
            payload = json.loads(msg.value.decode('utf-8', 'ignore'))
            client_id = payload['client_id']
            group_id = payload.get('group_id', "unknown")
            timestamp = int(str(payload['timestamp']).split('.')[0])
            incoming_streams = payload.get('incoming_streams', [])
            spectator = {"client_id": client_id, "group_id": group_id}

            for stream in incoming_streams:
                try:
                    # Discover the VNF uuid by given the vnfd name & index and store it in redis
                    vnf_uuid = get_vnf_uuid(redis_conn, stream, topic)
                    # Get quality ID and original metrics
                    quality_id = stream.get("quality_id", None)
                    original_metrics = stream.get("metrics", [])

                    translator = vtranscoder3d_spectators.Metric(
                        client_id, group_id, timestamp, quality_id, original_metrics,
                        source=NFVI_OR_APP)

                    # Retrieve information related to the MANO including VIM, NS, VNF, VDU.
                    # A request will be performed in the Redis using the concatenation of
                    # topic, vdu_uuid as key. In case that no entry exists in the Redis, a
                    # request will be done in the OSM NBI API. After the successful retrieval,
                    # the MANO data are stored in the Redis for future usage.
                    mano_data = generate_payload(translator, redis_conn, topic, vnf_uuid)

                    stream_metrics = translator.get_metrics()
                    # Publish the value(s) in the Kafka bus, in translation-specific-topic
                    publish_messages(stream_metrics, mano_data, spectator)

                except VduUuidMissRedis as ex:
                    logger.info(ex)
                except (VnfNotFound, InvalidTranscoderId, OsmInfoNotFound) as exc:
                    logger.warning(exc)

        except (VnfNotFound, OsmInfoNotFound) as ex:
            logger.warning(ex)
        except json.decoder.JSONDecodeError as je:
            logger.error("JSONDecodeError: {}".format(je))
        except Exception as ex:
            logger.exception(ex)


def get_vnf_uuid(redis_connection, stream, topic):
    """ Get the VNF uuid, if any

    Args:
        redis_connection (object): The redis connection object
        stream (dict): The stream
        topic (str): The Kafka topic

    Returns:
        str: the VNF uuid

    Raises:
        InvalidTranscoderId: if the transcoder ID is not valid
        VnfNotFound: if VNF uuid does not exist
    """
    transcoder_id = stream.get("transcoder_id", None)
    if transcoder_id is None:
        raise InvalidTranscoderId(
            'Invalid transcoder_id value. Its value is {}'.format(transcoder_id))

    try:
        if int(transcoder_id) == 0:
            raise InvalidTranscoderId('Invalid transcoder_id value. Its value is {}'.format(
                transcoder_id))
    except ValueError:
        pass

    search_for_transcoder_id = "{}:{}".format(topic, transcoder_id)
    cached_vnf_uuid_bytes = redis_connection.get(name=search_for_transcoder_id)

    if cached_vnf_uuid_bytes is not None:
        vnf_uuid = convert_bytes_to_str(cached_vnf_uuid_bytes)
    else:
        vnf_uuid = discover_vnf_uuid_by_vnfd_name_index(transcoder_id)
        if vnf_uuid is not None:
            redis_connection.set(name=search_for_transcoder_id,
                                 value="{}".format(vnf_uuid), ex=300)  # 5 minutes

    logger.debug("VNF is {} for id {}".format(vnf_uuid, transcoder_id))

    quality_id = stream.get("quality_id", None)
    if vnf_uuid is None or quality_id is None:
        raise VnfNotFound('The VNF uuid does not exist in the consumed message')
    vnf_uuid = vnf_uuid.replace(" ", "_")
    return vnf_uuid


def generate_payload(translator, redis_connection, topic, vnf_uuid):
    """ Get the OSM related data

    Args:
        translator (object): The translator object
        redis_connection (object): The redis connection object
        topic (str): The kafka topic
        vnf_uuid (str): The VNF uuid

    Returns:
        dict: The mano-related data

    Raises:
       OsmInfoNotFound
    """
    redis_key = compose_redis_key(topic, vnf_uuid, identifier_type='vnf')
    cached_value_bytes = redis_connection.get(name=redis_key)

    if cached_value_bytes is not None:
        # Load the relevant OSM-info entry from the redis
        record = json.loads(convert_bytes_to_str(cached_value_bytes))
        if record.get('status', 404) == 404:
            raise VduUuidMissRedis(
                "OSM data not found in Redis for the VNF uuid: `{}`".format(vnf_uuid))
        mano_data = record.get('mano')
        logger.debug("Load OSM entry for vTranscoder3D VNF uuid: `{}` from Redis".format(
            vnf_uuid))
    else:
        # Generate a standard structure for each metric
        mano_data = translator.get_translation(vnf_uuid)
        mano_data_len = len(mano_data)

        # Keep status in redis to highlight if a VNF record exists in OSM or not.
        # If VNF does not exist use status 404 and ignore it in the next redis read.
        if not mano_data_len:
            redis_record = {"status": 404}  # 404 means means that VNF uuid does not exist in OSM
        else:
            redis_record = {"status": 200, "mano": mano_data}  # 200 means VNF uuid exists in OSM
            logger.debug(
                "Load OSM entry for vTranscoder3D VNF uuid: `{}` from OSM".format(vnf_uuid))

        # Save the entry in the Redis
        redis_connection.set(name=redis_key, value=json.dumps(redis_record),
                             ex=REDIS_EXPIRATION_SECONDS)
        if not mano_data_len:
            raise OsmInfoNotFound(
                "OSM data not found in OSM API for the VNF uuid: `{}`".format(vnf_uuid))
    return mano_data


def publish_messages(metrics, mano_data, spectator):
    """ Send the translated metrics in Kafka bus

    Args:
        metrics (list): The list of metrics
        mano_data (dict): The OSM details for the given VNF
        spectator (dict): The spectator details (client/group)
    """
    producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER, api_version=KAFKA_API_VERSION,
                             value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    for m in metrics:
        adapted_metric = {"metric": m, "mano": mano_data, "spectator": spectator}
        t = producer.send(KAFKA_TRANSLATION_TOPIC, adapted_metric)
        # Block for 'synchronous' sends for X seconds
        try:
            t.get(timeout=KAFKA_TIMEOUT)
        except KafkaError as ke:
            logger.error(ke)

    producer.close()


if __name__ == '__main__':
    main()
