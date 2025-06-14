# Repolizer - GitHub Repository Health Analyzer

![Repolizer Logo](static/icons/icon-192x192.png)

**Repolizer** is a comprehensive GitHub repository health analysis tool with web UI that evaluates repositories across multiple dimensions to provide actionable insights for maintaining and improving code quality, security, and best practices.

## 🌟 Features

### Core Functionality
- **Multi-dimensional Repository Analysis**: Evaluates repositories across 10+ categories including security, documentation, code quality, performance, testing, and more
- **GitHub Repository Scraping**: Intelligent scraping system with rate limiting, token rotation, and fallback mechanisms
- **Progressive Web App (PWA)**: Installable web application with offline capabilities
- **Real-time Analysis**: Live progress tracking with Server-Sent Events (SSE)
- **Batch Processing**: Analyze multiple repositories efficiently with parallel processing
- **Report Generation**: Comprehensive PDF and HTML reports with detailed findings

### Analysis Categories
- **🛡️ Security**: Vulnerability scanning, dependency checks, secret detection
- **📚 Documentation**: README quality, API docs, code comments, examples
- **⚡ Performance**: Bundle analysis, caching, lazy loading, query optimization
- **🔧 Code Quality**: Linting, complexity metrics, code duplication, refactoring opportunities
- **🧪 Testing**: Test coverage, unit tests, integration tests, E2E testing
- **♿ Accessibility**: WCAG compliance, alt text, keyboard navigation, screen reader compatibility
- **🔄 CI/CD**: Build status, deployment frequency, pipeline configuration
- **🔧 Maintainability**: Code organization, modularity, dependency management
- **⚖️ Licensing**: License compliance, compatibility checks
- **👥 Community**: Contribution guidelines, issue templates, community health

### Web Interface
- **Repository Dashboard**: Visual overview of all analyzed repositories with filtering and sorting
- **Detailed Reports**: In-depth analysis with category breakdowns and recommendations
- **History Tracking**: Track repository health improvements over time
- **Share Reports**: Generate shareable links and social media integration
- **Statistics Dashboard**: Aggregate insights across all analyzed repositories

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Git
- GitHub Personal Access Token (optional but recommended for higher rate limits)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/repolizer.git
   cd repolizer
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure authentication** (optional):
   ```bash
   cp config.json.example config.json
   # Edit config.json with your GitHub token
   ```

### Basic Usage

#### Start the Web Application
```bash
python app.py
```
Access the web interface at `http://localhost:5000`

#### Scrape GitHub Repositories
```bash
python github_scraper.py --min-stars 100 --languages python,javascript --max-pages 5
```

#### Analyze a Single Repository
```bash
python repolizer_single.py --repo microsoft/vscode
```

#### Analyze All Scraped Repositories
```bash
python repolizer_single.py --process-all
```

## 📖 Detailed Usage

### GitHub Scraping

The scraper supports multiple configuration options:

```bash
# Basic scraping with filters
python github_scraper.py \
  --min-stars 50 \
  --languages "python,javascript,typescript" \
  --pushed-after "2023-01-01" \
  --max-pages 10

# Using multiple GitHub tokens for higher rate limits
python github_scraper.py \
  --github-token "token1,token2,token3" \
  --simple-query \
  --max-repos 1000
```

**Configuration Options**:
- `--min-stars`: Minimum star count filter
- `--languages`: Comma-separated list of programming languages
- `--pushed-after`: Filter by last update date
- `--countries`: Filter by contributor location
- `--owners`: Filter by repository owners
- `--max-pages`: Limit API pages to fetch
- `--max-repos`: Maximum repositories to collect

### Repository Analysis

#### Single Repository Analysis
```bash
# Analyze specific repository
python repolizer_single.py --repo facebook/react

# Force re-analysis of previously processed repository
python repolizer_single.py --repo facebook/react --force

# Analyze specific categories only
python repolizer_single.py --repo facebook/react --categories "security,documentation,testing"

# Analyze specific checks only
python repolizer_single.py --repo facebook/react --checks "readme,license,test_coverage"
```

