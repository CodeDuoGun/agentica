import os
from functools import wraps

import redis
from tcm_agent.config import config


def singleton(cls):
    @wraps(cls)
    def wrapper(*args, **kwargs):
        if cls.instance is None:
            cls.instance = cls(*args, **kwargs)
        return cls.instance

    cls.instance = None
    return wrapper


@singleton
class RedisSingleton:
    def __init__(self):
        self.client = redis.Redis(host=config.REDIS_HOST, port=config.REDIS_PORT, db=config.REDIS_DB, password=config.REDIS_AUTH, decode_responses=True)

    def set(self, key, value):
        return self.client.set(key, value)

    def set_expire(self, key, value, expire_time=86400):
        self.set(key, value)
        return self.client.expire(key, expire_time)

    def get(self, key):
        return self.client.get(key)

    def exist(self, key):
        return self.client.exists(key)

    def delete(self, *keys):
        return self.client.delete(*keys)

    def expire(self, key, expire_time):
        return self.client.expire(key, expire_time)

    def hexists(self, table, key):
        return self.client.hexists(table, key)

    def hget(self, table, key):
        return self.client.hget(table, key)

    def hgetall(self, table):
        return self.client.hgetall(table)

    def hset(self, table, key, value):
        return self.client.hset(table, key, value)

    def hdel(self, table, *keys):
        return self.client.hdel(table, *keys)

    def hkeys(self, table):
        return self.client.hkeys(table)

    def sadd(self, key, *values):
        return self.client.sadd(key, *values)

    def smembers(self, key):
        return self.client.smembers(key)

    def srem(self, key, *values):
        return self.client.srem(key, *values)

    def scard(self, key):
        return self.client.scard(key)

    def scan_iter(self, key):
        return self.client.scan_iter(key)

    def spop(self, key):
        return self.client.spop(key)

    def sismember(self, key, value):
        return self.client.sismember(key, value)

    def lpush(self, key, value):
        return self.client.lpush(key, value)

    def rpush(self, key, value):
        return self.client.rpush(key, value)

    def rpop(self, key):
        return self.client.rpop(key)

    def llen(self, key):
        return self.client.llen(key)

    def incr(self, key):
        return self.client.incr(key)

    def lrange(self, key, start, end):
        return self.client.lrange(key, start, end)

    def delete_keys_by_pattern(self, pattern="history_*_videoagent"):
        cursor = 0
        total_deleted = 0
        while True:
            cursor, keys = self.client.scan(cursor=cursor, match=pattern, count=1000)
            if keys:
                self.client.delete(*keys)
                total_deleted += len(keys)
                print(f"Deleted {len(keys)} keys, example: {keys[:3]}{'...' if len(keys) > 3 else ''}")
            if cursor == 0:
                break

        print(f"Total deleted keys: {total_deleted}")


redis_tool = RedisSingleton()
