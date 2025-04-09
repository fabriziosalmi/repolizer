import pandas as pd
import json
import os
import glob
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np
from flask import Flask, render_template, Response
import plotly.io as pio
import io

app = Flask(__name__, template_folder='templates')

def load_all_reports():
    """Load all saved reports from the data directory."""
    reports = []
    # Updated glob pattern to match report_*.json files
    report_files = glob.glob('reports/report_*.json')
    
    for file_path in report_files:
        try:
            with open(file_path, 'r') as file:
                report_data = json.load(file)
                reports.append(report_data)
        except Exception as e:
            print(f"Error loading report {file_path}: {e}")
    
    return reports

def calculate_average_scores(reports):
    """Calculate average scores across all reports."""
    if not reports:
        return 0, {}

    # Initialize counters
    total_final_score = 0
    final_score_count = 0
    category_scores = {}
    category_weights = {}

    # Process each report
    for report in reports:
        # Add final score
        if 'final_score' in report and isinstance(report['final_score'], (int, float)):
            total_final_score += report['final_score']
            final_score_count += 1

        # Process category scores
        if 'dettagli' in report:
            for category, metrics in report['dettagli'].items():
                if category not in category_scores:
                    category_scores[category] = 0
                    category_weights[category] = 0

                for metric_name, metric_data in metrics.items():
                    if metric_data.get('conta_punteggio', False) and not metric_data.get('score_is_na', True):
                        score = metric_data.get('punteggio', 0)
                        weight = metric_data.get('peso', 1)
                        category_scores[category] += score * weight
                        category_weights[category] += weight

    # Calculate weighted averages
    avg_category_scores = {
        category: (category_scores[category] / category_weights[category])
        if category_weights[category] > 0 else 0
        for category in category_scores
    }

    avg_final_score = total_final_score / final_score_count if final_score_count > 0 else 0

    return avg_final_score, avg_category_scores

def calculate_statistics():
    """Calculate all statistics for the page."""
    reports = load_all_reports()
    
    if not reports:
        return {
            "error": "No reports found",
            "stats": None,
            "charts": None
        }
    
    # Calculate average final score
    total_final_score = 0
    final_score_count = 0
    final_scores = []
    highest_repo = {"name": None, "score": 0, "url": None}
    lowest_repo = {"name": None, "score": float('inf'), "url": None}

    for report in reports:
        if 'punteggio_totale' in report and isinstance(report['punteggio_totale'], (int, float)):
            score = report['punteggio_totale']
            total_final_score += score
            final_scores.append(score)
            # Track highest and lowest scoring repositories
            if score > highest_repo["score"]:
                highest_repo = {"name": report.get("nome_repository"), "score": score, "url": report.get("url")}
            if score < lowest_repo["score"]:
                lowest_repo = {"name": report.get("nome_repository"), "score": score, "url": report.get("url")}
            final_score_count += 1

    avg_final_score = total_final_score / final_score_count if final_score_count > 0 else 0
    median_score = np.median(final_scores) if final_scores else 0

    # Calculate category averages
    _, avg_category_scores = calculate_average_scores(reports)
    
    # Calculate variance and standard deviation
    variance = np.var(final_scores) if final_scores else 0
    std_dev = np.std(final_scores) if final_scores else 0

    # Calculate percentage of repositories in score ranges
    high_scores = len([score for score in final_scores if score >= 7])
    medium_scores = len([score for score in final_scores if 4 <= score < 7])
    low_scores = len([score for score in final_scores if score < 4])
    total_repos = len(final_scores)
    score_distribution = {
        "high": round((high_scores / total_repos) * 100, 2) if total_repos > 0 else 0,
        "medium": round((medium_scores / total_repos) * 100, 2) if total_repos > 0 else 0,
        "low": round((low_scores / total_repos) * 100, 2) if total_repos > 0 else 0
    }

    # Create summary stats
    summary_stats = {
        "total_repos": total_repos,
        "avg_score": round(avg_final_score, 2),
        "median_score": round(median_score, 2),
        "categories_count": len(avg_category_scores),
        "variance": round(variance, 2),
        "std_dev": round(std_dev, 2),
        "score_distribution": score_distribution,
        "highest_repo": highest_repo,
        "lowest_repo": lowest_repo
    }
    
    # Find highest and lowest scoring categories
    if avg_category_scores:
        best_category = max(avg_category_scores.items(), key=lambda x: x[1])
        worst_category = min(avg_category_scores.items(), key=lambda x: x[1])
        summary_stats["best_category"] = {
            "name": best_category[0],
            "score": round(best_category[1], 2)
        }
        summary_stats["worst_category"] = {
            "name": worst_category[0],
            "score": round(worst_category[1], 2)
        }

    # Create category scores dataframe
    if avg_category_scores:
        scores_df = pd.DataFrame({
            'Category': list(avg_category_scores.keys()),
            'Average Score': [round(score, 2) for score in avg_category_scores.values()]
        })
        scores_df = scores_df.sort_values(by='Average Score', ascending=False)
    else:
        scores_df = pd.DataFrame()
    
    # Create timeline data if timestamps are available
    timeline_data = None
    if any('data_analisi' in report for report in reports):
        timeline_data = [
            {'date': report.get('data_analisi'), 'score': report.get('punteggio_totale', 0)}
            for report in reports if 'data_analisi' in report
        ]
    
    return {
        "summary_stats": summary_stats,
        "category_scores": avg_category_scores,
        "scores_df": scores_df.to_dict('records'),
        "final_scores": final_scores,
        "timeline_data": timeline_data
    }