#### Batch Processing
```bash
# Process all repositories (sequential)
python repolizer_single.py --process-all

# Parallel processing with custom worker count
python repolizer_single.py --process-all --parallel --max-workers 8

# Resilient mode (skip problematic repositories)
python repolizer_single.py --process-all --resilient --resilient-timeout 120
```

### Web Interface Features

#### Repository Dashboard
- **View all analyzed repositories** with visual health scores
- **Filter by language, score range, or search terms**
- **Sort by score, stars, last updated, or alphabetically**
- **Pagination** for large repository collections

#### Analysis Interface
- **Real-time progress tracking** during analysis
- **Live log streaming** for transparency
- **Batch analysis** with queue management
- **Result export** in JSON format

#### Report Generation
- **Interactive HTML reports** with category breakdowns
- **PDF export** for offline sharing
- **Historical tracking** to monitor improvements
- **Shareable links** for collaboration

## 🔧 Configuration

### GitHub API Configuration
Create `config.json` from the example:
```json
{
  "github_token": "your-github-token-here",
  "rate_limits": {
    "github_api": 5000,
    "github_search": 30
  },
  "retries": {
    "max_attempts": 3,
    "backoff_factor": 1.5
  }
}
```

### Analysis Configuration
Modify `config.yaml` to customize:
- **Check categories and weights**
- **API endpoints and timeouts**
- **Notification settings**
- **Output formatting**

### Authentication
The web interface supports basic authentication:
- Default credentials: `admin` / `invaders`
- Configure in `app.py` or environment variables
- **Change default credentials in production!**

## 📊 Understanding Reports

### Overall Health Score
- **0-39**: Needs Improvement (Red)
- **40-69**: Good (Yellow) 
- **70-100**: Excellent (Green)

### Category Scores
Each category is evaluated independently:
- **Security**: CVE scanning, dependency analysis, secret detection
- **Documentation**: Completeness, clarity, examples, API docs
- **Code Quality**: Complexity, duplication, style consistency
- **Testing**: Coverage percentage, test types, reliability
- **Performance**: Bundle size, optimization, caching strategies

### Recommendations
Reports include:
- **Critical issues** requiring immediate attention
- **Improvement suggestions** for each category
- **Best practice recommendations**
- **Resource links** for implementation guidance

## 🛡️ Security & Privacy

- **Tokens are never stored** - only used for API requests
- **Local analysis** - repositories are cloned temporarily and cleaned up
- **No data collection** - analysis results stored locally
- **Rate limiting** to respect GitHub API guidelines
- **Secure defaults** for all configurations

## 🌐 PWA Features

Repolizer is a Progressive Web App with:
- **Offline functionality** for previously loaded data
- **Install prompt** for desktop and mobile
- **Service worker caching** for static assets
- **Responsive design** for all screen sizes
- **Fast loading** with critical CSS inlining

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](docs/contributing.md) for details.

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
python -m pytest tests/

# Start development server with auto-reload
flask --app app.py --debug run
```

### Project Structure
```
repolizer/
├── app.py                 # Main Flask application
├── github_scraper.py      # Repository scraping logic
├── repolizer_single.py    # Analysis orchestrator
├── checks/                # Analysis modules by category
│   ├── security/
│   ├── documentation/
│   ├── performance/
│   └── ...
├── templates/             # HTML templates
├── static/               # CSS, JS, and assets
├── utils/                # Utility functions
└── docs/                 # Documentation
```

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 💬 Support

- **Issues**: Report bugs and feature requests on GitHub Issues
- **Documentation**: Check the [docs/](docs/) directory for detailed guides

---

**Made with ❤️ by the Repolizer team**

*Helping developers build better, more secure, and well-documented repositories.*
