import os
import pytest
import tempfile
import shutil
import logging
from unittest.mock import patch, MagicMock
from pathlib import Path
from checks.ci_cd.monitoring_integration import check_monitoring_integration, run_check
import logging
from opentelemetry import trace
import logging
from opentelemetry import trace

# Setup logging for tests
logging.basicConfig(level=logging.DEBUG)

class TestMonitoringIntegration:
    @pytest.fixture
    def mock_repo(self):
        """Create a temporary directory to simulate a repository"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    def test_empty_repository(self, mock_repo):
        """Test with an empty repository - should have no monitoring"""
        result = check_monitoring_integration(mock_repo)
        
        assert result["has_monitoring"] == False
        assert result["monitoring_tools"] == []
        assert result["has_logging"] == False
        assert result["has_metrics"] == False
        assert result["has_tracing"] == False
        assert result["has_alerting"] == False
        assert result["has_dashboards"] == False
        assert result["monitoring_score"] == 0
    
    def test_prometheus_config(self, mock_repo):
        """Test with a repository containing Prometheus configuration"""
        # Create prometheus.yml file
        prometheus_file = os.path.join(mock_repo, "prometheus.yml")
        with open(prometheus_file, "w") as f:
            f.write("scrape_configs:\n  - job_name: 'app'\n    static_configs:\n      - targets: ['localhost:8080']")
        
        result = check_monitoring_integration(mock_repo)
        
        assert result["has_monitoring"] == True
        assert "prometheus" in result["monitoring_tools"]
        assert result["monitoring_score"] >= 20
    
    def test_monitoring_directory(self, mock_repo):
        """Test with a repository containing a monitoring directory"""
        # Create monitoring directory and some files
        monitoring_dir = os.path.join(mock_repo, "monitoring")
        os.makedirs(monitoring_dir)
        
        with open(os.path.join(monitoring_dir, "grafana.json"), "w") as f:
            f.write('{"dashboard": {"title": "App Metrics"}}')
        
        result = check_monitoring_integration(mock_repo)
        
        assert result["has_monitoring"] == True
        assert "grafana" in result["monitoring_tools"]
        assert result["has_dashboards"] == True
        assert result["monitoring_score"] >= 20
    
    def test_logging_in_source_file(self, mock_repo):
        """Test with a repository containing source files with logging"""
        # Create Python file with logging
        os.makedirs(os.path.join(mock_repo, "src"))
        with open(os.path.join(mock_repo, "src", "app.py"), "w") as f:
            f.write("""
logger = logging.getLogger(__name__)

def main():
    logger.info("Application started")
    logger.error("An error occurred")
""")
        
        result = check_monitoring_integration(mock_repo)
        
        assert result["has_logging"] == True
        assert result["monitoring_score"] >= 15
    
    def test_metrics_and_tracing(self, mock_repo):
        """Test with a repository containing metrics and tracing code"""
        # Create files with metrics and tracing
        os.makedirs(os.path.join(mock_repo, "src"))
        
        with open(os.path.join(mock_repo, "src", "metrics.js"), "w") as f:
            f.write("""
const prometheus = require('prom-client');
const counter = new prometheus.Counter({
    name: 'http_requests_total',
    help: 'Total HTTP requests'
});
""")
        
        with open(os.path.join(mock_repo, "src", "tracing.py"), "w") as f:
            f.write("""
tracer = trace.get_tracer(__name__)

def process_request():
    with tracer.start_as_current_span("process_request"):
        # do work
        pass
""")
        
        result = check_monitoring_integration(mock_repo)
        
        assert result["has_metrics"] == True
        assert result["has_tracing"] == True
        assert "prometheus" in result["monitoring_tools"]
        assert "opentelemetry" in result["monitoring_tools"]
        assert result["monitoring_score"] >= 35
    
    def test_alerting_config(self, mock_repo):
        """Test with a repository containing alerting configuration"""
        # Create alerting configuration
        os.makedirs(os.path.join(mock_repo, "config"))
        
        with open(os.path.join(mock_repo, "config", "alerts.yml"), "w") as f:
            f.write("""
