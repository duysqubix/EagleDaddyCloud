import redis
import json
from EagleDaddyCloud.settings import CONFIG


def send_proxy_data(connection_pool: redis.ConnectionPool, data: dict):
    with redis.Redis(connection_pool=connection_pool) as proxy:
        proxy.publish(CONFIG.proxy.channel, json.dumps(data))
