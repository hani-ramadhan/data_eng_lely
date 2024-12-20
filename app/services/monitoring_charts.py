from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import pygal
from pygal.style import Style
from datetime import datetime, timedelta
from typing import Dict, List
import json

# Custom style for consistent look
CUSTOM_STYLE = Style(
    background='transparent',
    plot_background='transparent',
    foreground='#333',
    foreground_strong='#333',
    colors=('#2ecc71', '#3498db', '#e74c3c'),  # Green, Blue, Red
    font_family='Arial'
)

class GithubMonitoringCharts:
    @staticmethod
    def create_total_events_chart(historical_data: List[Dict]) -> str:
        """Create line chart for total events over time"""
        chart = pygal.Line(
            style=CUSTOM_STYLE,
            height=300,
            show_legend=True,
            x_label_rotation=45,
            dots_size=2,
            compress=True
        )
        chart.title = 'Total Events Over Time'
        
        # Prepare data series
        timestamps = []
        watch_events = []
        issue_events = []
        pr_events = []
        
        for snapshot in historical_data:
            timestamps.append(datetime.fromtimestamp(snapshot['timestamp']).strftime('%H:%M:%S'))
            counts = snapshot['counts']
            watch_events.append(counts.get('WatchEvent', 0))
            issue_events.append(counts.get('IssuesEvent', 0))
            pr_events.append(counts.get('PullRequestEvent', 0))
        
        # Add data series
        chart.x_labels = timestamps
        chart.add('Watch Events', watch_events)
        chart.add('Issue Events', issue_events)
        chart.add('PR Events', pr_events)
        
        return chart.render()

    @staticmethod
    def create_distribution_chart(historical_data: List[Dict]) -> str:
        """Create stacked line chart for event distribution"""
        chart = pygal.StackedLine(
            style=CUSTOM_STYLE,
            height=300,
            x_label_rotation=45,
            fill=True,
            dots_size=2,
            compress=True
        )
        chart.title = 'Event Distribution Over Time'
        
        # Calculate percentages
        timestamps = []
        watch_pct = []
        issue_pct = []
        pr_pct = []
        
        for snapshot in historical_data:
            timestamps.append(datetime.fromtimestamp(snapshot['timestamp']).strftime('%H:%M:%S'))
            counts = snapshot['counts']
            total = sum(counts.values())
            
            if total > 0:
                watch_pct.append(counts.get('WatchEvent', 0) / total * 100)
                issue_pct.append(counts.get('IssuesEvent', 0) / total * 100)
                pr_pct.append(counts.get('PullRequestEvent', 0) / total * 100)
            else:
                watch_pct.append(0)
                issue_pct.append(0)
                pr_pct.append(0)
        
        chart.x_labels = timestamps
        chart.add('Watch Events %', watch_pct)
        chart.add('Issue Events %', issue_pct)
        chart.add('PR Events %', pr_pct)
        
        return chart.render()

    @staticmethod
    def create_pr_time_chart(historical_pr_data: List[Dict], repository: str) -> str:
        """Create line chart for PR average time"""
        chart = pygal.Line(
            style=CUSTOM_STYLE,
            height=300,
            show_legend=False,
            x_label_rotation=45,
            dots_size=2,
            compress=True
        )
        chart.title = f'PR Average Time for {repository}'
        
        timestamps = []
        avg_times = []
        
        for data_point in historical_pr_data:
            timestamps.append(datetime.fromtimestamp(data_point['timestamp']).strftime('%H:%M:%S'))
            avg_times.append(data_point.get('average_time_between_prs', 0))
        
        chart.x_labels = timestamps
        chart.add('Average Time (minutes)', avg_times)
        
        return chart.render()
