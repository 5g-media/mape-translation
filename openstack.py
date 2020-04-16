import json
import logging
import redis
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from settings import KAFKA_SERVER, KAFKA_CLIENT_ID, KAFKA_API_VERSION, KAFKA_MONITORING_TOPICS, \
    LOGGING, KAFKA_GROUP_ID, KAFKA_TRANSLATION_TOPIC, REDIS_HOST, REDIS_PORT, REDIS_NFVI_DB, \
    REDIS_EXPIRATION_SECONDS, KAFKA_TIMEOUT
from translator.utils import consume_metric_or_not, yield_memory_metrics_from_flavor_openstack, \
    yield_vcpu_metric_from_flavor_openstack, compose_redis_key, convert_bytes_to_str
from translator.exceptions import VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist, \
    VduUuidMissRedis
from translator import openstack

logging.config.dictConfig(LOGGING)
logger = logging.getLogger("openstack")


def main():
    nfvi_or_app = "openstack"
    # See more: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaConsumer.html
    consumer = KafkaConsumer(bootstrap_servers=KAFKA_SERVER, client_id=KAFKA_CLIENT_ID,
                             enable_auto_commit=True,
                             api_version=KAFKA_API_VERSION, group_id=KAFKA_GROUP_ID[nfvi_or_app])
    consumer.subscribe(pattern=KAFKA_MONITORING_TOPICS[nfvi_or_app])

    # See more: https://redis-py.readthedocs.io/en/latest/
    redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_NFVI_DB)

    # The OpenStack provides us the `VM uuid` as reference, a.k.a the `VDU uuid`.
    # Therefore, this is the key that we can use.
    for msg in consumer:
        try:
            topic = msg.topic
            # Process the message
            metric = json.loads(msg.value.decode('utf-8', 'ignore'))
            source_type = metric.get("source").lower()
            metric_type = metric.get("counter_name", None)

            # Retrieve the VDU uuid
            vdu_uuid = metric.get("resource_metadata", {}).get('instance_id', None)
            if vdu_uuid is None:
                raise VduUuidDoesNotExist(
                    '[OpenStack] The VDU uuid does not exist in the consumed message')

            # Make dynamic filtering
            if not consume_metric_or_not(source_type, metric_type):
                continue

            if metric_type == "disk.device.usage":
                metric["counter_name"] = 'disk.usage'

            # Init the OpenStack translator
            translator = openstack.Metric(raw_metric=metric, source=nfvi_or_app)

            # Retrieve information related to the MANO including VIM, NS, VNF, VDU.
            # A request will be performed in the Redis using the concatenation of topic,
            # vdu_uuid as key. In case that no entry exists in the Redis, a request will be
            # done in the OSM NBI API. After the successful retrieval, the MANO data are
            # stored in the Redis for future usage.
            adapted_metric = generate_payload(translator, redis_conn, topic, vdu_uuid)

            # Publish the value(s) in the Kafka bus, in translation-specific-topic
            publish_messages(metric_type=metric_type, metric=adapted_metric)

        except VduUuidMissRedis as ex:
            logger.info(ex)
        except (VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist) as exc:
            logger.warning(exc)
        except json.decoder.JSONDecodeError as je:
            logger.error("JSONDecodeError: {}".format(je))
        except Exception as ex:
            logger.exception(ex)


def generate_payload(translator, redis_conn, topic, vdu_uuid):
    """ Compose a uniform payload

    Args:
        translator (object): The translator object
        redis_conn (object):  The redis connection object
        topic (str): The kafka topic
        vdu_uuid (str): The VDU uuid in OpenStack

    Returns:
        dict: The metric as well as the mano-related data

    Raises:
        OsmInfoNotFound: if VDU uuid does not exist in OSM records
    """
    redis_key = compose_redis_key(topic, vdu_uuid)
    cached_value_bytes = redis_conn.get(name=redis_key)

    if cached_value_bytes is not None:
        # Load the relevant OSM-info entry from the redis
        record = json.loads(convert_bytes_to_str(cached_value_bytes))
        if record.get('status', 404) == 404:
            raise VduUuidMissRedis("OSM data not found for the VDU uuid: `{}`".format(vdu_uuid))
        mano_data = record.get('mano')
        logger.debug("Load OSM entry for OpenStack vdu uuid: `{}` from Redis".format(vdu_uuid))
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
            logger.info(
                "Load OSM entry for OpenStack vdu uuid: `{}` from OSM ".format(vdu_uuid))

        # Save the entry in the Redis
        redis_conn.set(name=redis_key, value=json.dumps(redis_record),
                       ex=REDIS_EXPIRATION_SECONDS)

        if not mano_data_len:
            raise OsmInfoNotFound(
                "OSM related-data not found for the VDU uuid: `{}`".format(vdu_uuid))

    return {"metric": translator.get_metric(), "mano": mano_data}


def publish_messages(metric_type, metric):
    """ Send the translated metric in Kafka bus

    Args:
        metric_type (str): The type of the metric
        metric (dict): The metric after the translation

    Returns:
        None
    """
    producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER, api_version=KAFKA_API_VERSION,
                             value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    t = producer.send(KAFKA_TRANSLATION_TOPIC, metric)
    # Block for 'synchronous' sends for X seconds
    try:
        t.get(timeout=KAFKA_TIMEOUT)
    except KafkaError as ke:
        logger.error(ke)
        pass

    if metric_type == "memory.usage":
        metrics = yield_memory_metrics_from_flavor_openstack(metric)
        for item in metrics:
            x = producer.send(KAFKA_TRANSLATION_TOPIC, item)
            try:
                x.get(timeout=KAFKA_TIMEOUT)
            except KafkaError as ke:
                logger.error(ke)

    elif metric_type == "cpu":
        vcpu_metric = yield_vcpu_metric_from_flavor_openstack(metric)
        y = producer.send(KAFKA_TRANSLATION_TOPIC, vcpu_metric)
        try:
            y.get(timeout=KAFKA_TIMEOUT)
        except KafkaError as ke:
            logger.error(ke)

    producer.close()


if __name__ == '__main__':
    # Entry point
    main()
