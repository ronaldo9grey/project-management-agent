# Project Management Agent

An intelligent project management assistant powered by AI, designed to streamline daily reporting, project tracking, and risk management.

## Features

### 📝 Smart Daily Report
- **Natural Language Parsing**: AI-powered parsing of daily work reports using natural language input
- **STAR Principle Content Polishing**: Automatically refines report content following STAR (Specific, Time-bound, Achievable, Relevant) principles
- **Shared Time Slot Detection**: Intelligently identifies multiple tasks sharing the same time period and distributes work hours accordingly
- **Project Matching**: Fuzzy matching algorithm to link work items with existing projects

### 📊 Project Dashboard
- **Real-time Progress Tracking**: Visual dashboard showing project status, progress, and key metrics
- **Risk Radar**: Five-dimensional risk assessment (progress, material cost, labor cost, outsourcing cost, indirect cost)
- **Task Management**: Hierarchical task structure with automatic status calculation

### 🤖 AI Assistant
- **Intelligent Q&A**: Ask questions about project details, tasks, and progress
- **Weekly Report Generation**: AI-generated weekly summaries based on daily reports
- **Smart Task Matching**: Automatically links daily work items to project tasks

### 🔔 Notification System
- **Push Notifications**: WeChat push notifications via PushPlus
- **Risk Alerts**: Automatic alerts for high-risk projects
- **Daily Reminders**: Reminders for unsubmitted daily reports

## Tech Stack

### Backend
- **Framework**: FastAPI
- **Database**: PostgreSQL
- **AI**: DeepSeek API for intelligent parsing
- **ORM**: SQLAlchemy

### Frontend
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State Management**: Zustand

### Deployment
- **Web Server**: Nginx
- **Application Server**: Uvicorn
- **Process Manager**: systemd

## Installation

### Prerequisites
- Python 3.9+
- Node.js 18+
- PostgreSQL 14+

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your configuration

# Run server
uvicorn app.main:app --host 0.0.0.0 --port 3000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Production build
npm run build
```

## Configuration

### Environment Variables

Create a `.env` file in the backend directory:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# DeepSeek AI
DEEPSEEK_API_KEY=your_api_key
DEEPSEEK_API_URL=https://api.deepseek.com/v1

# Push Notifications (Optional)
PUSHPLUS_TOKEN=your_token
PUSHPLUS_TOPIC=your_topic

# HuggingFace Mirror (China)
HF_ENDPOINT=https://hf-mirror.com
```

## API Documentation

Access the interactive API documentation at `/docs` when running the server.

### Key Endpoints

- `POST /api/agent/daily/smart-parse` - Smart parse daily report text
- `POST /api/agent/daily/create` - Submit daily report
- `GET /api/agent/projects` - List all projects
- `GET /api/agent/projects/{id}` - Get project details
- `GET /api/agent/dashboard/overview` - Dashboard statistics
- `POST /api/agent/weekly-reports/generate` - Generate weekly report

## Scheduled Tasks

The system runs the following scheduled tasks:

| Time | Task | Description |
|------|------|-------------|
| 08:00 | Morning Alerts | Push high-risk project alerts to WeChat |
| 16:00 | Daily Reminder | Remind users to submit daily reports |

## Project Structure

```
project-agent/
├── backend/
│   ├── app/
│   │   ├── main.py           # Main FastAPI application
│   │   ├── push_service.py   # Push notification service
│   │   ├── task_auto.py      # Task matching logic
│   │   └── work_time_config.py # Work time calculations
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── pages/            # React pages
│   │   ├── components/       # Reusable components
│   │   ├── api.ts            # API client
│   │   └── store.ts          # State management
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- DeepSeek AI for intelligent text parsing
- PushPlus for WeChat notification integration
- The open-source community for the amazing tools and libraries
