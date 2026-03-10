"""
Timing profiler for performance diagnostics.
Tracks per-stage latencies without adding significant overhead.
"""

import time
from functools import wraps
import logging

logger = logging.getLogger(__name__)

class TimingProfiler:
    """Track execution timing for different pipeline stages"""
    
    def __init__(self):
        self.stages = {}
        self.request_id = None
    
    def start_stage(self, stage_name: str) -> float:
        """Start timing a stage"""
        start = time.time()
        self.stages[stage_name] = {'start': start}
        return start
    
    def end_stage(self, stage_name: str) -> float:
        """End timing a stage and return elapsed time in ms"""
        if stage_name not in self.stages:
            return 0
        
        end = time.time()
        elapsed_ms = (end - self.stages[stage_name]['start']) * 1000
        self.stages[stage_name]['elapsed_ms'] = elapsed_ms
        
        return elapsed_ms
    
    def get_summary(self) -> dict:
        """Get summary of all stage timings"""
        return {
            stage: data.get('elapsed_ms', 0) 
            for stage, data in self.stages.items()
        }
    
    def log_summary(self):
        """Log timing summary"""
        summary = self.get_summary()
        total_ms = sum(summary.values())
        
        logger.info(f"\n=== TIMING PROFILE (Request: {self.request_id}) ===")
        for stage, elapsed_ms in sorted(summary.items(), key=lambda x: x[1], reverse=True):
            pct = (elapsed_ms / total_ms * 100) if total_ms > 0 else 0
            logger.info(f"  {stage:<30} {elapsed_ms:>8.2f}ms ({pct:>5.1f}%)")
        logger.info(f"  {'TOTAL':<30} {total_ms:>8.2f}ms")
        logger.info("=" * 60)


def time_function(profiler_attr='_profiler'):
    """Decorator to time a function and add to profiler"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get profiler from self or args[0]
            profiler = None
            if args and hasattr(args[0], profiler_attr):
                profiler = getattr(args[0], profiler_attr)
            
            stage_name = func.__name__
            
            if profiler:
                profiler.start_stage(stage_name)
            
            result = func(*args, **kwargs)
            
            if profiler:
                elapsed = profiler.end_stage(stage_name)
                if elapsed > 100:  # Log slow calls (>100ms)
                    logger.debug(f"Slow stage: {stage_name} = {elapsed:.2f}ms")
            
            return result
        return wrapper
    return decorator