alerts:
  - name: HighErrorRate
    condition: error_rate > 0.01
    threshold: 0.01
    notification:
      - email: alerts@example.com
      - pagerduty: ABC123
""")
        
        result = check_monitoring_integration(mock_repo)
        
        assert result["has_alerting"] == True
        assert result["monitoring_score"] >= 15
    
    def test_docker_compose_with_monitoring(self, mock_repo):
        """Test with a repository containing docker-compose with monitoring services"""
        # Create docker-compose.yml with monitoring services
        with open(os.path.join(mock_repo, "docker-compose.yml"), "w") as f:
            f.write("""
version: '3'
services:
  app:
    build: .
    ports:
      - "8080:8080"
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
""")
        
        result = check_monitoring_integration(mock_repo)
        
        assert result["has_monitoring"] == True
        assert set(["prometheus", "grafana"]).issubset(set(result["monitoring_tools"]))
        assert result["monitoring_score"] >= 20
    
    def test_complete_monitoring_setup(self, mock_repo):
        """Test with a repository having complete monitoring setup"""
        # Create directory structure
        os.makedirs(os.path.join(mock_repo, "monitoring/dashboards"), exist_ok=True)
        os.makedirs(os.path.join(mock_repo, "src"), exist_ok=True)
        
        # Add monitoring config files
        with open(os.path.join(mock_repo, "monitoring", "prometheus.yml"), "w") as f:
            f.write("scrape_configs:\n  - job_name: 'app'")
        
        with open(os.path.join(mock_repo, "monitoring/dashboards", "app.json"), "w") as f:
            f.write('{"dashboard": {"panels": [{"title": "Error Rate"}]}}')
        
        with open(os.path.join(mock_repo, "monitoring", "alerts.yml"), "w") as f:
            f.write("groups:\n  - name: alerts\n    rules:\n      - alert: HighErrorRate")
        
        # Add source files with monitoring code
        with open(os.path.join(mock_repo, "src", "app.py"), "w") as f:
            f.write("""

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

def process():
    logger.info("Processing")
    with tracer.start_as_current_span("process"):
        metrics.counter("requests").inc()
""")
        
        result = check_monitoring_integration(mock_repo)
        
        # Check that all monitoring features are detected
        assert result["has_monitoring"] == True
        assert result["has_logging"] == True
        assert result["has_metrics"] == True
        assert result["has_tracing"] == True
        assert result["has_alerting"] == True
        assert result["has_dashboards"] == True
        
        # Score should be close to 100
        assert result["monitoring_score"] >= 80
    
    def test_api_data_fallback(self):
        """Test using API data when no repo path is provided"""
        api_data = {
            "monitoring": {
                "has_monitoring": True,
                "tools": ["datadog", "prometheus"],
                "has_logging": True,
                "has_metrics": True,
                "has_tracing": False,
                "has_alerting": True,
                "has_dashboards": True
            }
        }
        
        result = check_monitoring_integration(repo_data=api_data)
        
        assert result["has_monitoring"] == True
        assert set(["datadog", "prometheus"]).issubset(set(result["monitoring_tools"]))
        assert result["has_logging"] == True
        assert result["has_metrics"] == True
        assert result["has_tracing"] == False
        assert result["has_alerting"] == True
        assert result["has_dashboards"] == True
        assert result["monitoring_score"] >= 50
    
    def test_run_check_success(self, mock_repo):
        """Test the run_check function with successful execution"""
        # Setup a minimal monitoring config
        with open(os.path.join(mock_repo, "prometheus.yml"), "w") as f:
            f.write("scrape_configs:\n  - job_name: 'app'")
        
        repository = {"local_path": mock_repo}
        result = run_check(repository)
        
        assert result["status"] == "completed"
        assert result["score"] > 0
        assert result["errors"] is None
        assert "result" in result
    
    def test_run_check_error(self):
        """Test the run_check function with an error"""
        with patch("checks.ci_cd.monitoring_integration.check_monitoring_integration", 
                  side_effect=Exception("Test error")):
            repository = {"local_path": "/non/existent/path"}
            result = run_check(repository)
            
            assert result["status"] == "failed"
            assert result["score"] == 0
            assert "Test error" in result["errors"]
            assert result["result"] == {}