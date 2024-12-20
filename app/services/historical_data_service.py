from datetime import datetime, timedelta
import json
import redis
import os

class HistoricalDataService:
    # Separate Redis client for historical data

    # # for local
    # redis_client = redis.Redis(
    #     host=os.getenv('HISTORICAL_REDIS_HOST', 'localhost'),
    #     port=int(os.getenv('HISTORICAL_REDIS_PORT', 6380)),
    #     decode_responses=True
    # )

    

    # for docker
    redis_client = redis.Redis(
        host=os.getenv('HISTORICAL_REDIS_HOST', 'historical-redis'),  # Changed from localhost to historical-redis
        port=6379,  
        decode_responses=True
    )

    STORE_SNAPSHOT_TIME_WINDOW = 10 # in minutes

    @classmethod
    async def store_metrics_snapshot(cls, event_service_method):
        """
        Store current metrics in Redis with timestamp
        
        :param event_service_method: Method to count events (to break circular dependency)
        """
        try:
            current_time = datetime.now()
            
            # Get current metrics for a fixed t-minute window
            event_data = await event_service_method(cls.STORE_SNAPSHOT_TIME_WINDOW)

            # Prepare data for storage
            snapshot_serialized = {
                'timestamp': str(current_time.timestamp()),
                'counts': json.dumps(event_data['counts']),
                'total': str(sum(event_data['counts'].values()))
            }
            
            print(snapshot_serialized)
            # Use historical service's own Redis client
            pipe = cls.redis_client.pipeline()
            
            # Store snapshot
            key = f"metrics:snapshot:{current_time.timestamp()}"
            pipe.hmset(key, snapshot_serialized)
            pipe.expire(key, 900)  # 15 minutes
            
            # Maintain list of snapshot keys
            pipe.zadd('metrics:snapshots', {key: current_time.timestamp()})
            pipe.zremrangebyscore(
                'metrics:snapshots',
                '-inf',
                (current_time - timedelta(minutes=15)).timestamp()
            )
            pipe.execute()
            
        except Exception as e:
            print(f"Error storing metrics snapshot: {e}")

    @classmethod
    async def get_historical_data(cls):
        """
        Retrieve historical data 
        
        :param event_service_method: Optional method, kept for compatibility
        """
        try:
            # Retrieve snapshot keys
            snapshot_keys = cls.redis_client.zrange(
                'metrics:snapshots',
                -10,  # Last 10 snapshots
                -1
            )
            
            historical_data = []
            for key in snapshot_keys:
                snapshot = cls.redis_client.hgetall(key)
                if snapshot:
                    snapshot['timestamp'] = float(snapshot['timestamp'])
                    snapshot['counts'] = json.loads(snapshot['counts'])
                    historical_data.append(snapshot)
            
            return sorted(historical_data, key=lambda x: x['timestamp'])
            
        except Exception as e:
            print(f"Error retrieving historical data: {e}")
            return []