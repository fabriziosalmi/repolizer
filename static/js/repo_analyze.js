// ... existing code ...

let eventSource = null;
let currentJobId = null;
let analysisResultsData = null; // Store the full results object

// ... existing code ...

function connectAnalyzerStream(jobId) {
    // ... existing code ...
    analysisResultsData = null; // Reset results data on new connection
    // ... existing code ...

    eventSource.addEventListener('complete', (event) => {
        console.log('Analysis complete event received:', event.data);
        const data = JSON.parse(event.data);
        analysisResultsData = data.results; // Store the full results

        // Update UI
        progressBar.style.width = '100%';
        progressBar.classList.remove('bg-blue-500');
        progressBar.classList.add('bg-green-500');
        statusText.textContent = 'Analysis completed successfully.';
        stopButton.disabled = true;
        stopButton.classList.add('hidden'); // Hide stop button
        analyzeButton.disabled = false; // Re-enable analyze button

        // Display summary
        displayResultsSummary(analysisResultsData);

        // Show and configure action buttons
        const resultsActions = document.getElementById('resultsActions');
        const downloadButton = document.getElementById('downloadReportButton');
        const viewReportButton = document.getElementById('viewReportButton');

        if (resultsActions && downloadButton && viewReportButton && analysisResultsData && analysisResultsData.repository) {
            // Set the href for the View Report button
            // Use encodeURIComponent in case the repo name has special characters
            const repoIdForLink = encodeURIComponent(analysisResultsData.repository.id || analysisResultsData.repository.full_name);
            viewReportButton.href = `/repo/${repoIdForLink}`;

            resultsActions.classList.remove('hidden'); // Show the buttons container

            // Add download functionality
            downloadButton.onclick = () => {
                downloadJsonReport(analysisResultsData);
            };

        } else {
             console.error("Could not find action buttons or results data is incomplete.");
        }


        // Add final log message
        addLogMessage('Analysis completed.', 'complete');

        // Close the connection
        if (eventSource) {
            eventSource.close();
            eventSource = null;
            console.log('SSE connection closed.');
        }
    });

    // ... existing error and log handlers ...
}

function displayResultsSummary(results) {
    const resultsSummaryDiv = document.getElementById('resultsSummary');
    const analysisResultsDiv = document.getElementById('analysisResults'); // Get the main results container

    if (!resultsSummaryDiv || !analysisResultsDiv) return;

    analysisResultsDiv.classList.remove('hidden'); // Ensure the results area is visible

    let summaryHtml = '<p class="text-gray-700">Analysis finished. ';
    if (results && results.overall_score !== undefined) {
        const score = results.overall_score.toFixed(1);
        let scoreColor = 'text-gray-600';
        if (score >= 70) scoreColor = 'text-green-600';
        else if (score >= 40) scoreColor = 'text-yellow-600';
        else scoreColor = 'text-red-600';

        summaryHtml += `Overall Score: <strong class="${scoreColor}">${score}/100</strong>. `;
    }
    if (results && results.total_checks !== undefined) {
        summaryHtml += `Total checks performed: <strong>${results.total_checks}</strong>.`;
    }
     if (results && results.repository && results.repository.full_name) {
         summaryHtml += `<br>Repository: <strong>${results.repository.full_name}</strong>`;
     }
     if (results && results.timestamp) {
         const formattedTimestamp = new Date(results.timestamp).toLocaleString();
         summaryHtml += `<br>Timestamp: <span class="text-xs text-gray-500">${formattedTimestamp}</span>`;
     }

    summaryHtml += '</p>';
    resultsSummaryDiv.innerHTML = summaryHtml;
}

// Function to trigger JSON download
function downloadJsonReport(data) {
    if (!data || !data.repository) {
        console.error("Cannot download report: results data is missing or incomplete.");
        alert("Error: Analysis results data is not available for download.");
        return;
    }
    try {
        const jsonString = JSON.stringify(data, null, 2); // Pretty print JSON
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        // Sanitize filename
        const repoName = (data.repository.full_name || data.repository.id || 'report').replace(/[^a-z0-9_\-]/gi, '_');
        a.href = url;
        a.download = `repolizer_analysis_${repoName}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url); // Clean up the object URL
    } catch (error) {
        console.error("Error creating or downloading JSON report:", error);
        alert("Error generating report for download.");
    }
}


// ... existing stopAnalysis, addLogMessage, etc. functions ...

// Modify the initial form submission logic if needed
analyzeForm.addEventListener('submit', (event) => {
    event.preventDefault();
    // ... existing code to gather config ...

    // Reset UI before starting
    progressBar.style.width = '0%';
    progressBar.classList.remove('bg-green-500', 'bg-red-500');
    progressBar.classList.add('bg-blue-500');
    statusText.textContent = 'Starting analysis...';
    logContainer.innerHTML = ''; // Clear previous logs
    document.getElementById('analysisResults').classList.add('hidden'); // Hide previous results
    document.getElementById('resultsActions').classList.add('hidden'); // Hide action buttons
    analysisResultsData = null; // Clear previous results data

    // ... existing fetch call to /api/analyze ...
});
