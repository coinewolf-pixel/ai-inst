from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
import json
import os

KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

producer: AIOKafkaProducer = None

async def start_kafka():
    global producer
    producer = AIOKafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    await producer.start()

async def stop_kafka():
    if producer:
        await producer.stop()

async def publish(topic: str, message: dict):
    if producer:
        await producer.send(topic, message)
