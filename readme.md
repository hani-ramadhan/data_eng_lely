# GitHub Event Monitoring System

A system that allows GitHub Event Analysts to monitor and analyze PullRequest, Watch, and Issue events from GitHub repositories.

## System Context
See context_diagram.pdf

## Key Features

1. **Pull Request Analysis**
   - Calculate average time gap between pull requests for repositories
   - Track pull request patterns over time

2. **Event Type Monitoring**
   - Count events by type (PullRequest, Watch, Issue)
   - Filter events by time window

3. **Interactive Dashboard**
   - Visualize event metrics
   - Real-time updates
   - Historical trends

## Quick Start

### Prerequisites
- Docker Desktop
- GitHub Personal Access Token

### Setup Steps
1. Clone the repository:
```bash
git clone <repository-url>
cd <repository-name>
```

2. Configure GitHub token:
```bash
cp .env.example .env
# Add your GitHub token to .env file
```
Update the content with your github token

3. Start the system:
```bash
docker-compose up --build
```

4. Access:
   - Dashboard: http://localhost:8000/dashboard
   - API: http://localhost:8000/docs

## API Endpoints

1. Event Count (By Time Window):
```
GET /metrics/event-count/{offset}
Example: /metrics/event-count/10 (last 10 minutes)
```

2. Pull Request Time Analysis:
```
GET /metrics/pr-time-gap?repository={owner/repo}
Example: /metrics/pr-time-gap?repository=microsoft/vscode
```

## Project Structure
```
.
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── app/
    ├── main.py                     # FastAPI app
    ├── services/
    │   ├── event_service.py        # GitHub API integration
    │   ├── historical_data_service.py  # Data storage
    │   └── monitoring_charts.py    # Visualizations
    ├── models/
    |   └── github_events.py    # model class for verification
    └── templates/
        ├── base.html        # Base HTML for the monitoring dashboard
        ├── dashboard.html  # Dashboard base for the monitoring page
        ├── error.html  # Display for dashboard server error 
        └── monitoring.html   # Main monitoring cards for visualization
```

## Implementation Details

### Data Collection
- Real-time monitoring of GitHub Events API
- Focus on three event types:
  - PullRequest Events
  - Watch Events
  - Issue Events
- 24-hour data retention

### Storage
- Redis for event data
- Separate storage for historical metrics
- Efficient data querying and aggregation

## Development

### Local Setup
```bash
# Start services
docker-compose up --build

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Configuration Files
- `.env`: Environment variables (GitHub token)
- `docker-compose.yml`: Service configuration
- `requirements.txt`: Python dependencies

## Future Improvements
1. Additional event type support
2. Enhanced visualization options
3. Extended historical data analysis
4. Export capabilities
5. Advanced repository metrics
