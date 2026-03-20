import time
import logging
from contextlib import contextmanager
from typing import Optional

PRICING_REGISTRY={
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "text-embedding-3-small": {"input": 0.02, "output": 0.0},
    "default": {"input": 0.0, "output": 0.0}
}

class TelemetryService:
    def __init__(self, request_id: str, user_id: Optional[str] = None):
        self.request_id = request_id
        self.logger = logging.getLogger("json_logger")
        self.user_id = user_id

        self.metrics = {
            # High Level Stages
            "routing_ms": 0.0,
            "retrieval_ms": 0.0,
            "llm_ms": 0.0,
            # Sub-stages (Logged but can be aggregated)
            "embedding_ms": 0.0,
            "vector_search_ms": 0.0,
            "db_fetch_ms": 0.0,
            # Costs & Metadata
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
            "models_used": set(),
            "error_type": None
        }

        self.start_time = time.time()

    @contextmanager
    def measure(self, stage: str):
        """
        measure latency of each stage & log start & end event
        """

        t0 = time.time()

        self.logger.info({
            "event": f'{stage}_start',
            "request_id": self.request_id 
        })

        try:
            yield
        finally:
            duration = (time.time()-t0)*1000
            key = f'{stage}_ms'
            self.metrics[key] = self.metrics.get(key, 0.0) + round(duration,2)

            self.logger.info({
                "event": f'{stage}_complete',
                "request_id": self.request_id, 
                "duration_ms": duration

            })

    def _calculate_cost(self, model: str, p_tokens: int, c_tokens: int)-> float:
        pricing= PRICING_REGISTRY.get(model, PRICING_REGISTRY["default"])
        input_cost = (p_tokens/1_000_000)*pricing["input"]
        output_cost = (c_tokens/1_000_000)*pricing["output"]

        return input_cost+output_cost
    
    def track_llm(self, usage_object, model: str):
        if not usage_object:
            return
        
        p= usage_object.prompt_tokens
        c = usage_object.completion_tokens

        self.metrics["prompt_tokens"] += p
        self.metrics["completion_tokens"] += c
        self.metrics["models_used"].add(model)
        self.metrics["cost_usd"] += self._calculate_cost(model, p, c)

    def track_embedding(self, token_count: int, model: str = "text-embedding-3-small"):
        self.metrics["prompt_tokens"] += token_count
        self.metrics["models_used"].add(model)
        self.metrics["cost_usd"] += self._calculate_cost(model, token_count, 0)
    
    def set_error(self, error_type: str):
        self.metrics["error_type"]= error_type
    
    def get_summary(self):
        sorted_models = sorted(list(self.metrics["models_used"]))
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "total_latency_ms": round((time.time() - self.start_time) * 1000, 2),
            "model_str": ", ".join(sorted_models),
            **self.metrics
        }



    

    

        





    
