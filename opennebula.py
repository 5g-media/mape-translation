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
from translator import opennebula as one

logging.config.dictConfig(LOGGING)
logger = logging.getLogger("opennebula")


def main():
    nfvi = "opennebula"
    # Set the consumer to listens to proper set of topics
    consumer = KafkaConsumer(bootstrap_servers=KAFKA_SERVER, client_id=KAFKA_CLIENT_ID,
                             enable_auto_commit=True,
                             api_version=KAFKA_API_VERSION, group_id=KAFKA_GROUP_ID[nfvi])
    consumer.subscribe(pattern=KAFKA_MONITORING_TOPICS[nfvi])
    redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_NFVI_DB)

    # The OpenNebula publisher provides us the `vdu_uuid` as reference that maps to the
    # OSM vim_id entry. Therefore, this is the key that we can use.
    for msg in consumer:
        try:
            topic = msg.topic
            # Retrieve the metric record
            metric = json.loads(msg.value.decode('utf-8', 'ignore'))
            vdu_uuid = get_vdu(metric)

            # Todo: filtering if needed

            # Init the OpenNebula translator
            translator = one.Metric(raw_metric=metric, source=nfvi)

            # Retrieve information related to the MANO including VIM, NS, VNF, VDU.
            # A request will be performed in the Redis using the concatenation of topic,
            # vdu_uuid as key. In case that no entry exists in the Redis, a request will
            # be done in the OSM NBI API. After the successful retrieval, the MANO data
            # are stored in the Redis for future usage.
            adapted_metric = generate_payload(translator, redis_conn, topic, vdu_uuid)

            # Publish the value(s) in the Kafka bus, in translation-specific-topic
            publish_message(adapted_metric)

        except VduUuidMissRedis as ex:
            logger.info(ex)
        except (VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist) as exc:
            logger.warning(exc)
        except json.decoder.JSONDecodeError as je:
            logger.error("JSONDecodeError: {}".format(je))
        except Exception as ex:
            logger.exception(ex)


def get_vdu(metric):
    """ Get the VDU uuid

    Args:
        metric (dict): The incoming message

    Returns:
        str: the VDU uuid

    Raises:
        VduUuidDoesNotExist: if the VDU uuid is not provided in the message
    """
    vdu_uuid = metric.get("vdu_uuid", None)
    if not vdu_uuid:
        raise VduUuidDoesNotExist("The OpenNebula VDU uuid is not available")
    return "{}".format(vdu_uuid)


def generate_payload(translator, redis_connection, topic, vdu_uuid):
    """ Compose a uniform payload

    Args:
        translator (object): The translator object
        redis_connection (object):  The redis connection object
        topic (str): The kafka topic
        vdu_uuid (str): The VDU uuid in OpenStack

    Returns:
        dict: The metric as well as the mano-related data

    Raises:
        OsmInfoNotFound: if VDU uuid does not exist in OSM records
    """
    redis_key = compose_redis_key(topic, vdu_uuid)
    cached_value_bytes = redis_connection.get(name=redis_key)

    if cached_value_bytes is not None:
        # Load the relevant OSM entry from the redis
        record = json.loads(convert_bytes_to_str(cached_value_bytes))
        if record.get('status', 404) == 404:
            raise VduUuidMissRedis("OSM data not found for the VDU uuid: `{}`".format(vdu_uuid))
        mano_data = record.get('mano')
        logger.debug("Load OSM entry for OpenNebula VM uuid: `{}` from Redis".format(vdu_uuid))
    else:
        # Generate a uniform structure for each metric
        mano_data = translator.get_translation(vdu_uuid)
        mano_data_len = len(mano_data)

        # Keep status in redis to highlight if a VDU record exists in OSM or not.
        # If VDU does not exist use status 404 and ignore it in the next redis read.
        if not mano_data_len:
            redis_record = {"status": 404}
        else:
            redis_record = {"status": 200, "mano": mano_data}
            logger.info("Load OSM entry for OpenNebula vdu uuid: `{}` from OSM ".format(vdu_uuid))

        # Save the entry in the Redis
        redis_connection.set(name=redis_key, value=json.dumps(redis_record),
                             ex=REDIS_EXPIRATION_SECONDS)

        if not mano_data_len:
            raise OsmInfoNotFound(
                "OSM related-data not found for the VDU uuid: `{}`".format(vdu_uuid))

    return {"metric": translator.get_metric(), "mano": mano_data}


def publish_message(adapted_metric):
    """Send the metric in Kafka bus

    Args:
        adapted_metric (dict): The translated metric
    """
    producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER, api_version=KAFKA_API_VERSION,
                             value_serializer=lambda v: json.dumps(v).encode('utf-8'))

    t = producer.send(KAFKA_TRANSLATION_TOPIC, adapted_metric)
    # Block for 'synchronous' send for at most X seconds.
    try:
        t.get(timeout=KAFKA_TIMEOUT)
    except KafkaError as ke:
        logger.error(ke)
        pass
    producer.close()


if __name__ == '__main__':
    main()
