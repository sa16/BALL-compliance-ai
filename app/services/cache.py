import os
import hashlib
import logging
import json
import uuid
import random
from typing import Optional
import redis


logger = logging.getLogger("json_logger")
# REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

class CacheService:
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://ball_redis:6379/0")
        self.client = redis.from_url(redis_url, 
                                     decode_responses=True,
                                     socket_timeout=2,
                                    socket_connect_timeout=2,
                                    retry_on_timeout=True,
                                    health_check_interval=30)

        #TTL for intent routing, LLM response & embedding layers
        self.NEGATIVE_TTL = 300 #5 mins
        self.INTENT_TTL = 604800#7 days
        self.RESPONSE_TTL = 86400#24hours
        self.EMBED_TTL = 2592000#30 days
        self.EMBED_VERSION = "v1"

    def _hash(self, text: str)->str:
        """redis is going to return a long hashcode that might be difficult to manage, so this func renders a shorter one"""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
    
    def _normalize(self, text: str)->str:
        return " ".join(text.lower().strip().split())
    
    def _get_ttl_with_jitter(self, base_ttl: int)->int:
        #to avoid all cache items expiring at the same time
        return base_ttl + random.randint(-300, 300)

    #STAMPEDE PROTECTION LAYER 

    def acquire_lock(self, lock_key: str, expire: int=45)->Optional[str]:
        """in a cache expiry scenario - uses setnx - lock to ensure large amounts of simultaneous calls to LLM (which would be expensive) 
        - once cache expires, the 1st user is locked & goes through full route (intent routing, embedding, retrieval->llm reponse).
        -cache is now populated again, lock is released & then the subsequent users hit the cache layers
        """
        try:
            token = str(uuid.uuid4())
            acquired = self.client.set(lock_key, token,nx=True, ex=expire)
            return token if acquired else None
        except Exception:
            return str(uuid.uuid4()) # no lock if redis is down
        
    def release_lock(self, lock_key: str, token: str):
        try: 
            if self.client.get(lock_key)==token: self.client.delete(lock_key)
        except Exception:
            pass

    #RESPONSE LAYER
    def get_response(self, query: str, policy_id: Optional[str])->Optional[str]:
        """stages the reponse for redis"""
        normalized = self._normalize(query)
        key_suffix = self._hash(f"{normalized}_{policy_id}")
        key = f"response:policy_{policy_id}:{key_suffix}" if policy_id else f"response:global:{key_suffix}"

        try:
            data = self.client.get(key)
            if data:
                logger.info({"event": "cache_hit", "layer": "response"})
                return json.loads(data)
            logger.info({"event": "cache_miss", "layer": "response"})
        except Exception as e:
            logger.error({"event": "redis_read_error", "layer": "response", "error": type(e).__name__})
            return None
        

    def set_response(self, query: str, policy_id: Optional[str], response_dict: dict, is_negative: bool = False):
        """saves response to redis"""
        payload = json.dumps(response_dict)

        if len(payload) > 100_000: 
            logger.warning({"event": "cache_skip_oversized", "layer": "response", "size": len(payload)})
            return
        normalized = self._normalize(query)
        key_suffix = self._hash(f"{normalized}_{policy_id}")
        key = f"response:policy_{policy_id}:{key_suffix}" if policy_id else f"response:global:{key_suffix}"

        set_key  = f"keys:{policy_id}" if policy_id else "keys:global"

        base_ttl = self.NEGATIVE_TTL if is_negative else self.RESPONSE_TTL
        ttl = self._get_ttl_with_jitter(base_ttl)

        try:
            self.client.setex(key, ttl, payload)
            self.client.sadd(set_key, key)
            logger.info({"event": "cache_write", "layer": "response", "key": key, "is_negative": is_negative})
        except Exception as e:
            logger.error({"event": "redis_write_error", "layer": "response", "error": type(e).__name__})

    def get_intent(self, query: str)->Optional[str]:
        key = f"intent:{self._hash(self._normalize(query))}"
        try:
            data = self.client.get(key)
            if data: 
                logger.info({"event": "cache_hit", "layer": "intent"})
                return data
            return None

        except Exception: return None
    
    
    def set_intent(self, query: str, intent: str):
        key = f"intent:{self._hash(self._normalize(query))}"
        ttl = self._get_ttl_with_jitter(self.INTENT_TTL)
        try:
            self.client.setex(key, ttl, intent)
        except Exception:
            pass
    
    def get_embedding(self, text: str) -> Optional[list]:
        key = f"embed:{self.EMBED_VERSION}:{self._hash(self._normalize(text))}"
        try:
            data = self.client.get(key)
            if data:
                logger.info({"event": "cache_hit", "layer": "embedding"})
                return json.loads(data)
            return None
        except Exception:
            return None

    def set_embedding(self, text: str, embedding: list):
        payload = json.dumps(embedding)
        if len(payload) > 100_000: return
        key = f"embed:{self.EMBED_VERSION}:{self._hash(self._normalize(text))}"
        ttl = self._get_ttl_with_jitter(self.EMBED_TTL)
        try:
            self.client.setex(key, ttl, payload)
        except Exception:
            pass
    
    def invalidate_policy(self, policy_id: str):
        """if a policy is changed or drop, we have to delete corresponding record in cache layer"""
        set_key = f"keys:policy_{policy_id}" if policy_id else "keys:global"
        try:
            count = 0
            for key in self.client.sscan_iter(set_key):
                self.client.delete(key)
                count +=1
            self.client.delete(set_key)
            logger.info({"event": "cache_invalidated", "policy_id": policy_id, "keys_removed": count})
        except Exception as e:
            logger.error({"event": "redis_invalidate_error", "error": type(e).__name__})


cache_service = CacheService()







    

        


