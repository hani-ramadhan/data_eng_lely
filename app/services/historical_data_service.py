from datetime import datetime, timedelta
from tempfile import template
from ..services.event_service import EventService
import pygal
from pygal.style import Style
import json
import redis
import os

# Custom style for consistent look
CUSTOM_STYLE = Style(
    background='transparent',
    plot_background='transparent',
    foreground='#333',
    foreground_strong='#333',
    colors=('#2ecc71', '#3498db', '#e74c3c'),  # Green, Blue, Red
    font_family='Arial'
)

class HistoricalDataService:
    """Service to handle historical data storage and retrieval"""

    # Separate Redis client for historical data
    redis_client = redis.Redis(
        host=os.getenv('HISTORY_REDIS_HOST', 'localhost'),
        port=int(os.getenv('HISTORY_REDIS_PORT', 6380)),  # Note different default port
        decode_responses=True
    )
    
    @classmethod
    async def store_metrics_snapshot(cls, event_service: EventService):
        """Store current metrics in Redis with timestamp"""
        try:
            current_time = datetime.now()
            
            # Get current metrics from event service
            event_data = await event_service.count_events_by_type(10)

            # Prepare data for storage
            snapshot_serialized = {
                'timestamp': str(current_time.timestamp()),
                'counts': json.dumps(event_data['counts']),
                'total': str(sum(event_data['counts'].values()))
            }
            
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
    async def get_historical_data(cls, event_service: EventService) -> list:
        """Retrieve historical data for the specified time period"""
        try:
            # Use historical service's own Redis client
            snapshot_keys = cls.redis_client.zrangebyscore(
                'metrics:snapshots',
                '-inf',
                '+inf'
            )
            
            historical_data = []
            for key in snapshot_keys:
                snapshot = cls.redis_client.hgetall(key)
                if snapshot:
                    snapshot['timestamp'] = float(snapshot['timestamp'])
                    snapshot['counts'] = json.loads(snapshot['counts'])
                    historical_data.append(snapshot)
            
            print(historical_data)
            return sorted(historical_data, key=lambda x: x['timestamp'])
            
        except Exception as e:
            print(f"Error retrieving historical data: {e}")
            return []

class EnhancedDashboardChartGenerator:
    @staticmethod
    def create_event_distribution_history(historical_data: list) -> str:
        """Generate time series chart for event distribution"""
        chart = pygal.Line(
            style=CUSTOM_STYLE,
            height=300,
            show_legend=True,
            x_label_rotation=45,
            compress=True
        )
        chart.title = 'Event Distribution Over Time'
        
        # Prepare data series for each event type
        event_series = {}
        timestamps = []
        
        for snapshot in historical_data:
            timestamp = datetime.fromtimestamp(snapshot['timestamp'])
            timestamps.append(timestamp.strftime('%H:%M:%S'))
            
            for event_type, count in snapshot['counts'].items():
                if event_type not in event_series:
                    event_series[event_type] = []
                event_series[event_type].append(count)
        
        # Add data series to chart
        for event_type, counts in event_series.items():
            label = event_type.replace('Event', '')
            chart.add(label, counts)
        
        chart.x_labels = timestamps
        return chart.render()

    @staticmethod
    def create_total_events_history(historical_data: list) -> str:
        """Generate time series chart for total events"""
        chart = pygal.Line(
            style=CUSTOM_STYLE,
            height=300,
            show_legend=False,
            x_label_rotation=45,
            compress=True
        )
        chart.title = 'Total Events Over Time'
        
        timestamps = []
        totals = []
        
        for snapshot in historical_data:
            timestamp = datetime.fromtimestamp(snapshot['timestamp'])
            timestamps.append(timestamp.strftime('%H:%M:%S'))
            totals.append(int(snapshot['total']))
        
        chart.add('Total Events', totals)
        chart.x_labels = timestamps
        return chart.render()
