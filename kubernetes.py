import json
import logging
import redis
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from settings import KAFKA_SERVER, KAFKA_CLIENT_ID, KAFKA_API_VERSION, KAFKA_MONITORING_TOPICS, \
    LOGGING, KAFKA_GROUP_ID, KAFKA_TRANSLATION_TOPIC, REDIS_HOST, REDIS_PORT, REDIS_NFVI_DB, \
    KAFKA_TIMEOUT, REDIS_EXPIRATION_SECONDS
from translator.utils import compose_redis_key, convert_bytes_to_str
from translator.exceptions import VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist, \
    VduUuidMissRedis
from translator import kubernetes

logging.config.dictConfig(LOGGING)
logger = logging.getLogger("kubernetes")


def main():
    nfvi = "kubernetes"
    # Set the consumer to listens to proper set of topics
    consumer = KafkaConsumer(bootstrap_servers=KAFKA_SERVER, client_id=KAFKA_CLIENT_ID,
                             enable_auto_commit=True, api_version=KAFKA_API_VERSION,
                             group_id=KAFKA_GROUP_ID[nfvi])
    consumer.subscribe(pattern=KAFKA_MONITORING_TOPICS[nfvi])
    redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_NFVI_DB)

    # The K8s publisher provides us the `container_id` as reference that maps to the
    # OSM vim_id entry. Therefore, this is the key that we can use. Each message
    # includes (one or more) metrics for the same container
    for msg in consumer:
        try:
            topic = msg.topic
            # Retrieve the Container id and the type of the metric
            metric = json.loads(msg.value.decode('utf-8', 'ignore'))
            container_id = metric.get("container_id", None)

            # Todo: filtering if needed

            # Get the metrics (if any)
            metrics = metric.get("data", [])

            # init translator
            translator = kubernetes.Metric(raw_metric=metrics[0], source=nfvi)

            # Retrieve information related to the MANO including VIM, NS, VNF, VDU.
            # A request will be performed in the Redis using the concatenation of topic,
            # container_id as key. In case that no entry exists in the Redis, a request
            # will be done in the OSM NBI API. After the successful retrieval, the MANO
            # data are stored in the Redis for future usage.
            mano_data = generate_payload(translator, redis_conn, topic, container_id)

            # Publish the value(s) in the Kafka bus, in translation-specific-topic
            publish_messages(metrics, mano_data)

        except VduUuidMissRedis as ex:
            logger.info(ex)
        except (VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist) as exc:
            logger.warning(exc)
        except json.decoder.JSONDecodeError as je:
            logger.error("JSONDecodeError: {}".format(je))
        except Exception as ex:
            logger.exception(ex)


def generate_payload(translator, redis_connection, topic, container_id):
    """ Fetch the OSM related data given the container id

    Args:
        translator (object): The translator object
        redis_connection (object): The redis connection object
        topic (str): The topic name
        container_id (str): The container ID

    Returns:
        dict: the OSM related data

    Raises:
        OsmInfoNotFound: if VUD uuid (container id) does not exist in OSM records
    """
    redis_key = compose_redis_key(topic, container_id)
    cached_value_bytes = redis_connection.get(name=redis_key)

    if cached_value_bytes is not None:
        # Load the relevant OSM entry from the redis
        record = json.loads(convert_bytes_to_str(cached_value_bytes))
        if record.get('status', 404) == 404:
            raise VduUuidMissRedis(
                "OSM data not found for the k8s container id: `{}`".format(container_id))
        mano_data = record.get('mano')
    else:
        # mano_data = translator.get_translation(container_id)
        mano_data = translator.get_translation_vnf_on_demand(container_id)
        mano_data_len = len(mano_data)

        # Keep status in redis to highlight if a VDU record exists in OSM or not.
        # If VDU does not exist use status 404 and ignore it in the next redis read.
        if not mano_data_len:
            redis_record = {"status": 404}
        else:
            redis_record = {"status": 200, "mano": mano_data}
            logger.info("Load OSM entry for k8s container id: `{}` from OSM".format(container_id))

        # Save the entry in the Redis
        redis_connection.set(name=redis_key, value=json.dumps(redis_record),
                             ex=REDIS_EXPIRATION_SECONDS)

        if not mano_data_len:
            raise OsmInfoNotFound(
                "OSM related-data not found for the container id: `{}`".format(container_id))

    return mano_data


def publish_messages(metrics, mano_data):
    """Send the metrics in Kafka bus

    Args:
        metrics (list): The list of the translated metrics
        mano_data (dict): The OSM related data
    """
    producer = KafkaProducer(bootstrap_servers=KAFKA_SERVER, api_version=KAFKA_API_VERSION,
                             value_serializer=lambda v: json.dumps(v).encode('utf-8'))
    for metric in metrics:
        t = producer.send(KAFKA_TRANSLATION_TOPIC, {"metric": metric, "mano": mano_data})
        # Block for 'synchronous' send for at most X seconds.
        try:
            t.get(timeout=KAFKA_TIMEOUT)
        except KafkaError as ke:
            logger.error(ke)
            pass
    producer.close()


if __name__ == '__main__':
    # Entry point
    main()
