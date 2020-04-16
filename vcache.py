import json
import logging
import redis
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from settings import KAFKA_SERVER, KAFKA_CLIENT_ID, KAFKA_API_VERSION, KAFKA_MONITORING_TOPICS, \
    LOGGING, KAFKA_GROUP_ID, KAFKA_TRANSLATION_TOPIC, REDIS_HOST, REDIS_PORT, REDIS_NFVI_DB, \
    REDIS_EXPIRATION_SECONDS, KAFKA_TIMEOUT
from translator.exceptions import VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist, \
    VduUuidMissRedis
from translator.apps import vcache
from translator.utils import vcache_lb_metrics, compose_redis_key, convert_bytes_to_str

logging.config.dictConfig(LOGGING)
logger = logging.getLogger("vcache")


def main():
    nfvi_or_app = "telegraf"  # vCache in UC3

    # See more: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaConsumer.html
    consumer = KafkaConsumer(bootstrap_servers=KAFKA_SERVER, client_id=KAFKA_CLIENT_ID,
                             enable_auto_commit=True,
                             api_version=KAFKA_API_VERSION, group_id=KAFKA_GROUP_ID[nfvi_or_app])
    consumer.subscribe(pattern=KAFKA_MONITORING_TOPICS[nfvi_or_app])

    # See more: https://redis-py.readthedocs.io/en/latest/
    redis_conn = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_NFVI_DB)

    # The telegraf agent is running on top of vCache providing `VM uuid` as reference,
    # a.k.a the `VDU uuid` in the host field. Thus, this is the key that we use.
    for msg in consumer:
        topic = msg.topic
        try:
            payload = json.loads(msg.value.decode('utf-8', 'ignore'))
            fields = payload.get("fields", {})
            fields_keys = list(fields.keys())
            fields_no = len(fields_keys)

            # Message filtering
            if fields_no == 1:
                # Check if metric from set C has received
                lb_metrics = vcache_lb_metrics()
                if fields_keys[0] not in lb_metrics.keys():
                    continue
            elif fields_no >= 2:
                # Check if set A has received
                if 'bytes_sent' not in fields_keys:
                    continue
            else:
                continue

            # Find the VDU uuid
            vdu_uuid = get_vdu(payload)

            # Init the vCache (telegraf) translator
            translator = vcache.Metric(source=nfvi_or_app)

            # Retrieve information related to the MANO including VIM, NS, VNF, VDU.
            # A request will be performed in the Redis using the concatenation of topic,
            # vdu_uuid as key. In case that no entry exists in the Redis, a request will
            # be done in the OSM NBI API. After the successful retrieval, the MANO data are
            # stored in the Redis for future usage.
            mano_data = generate_payload(translator, redis_conn, topic, vdu_uuid)

            metrics = translator.get_metrics(payload)
            publish_messages(metrics, mano_data)

        except VduUuidMissRedis as ex:
            logger.info(ex)
        except (VduNotFound, OsmInfoNotFound, VduUuidDoesNotExist) as exc:
            logger.warning(exc)
        except json.decoder.JSONDecodeError as je:
            logger.error("JSONDecodeError: {}".format(je))
        except Exception as ex:
            logger.exception(ex)


def get_vdu(payload):
    """ Get the VDU uuid if it exist

    Args:
        payload (dict): the data as these provided by telegraf agent

    Returns:
        str: the VDU uuid (lower case)

    Raises:
        VduUuidDoesNotExist:if VDU uuid is not available
    """
    vdu_uuid_upper = payload.get("tags", {}).get('host', None)
    if vdu_uuid_upper is None:
        raise VduUuidDoesNotExist("vCache VDU uuid is not available")
    return vdu_uuid_upper.lower()


def generate_payload(translator, redis_conn, topic, vdu_uuid):
    """ Compose a uniform payload

    Args:
        translator (object): The translator object
        redis_conn (object):  The redis connection object
        topic (str): The kafka topic
        vdu_uuid (str): The VDU uuid in OpenStack

    Returns:
        dict: The mano-related data

    Raises:
        OsmInfoNotFound: if VDU uuid does not exist in OSM records
    """
    redis_key = compose_redis_key(topic, vdu_uuid)
    cached_value_bytes = redis_conn.get(name=redis_key)

    if cached_value_bytes is not None:
        # Load the relevant OSM-info entry from the redis
        record = json.loads(convert_bytes_to_str(cached_value_bytes))
        if record.get('status', 404) == 404:
            raise VduUuidMissRedis(
                "OSM data not found in redis for the VDU uuid: `{}`".format(vdu_uuid))
        mano_data = record.get('mano')
        logger.debug("Load OSM data for OpenStack/vCache vdu uuid: `{}` from Redis".format(vdu_uuid))
    else:
        # Generate a uniform structure for each metric
        mano_data = translator.get_translation(vdu_uuid)
        mano_data_len = len(mano_data)

        # Keep status in redis to highlight if a VDU record exists in OSM or not.
        # If VDU does not exist use status 404 and ignore it in the next redis read.
        if not mano_data_len:
            redis_record = {"status": 404}  # 404 means means that VDU uuid does not exist in OSM
        else:
            redis_record = {"status": 200, "mano": mano_data}  # 200 means VDU uuid exists in OSM
            logger.info("Load OSM data for OpenStack vdu uuid: `{}` from OSM ".format(vdu_uuid))

        # Save the entry in the Redis
        redis_conn.set(name=redis_key, value=json.dumps(redis_record),
                       ex=REDIS_EXPIRATION_SECONDS)

        if not mano_data_len:
            raise OsmInfoNotFound("OSM data not found for the VDU uuid: `{}`".format(vdu_uuid))

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
        # Block for 'synchronous' send; set timeout on X seconds
        try:
            t.get(timeout=KAFKA_TIMEOUT)
        except KafkaError as ke:
            logger.error(ke)
            pass
    producer.close()


if __name__ == '__main__':
    main()
