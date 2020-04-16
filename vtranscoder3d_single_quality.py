import json
import logging.config
import redis
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from settings import KAFKA_SERVER, KAFKA_CLIENT_ID, KAFKA_API_VERSION, KAFKA_MONITORING_TOPICS, \
    LOGGING, KAFKA_GROUP_ID, KAFKA_TRANSLATION_TOPIC, REDIS_HOST, REDIS_PORT, REDIS_NFVI_DB, \
    KAFKA_TIMEOUT, REDIS_EXPIRATION_SECONDS
from translator.utils import compose_redis_key, convert_bytes_to_str
from translator.exceptions import VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist, \
    VduUuidMissRedis
from translator.apps import vtranscoder3d

logging.config.dictConfig(LOGGING)
logger = logging.getLogger('vtranscoder3d')


def main():
    nfvi_or_app = "vtranscoder3d"
    # See more: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaConsumer.html
    consumer = KafkaConsumer(bootstrap_servers=KAFKA_SERVER, client_id=KAFKA_CLIENT_ID,
                             enable_auto_commit=True,
                             api_version=KAFKA_API_VERSION, group_id=KAFKA_GROUP_ID[nfvi_or_app])
    consumer.subscribe(pattern=KAFKA_MONITORING_TOPICS[nfvi_or_app])

    # See more: https://redis-py.readthedocs.io/en/latest/
    redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_NFVI_DB)

    # Consume the metrics coming from the vTranscoder3D in the UC1.
    # The _VIM_VM_ID value maps to the k8s container ID. The same identifier is used in the
    # monitoring of container & pod.
    # See Also: samples/uc1-vTranscoder3D/input/vtranscoder_metrics.json
    for msg in consumer:
        try:
            topic = msg.topic
            # Process the message
            metric = json.loads(msg.value.decode('utf-8', 'ignore'))

            # Retrieve the VDU uuid
            vdu_uuid = metric.get("_VIM_VM_ID", None)
            if vdu_uuid is None:
                raise VduUuidDoesNotExist('The VDU uuid does not exist in the consumed message')

            # Init the VNF translator
            translator = vtranscoder3d.Metric(record=metric, source=nfvi_or_app)

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
        except (VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist) as exc:
            logger.warning(exc)
        except json.decoder.JSONDecodeError as je:
            logger.warning("JSONDecodeError: {}".format(je))
        except Exception as ex:
            logger.exception(ex)


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


def publish_messages(metrics, mano_data):
    """ Send the translated metrics in Kafka bus

    Args:
        translated_metric (dict): The metric after the translation
        mano_data (dict): The OSM details for the given VNF
    """
    producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER, api_version=KAFKA_API_VERSION,
                             value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    for metric in metrics:
        t = producer.send(KAFKA_TRANSLATION_TOPIC, {"metric": metric, "mano": mano_data})
        # Block for 'synchronous' sends for X seconds
        try:
            t.get(timeout=KAFKA_TIMEOUT)
        except KafkaError as ke:
            logger.error(ke)
            pass

    producer.close()


if __name__ == '__main__':
    main()