def calculate_detailed_metrics(reports):
    """Extract detailed metrics insights from reports."""
    if not reports:
        return None, None, None

    category_metrics = {}
    metric_weights = {}
    highest_metrics = {}
    lowest_metrics = {}

    for report in reports:
        if 'category_scores' in report:
            for category, metrics in report.get('category_scores', {}).items():
                if category not in category_metrics:
                    category_metrics[category] = []
                category_metrics[category].append(metrics)

        if 'metric_weights' in report:
            for metric, weight in report.get('metric_weights', {}).items():
                if metric not in metric_weights:
                    metric_weights[metric] = []
                metric_weights[metric].append(weight)

    # Calculate highest and lowest scoring metrics
    for category, metrics_list in category_metrics.items():
        highest_metrics[category] = max(metrics_list, key=lambda x: x['score'])
        lowest_metrics[category] = min(metrics_list, key=lambda x: x['score'])

    return category_metrics, metric_weights, highest_metrics, lowest_metrics

def create_category_chart(category_scores):
    """Create a bar chart for category scores."""
    fig = go.Figure(data=[
        go.Bar(
            x=list(category_scores.keys()),
            y=list(category_scores.values()),
            text=[f"{score:.2f}" for score in category_scores.values()],
            textposition='auto',
            marker_color='royalblue'
        )
    ])
    fig.update_layout(
        title="Punteggi medi (tutti i repository)",
        xaxis_title="Categoria",
        yaxis_title="Punteggio medio",
        yaxis=dict(range=[0, 10])
    )
    return pio.to_html(fig, full_html=False)

def create_distribution_chart(final_scores):
    """Create a histogram of final scores."""
    fig = px.histogram(
        x=final_scores, 
        nbins=10,
        labels={'x': 'Score', 'y': 'Count'},
        title="Distribuzione punteggio (tutti i repository)"
    )
    fig.update_layout(xaxis=dict(range=[0, 10]))
    return pio.to_html(fig, full_html=False)

def create_timeline_chart(timeline_data):
    """Create a line chart of scores over time."""
    if not timeline_data:
        return None
        
    df = pd.DataFrame(timeline_data)
    df = df.sort_values('date')
    
    fig = px.line(
        df, 
        x='date', 
        y='score',
        title="Andamento punteggi (tutti i repository)",
        labels={'date': 'Date', 'score': 'Score'}
    )
    fig.update_layout(yaxis=dict(range=[0, 10]))
    return pio.to_html(fig, full_html=False)

@app.route('/stats')
def stats_page():
    """Display the statistics page."""
    reports = load_all_reports()
    stats_data = calculate_statistics()
    category_metrics, metric_weights, highest_metrics, lowest_metrics = calculate_detailed_metrics(reports)

    if "error" in stats_data:
        return f"<h1>Statistics Error</h1><p>{stats_data['error']}</p>"

    # Generate charts
    category_chart = create_category_chart(stats_data["category_scores"]) if stats_data["category_scores"] else ""
    distribution_chart = create_distribution_chart(stats_data["final_scores"])
    timeline_chart = create_timeline_chart(stats_data["timeline_data"]) if stats_data["timeline_data"] else ""

    # Pass all data to template
    return render_template(
        'stats.html',
        stats=stats_data["summary_stats"],
        scores_table=stats_data["scores_df"],
        category_chart=category_chart,
        distribution_chart=distribution_chart,
        timeline_chart=timeline_chart,
        category_metrics=category_metrics,
        metric_weights=metric_weights,
        highest_metrics=highest_metrics,
        lowest_metrics=lowest_metrics
    )

# If running this file directly, start a development server
if __name__ == "__main__":
    # Create templates directory if it doesn't exist
    if not os.path.exists('templates'):
        os.makedirs('templates')
    
    # Create a simple template if it doesn't exist
    template_path = 'templates/stats.html'
    if not os.path.exists(template_path):
        with open(template_path, 'w') as f:
            f.write("""
<!DOCTYPE html>
<html>
<head>
    <title>Repository Statistics</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 20px; line-height: 1.6; }
        .container { max-width: 1200px; margin: 0 auto; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #f5f5f5; border-radius: 8px; padding: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .stat-value { font-size: 24px; font-weight: bold; margin-bottom: 5px; }
        .stat-label { color: #666; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #f2f2f2; }
        .chart-container { margin: 30px 0; }
        h1, h2 { color: #333; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Repository Statistics</h1>
        
        <h2>Summary Statistics</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">{{ stats.total_repos }}</div>
                <div class="stat-label">Total Repositories Analyzed</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.avg_score }}</div>
                <div class="stat-label">Average Overall Score</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{{ stats.categories_count }}</div>
                <div class="stat-label">Categories Evaluated</div>
            </div>
            {% if stats.best_category %}
            <div class="stat-card">
                <div class="stat-value">{{ stats.best_category.name }}</div>
                <div class="stat-label">Highest Scoring Category ({{ stats.best_category.score }})</div>
            </div>
            {% endif %}
        </div>

        <h2>Category Average Scores</h2>
        <div class="chart-container">
            {{ category_chart|safe }}
        </div>

        <h2>Detailed Category Scores</h2>
        <table>
            <thead>
                <tr>
                    <th>Category</th>
                    <th>Average Score</th>
                </tr>
            </thead>
            <tbody>
                {% for score in scores_table %}
                <tr>
                    <td>{{ score.Category }}</td>
                    <td>{{ score['Average Score'] }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <h2>Distribution of Repository Scores</h2>
        <div class="chart-container">
            {{ distribution_chart|safe }}
        </div>

        {% if timeline_chart %}
        <h2>Report Timeline</h2>
        <div class="chart-container">
            {{ timeline_chart|safe }}
        </div>
        {% endif %}
    </div>
</body>
</html>
            """)
    
    print("Starting Flask server on port 5001. Access statistics at http://localhost:5001/stats")
    app.run(host='0.0.0.0', port=5001, debug=True)
