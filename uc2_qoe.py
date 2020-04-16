import json
import logging.config
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError
from settings import LOGGING

logging.config.dictConfig(LOGGING)
logger = logging.getLogger("translator")

# VARIABLES
KAFKA_SERVER = "217.172.11.173:9092"
KAFKA_CLIENT_ID = "offline-training-cno-uc2-qoe"
KAFKA_API_VERSION = (1, 1, 0)
KAFKA_GROUP_ID = "TEST_UC2_QOE_CG"
KAFKA_TOPIC = "app.uc2.qoe"


def main():
    # See more: https://kafka-python.readthedocs.io/en/master/apidoc/KafkaConsumer.html
    consumer = KafkaConsumer(bootstrap_servers=KAFKA_SERVER, client_id=KAFKA_CLIENT_ID,
                             enable_auto_commit=True,
                             api_version=KAFKA_API_VERSION, group_id=KAFKA_GROUP_ID)
    consumer.subscribe(pattern=KAFKA_TOPIC)

    for msg in consumer:
        topic = msg.topic
        try:
            print(msg.value)
            # the below raises json.decoder.JSONDecodeError when is not JSON
            message = json.loads(msg.value.decode('utf-8', 'ignore'))
            print(message)

        # do your operation

        except json.decoder.JSONDecodeError as je:
            logger.error("JSONDecodeError: {}".format(je))
        except Exception as ex:
            logger.exception(ex)


if __name__ == '__main__':
    main()
