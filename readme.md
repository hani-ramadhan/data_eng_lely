# GitHub Event Monitoring System

A system that allows GitHub Event Analysts to monitor and analyze PullRequest, Watch, and Issue events from GitHub repositories.

## System Context

```mermaid
graph TB
    Analyst[GitHub Event Analyst<br/>[Person]<br/>An analyst who monitors PullRequest,<br/>Watch, and Issue events from GitHub]
    Monitor[GitHub Event Monitoring System<br/>[Software System]<br/>Allows GitHub Event Analyst to view the pull<br/>request average time gap for some repositories<br/>and event count for each GitHub event types]
    API[GitHub Event API<br/>[Software System]<br/>Capture the events happening in GitHub]

    Analyst -->|Monitors GitHub PullRequest,<br/>Watch, and Issue events from using| Monitor
    Monitor -->|Gets PullRequest, Watch, and<br/>Issues Event from| API

    classDef person fill:#8b0000,stroke:#333,stroke-width:2px,color:#fff;
    classDef system fill:#8b0000,stroke:#333,stroke-width:2px,color:#fff;
    classDef external fill:#808080,stroke:#333,stroke-width:2px,color:#fff;

    class Analyst person;
    class Monitor system;
    class API external;
```

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

## Contributing
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License
MIT License - See LICENSE file for details