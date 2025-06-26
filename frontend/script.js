// Function to create the Sentiment by Importance Stacked Bar Chart (uses all_mapped_comments_list)
function createSentimentImportanceChart(canvasElement, allMappedCommentsList) {
    const importanceLevels = ['1', '2', '3', '4', '5'];
    // Define all expected sentiments, including analysis outcomes, in the desired legend order
    const allSentimentsInOrder = ['Positive', 'Negative', 'Neutral', 'Mixed', 'Unknown', 'Skipped - Empty', 'Failed Analysis'];

    // Aggregate counts: { importanceLevel: { sentiment: count, ... }, ... }
    const countsByImportance = importanceLevels.reduce((acc, level) => {
        acc[level] = {};
        allSentimentsInOrder.forEach(s => acc[level][s] = 0); // Initialize sentiment counts for this level
        return acc;
    }, {});

    allMappedCommentsList.forEach(item => {
        // Get importance, ensuring it's a number between 1 and 5
        const importance = item.Importance !== undefined ? item.Importance : null;
        const sentiment = item.Sentiment || 'Unknown'; // Default to Unknown if sentiment is missing

        if (typeof importance === 'number' && importance >= 1 && importance <= 5) {
             // Ensure sentiment is one of the expected ones, fallback to Unknown if unexpected
            const mappedSentiment = allSentimentsInOrder.includes(sentiment) ? sentiment : 'Unknown';
            countsByImportance[importance][mappedSentiment]++;
        } else {
            // Log items with invalid/missing importance if necessary
            if (importance !== null && importance !== 0) {
                 console.warn("Skipping item with invalid/unexpected importance for sentiment/importance chart:", item);
            } else {
                 // Optionally count items with Importance 0 or null under an 'N/A' or '0' category if you add one
            }
        }
    });

    // Prepare datasets for the stacked bar chart
    // Create datasets for each sentiment, but *only* if that sentiment appears in the data for at least one bar
    const datasets = allSentimentsInOrder // Iterate in desired legend order
    .map(sentiment => {
         // Get color from the JS palette
         const color = chartColors.sentiment[sentiment] || '#adb5bd'; // Fallback gray

         const dataForSentiment = importanceLevels.map(level => countsByImportance[level][sentiment]);

         // Only include this sentiment dataset if it has at least one non-zero count
         if (dataForSentiment.some(count => count > 0)) {
              return {
                  label: sentiment, // Label for this dataset (sentiment)
                  data: dataForSentiment, // Data for this sentiment across importance levels
                  backgroundColor: color,
                  borderColor: color,
                  borderWidth: 1,
                  stack: 'SentimentStack' // All datasets share the same stack name
              };
         } else {
             return null; // Exclude this dataset if all counts are zero
         }
    })
    .filter(dataset => dataset !== null); // Remove null entries (datasets with all zero counts)


     // Destroy existing chart instance if it exists on this canvas
    if (Chart.getChart(canvasElement)) {
        Chart.getChart(canvasElement).destroy();
    }


    sentimentImportanceChart = new Chart(canvasElement, {
        type: 'bar', // Stacked Bar chart
        data: {
            labels: importanceLevels, // X-axis labels are importance levels (1-5)
            datasets: datasets // Use the prepared datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    // --- THIS LINE CONTROLS THE LEGEND POSITION ---
                    position: 'bottom', // Set legend to appear at the bottom

                     labels: {
                         color: '#343a40', // Use hex code directly
                         // --- OPTIONAL: Reduce font size if needed, uncomment below ---
                         // font: {
                         //     size: 10 // Adjust size as needed
                         // }
                     }
                },
                title: {
                    display: true,
                    text: 'Sentiment Breakdown by Importance Level',
                    color: '#343a40' // Use hex code directly
                },
                tooltip: {
                     mode: 'index', // Show tooltip for all items at that index
                     intersect: false,
                     callbacks: {
                         label: function(context) {
                             const label = context.dataset.label || ''; // Sentiment label
                             const value = context.raw; // Count
                             // Find percentage within this bar (optional, more complex calculation needed)
                             // For simplicity, just show count
                              return `${label}: ${value}`;
                         }
                     }
                 }
            },
            scales: {
                x: { // X-axis (Importance Level)
                     stacked: true, // Make bars stacked
                     ticks: {
                         color: '#6c757d' // Use hex code directly
                     },
                      title: {
                        display: true,
                        text: 'Importance Level',
                        color: '#343a40' // Use hex code directly
                    }
                },
                y: { // Y-axis (Count)
                    stacked: true, // Make bars stacked
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                         color: '#6c757d' // Use hex code directly
                    },
                    title: {
                        display: true,
                        text: 'Count',
                        color: '#343a40' // Use hex code directly
                    }
                }
            }
        }
    });
}

// ... (rest of your code remains the same)
// !!! IMPORTANT: Replace with your actual API Gateway Invoke URL !!!
const API_BASE_URL = 'https://xx839r420m.execute-api.ap-northeast-1.amazonaws.com/v1';

// Global variables to hold chart instances
let sentimentBarChart = null;
let categoryBarChart = null;
let importanceDistributionChart = null;
let sentimentImportanceChart = null;

// --- Define Color Palettes in JavaScript ---
const chartColors = {
    // Sentiment colors
    sentiment: {
        'Positive': '#28a745', // Green
        'Negative': '#dc3545', // Red
        'Neutral': '#ffc107', // Yellow
        'Mixed': '#6610f2', // Indigo
        'Unknown': '#6c757d', // Gray
        'Skipped - Empty': '#ced4da', // Light gray
        'Failed Analysis': '#495057' // Dark gray
    },
    // Category colors
    category: {
        'Lecture Content': '#007bff', // Primary Blue
        'Lecture Materials': '#20c997', // Teal
        'Operations': '#fd7e14', // Orange
        'Other': '#e83e8c', // Pink
        'Unknown': '#6c757d', // Gray
        'Skipped - Empty': '#ced4da', // Light gray
        'Failed Analysis': '#495057' // Dark gray
    },
    // Importance colors (for distribution)
    importance: {
        1: '#007bff', // Blue
        2: '#28a745', // Green
        3: '#ffc107', // Yellow
        4: '#fd7e14', // Orange
        5: '#dc3545' // Red
    }
};


document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded. Fetching data...");
    // Ensure Chart.js is loaded before attempting to use it
    if (typeof Chart === 'undefined') {
        console.error("Chart.js library not loaded. Please check CDN link in index.html");
        document.getElementById('status-area').textContent = 'Error: Charting library failed to load.';
         document.getElementById('status-area').className = 'status-message error';
        return; // Stop execution if chartjs is not available
    }
    // Optional: Register the DataLabels plugin if using it in HTML (currently commented out)
    // if (window.ChartDataLabels) {
    //      Chart.register(window.ChartDataLabels);
    // }

    fetchAndDisplayStats();
    setupExportButton();
});

// Function to destroy existing charts before creating new ones
function destroyCharts() {
    if (sentimentBarChart) {
        sentimentBarChart.destroy();
        sentimentBarChart = null;
    }
    if (categoryBarChart) {
        categoryBarChart.destroy();
        categoryBarChart = null;
    }
     if (importanceDistributionChart) {
        importanceDistributionChart.destroy();
        importanceDistributionChart = null;
    }
     if (sentimentImportanceChart) {
        sentimentImportanceChart.destroy();
        sentimentImportanceChart = null;
    }
     console.log("Existing charts destroyed.");
}


async function fetchAndDisplayStats() {
    const statusArea = document.getElementById('status-area');
    const totalCommentsEl = document.getElementById('total-comments');
    const sentimentTableBody = document.querySelector('#sentiment-table tbody');
    const categoryTableBody = document.querySelector('#category-table tbody');
    const highRiskCountEl = document.getElementById('high-risk-count');
    const highRiskTableBody = document.querySelector('#high-risk-table tbody');
    const topImportantTableBody = document.querySelector('#top-important-table tbody');

    // Get canvas elements for charts
    const sentimentCanvas = document.getElementById('sentimentBarChart');
    const categoryCanvas = document.getElementById('categoryBarChart');
    const importanceDistributionCanvas = document.getElementById('importanceDistributionChart');
    const sentimentImportanceCanvas = document.getElementById('sentimentImportanceChart');


    statusArea.textContent = 'Loading analysis data...';
    statusArea.className = 'status-message loading'; // Add loading class for styling

    // Clear previous data and destroy old charts
    totalCommentsEl.textContent = '';
    sentimentTableBody.innerHTML = '';
    categoryTableBody.innerHTML = '';
    highRiskCountEl.textContent = '';
    highRiskTableBody.innerHTML = '';
    topImportantTableBody.innerHTML = '';
    destroyCharts(); // Destroy charts before loading new data

    // Hide all chart containers initially
     const chartCanvasElements = document.querySelectorAll('.chart-container canvas'); // Correctly select canvas elements
     chartCanvasElements.forEach(canvas => canvas.style.display = 'none');


    try {
        console.log(`Attempting to fetch stats from: ${API_BASE_URL}/stats`);
        const response = await fetch(`${API_BASE_URL}/stats`);

        if (!response.ok) {
            // Handle non-2xx status codes (e.g., 400, 500)
            const errorText = await response.text();
             console.error(`Fetch failed with HTTP status ${response.status}:`, errorText);
            throw new Error(`HTTP error ${response.status}: ${errorText}`);
        }

        const data = await response.json(); // This parses the OUTER API Gateway response { statusCode, headers, body }

        console.log("Outer API Gateway response:", data); // Log the outer structure

        // --- Check if the outer response has a body and parse the inner JSON string ---
        if (!data || !data.body || typeof data.body !== 'string') {
            console.error('API response is missing the body or body is not a string:', data);
             throw new Error('API returned unexpected response structure.');
        }

        // Parse the JSON string inside the 'body' property
        const stats = JSON.parse(data.body);

        console.log("Inner stats data parsed successfully:", stats); // Log the actual stats object


        // The Lambda now includes {"error": "..."} in the body for backend errors,
        // check for this error *after* parsing the inner body
        if (stats && stats.error) {
             console.error('Backend stats Lambda returned an error in the body:', stats.error);
             throw new Error(`Backend error: ${stats.error}`);
        }
         // Also check if the parsed inner body is unexpectedly empty or not an object
         if (!stats || typeof stats !== 'object' || Object.keys(stats).length === 0 || (stats.total_comments || 0) === 0) {
             console.warn('Parsed inner stats data is empty, unexpected format, or total_comments is 0:', stats);
             // Display "No data available" messages in status and tables
             statusArea.textContent = 'No analysis data available to display. Please process a CSV file first.';
             statusArea.className = 'status-message'; // Reset class
             totalCommentsEl.textContent = `Total Comments Processed: 0`;
             sentimentTableBody.innerHTML = '<tr><td colspan="3">No sentiment data available.</td></tr>';
             categoryTableBody.innerHTML = '<tr><td colspan="4">No category data available.</td></tr>';
             highRiskCountEl.textContent = `Total High-Risk: 0`;
             highRiskTableBody.innerHTML = '<tr><td colspan="5">No high-risk comments identified.</td></tr>';
             topImportantTableBody.innerHTML = '<tr><td colspan="5">No top important comments identified.</td></tr>';

            // Hide charts if no data
             if(sentimentCanvas) sentimentCanvas.style.display = 'none';
             if(categoryCanvas) categoryCanvas.style.display = 'none';
             if(importanceDistributionCanvas) importanceDistributionCanvas.style.display = 'none';
             if(sentimentImportanceCanvas) sentimentImportanceCanvas.style.display = 'none';


             return; // Exit the function here if no data
         }


        // Update status area
        statusArea.textContent = 'Data loaded successfully.';
        statusArea.className = 'status-message success'; // Set class to success


        // --- Display Overall Stats ---
        totalCommentsEl.textContent = `Total Comments Processed: ${stats.total_comments || 0}`;
        console.log(`Total comments reported by backend: ${stats.total_comments || 0}`);

        // --- Display Sentiment Stats (Table) ---
        const sentimentRows = [];
        // Check if sentiment_counts exists, is an object, and has entries
        if (stats.sentiment_counts && typeof stats.sentiment_counts === 'object' && Object.keys(stats.sentiment_counts).length > 0) {
            console.log("Populating sentiment table...");
            // Sort labels alphabetically, putting 'Unknown', 'Skipped', 'Failed' last (Optional but cleaner)
             const sortOrder = ['Positive', 'Negative', 'Neutral', 'Mixed', 'Lecture Content', 'Lecture Materials', 'Operations', 'Other', 'Unknown', 'Skipped - Empty', 'Failed Analysis'];
             const labels = Object.keys(stats.sentiment_counts).sort((a, b) => {
                 const indexA = sortOrder.indexOf(a);
                 const indexB = sortOrder.indexOf(b);
                 if (indexA === -1) return 1; // Put unknown items at the end
                 if (indexB === -1) return -1;
                 return indexA - indexB;
             });

            for (const sentiment of labels) { // Use sorted labels to iterate
                 const count = stats.sentiment_counts[sentiment];
                const percentage = (stats.sentiment_percentages && stats.sentiment_percentages[sentiment] !== undefined) ? stats.sentiment_percentages[sentiment].toFixed(1) : 'N/A';
                sentimentRows.push(`<tr><td>${sentiment}</td><td>${count}</td><td>${percentage}</td></tr>`);
            }
        } else {
             console.log("No sentiment_counts data for table.");
             sentimentRows.push('<tr><td colspan="3">No sentiment data available.</td></tr>');
        }
        sentimentTableBody.innerHTML = sentimentRows.join('');

        // --- Display Sentiment Bar Chart ---
        if (sentimentCanvas && stats.sentiment_counts && typeof stats.sentiment_counts === 'object' && Object.keys(stats.sentiment_counts).length > 0) {
             sentimentCanvas.style.display = 'block'; // Show canvas
             createSentimentBarChart(sentimentCanvas, stats.sentiment_counts, stats.sentiment_percentages);
        } else if (sentimentCanvas) {
             sentimentCanvas.style.display = 'none';
        }


        // --- Display Category Stats (Table) ---
        const categoryRows = [];
         // Check if category_counts exists, is an object, and has entries
        if (stats.category_counts && typeof stats.category_counts === 'object' && Object.keys(stats.category_counts).length > 0) {
            console.log("Populating category table...");
            // Sort labels alphabetically, putting 'Unknown', 'Skipped', 'Failed' last
            const sortOrder = ['Lecture Content', 'Lecture Materials', 'Operations', 'Other', 'Positive', 'Negative', 'Neutral', 'Mixed', 'Unknown', 'Skipped - Empty', 'Failed Analysis'];
             const labels = Object.keys(stats.category_counts).sort((a, b) => {
                 const indexA = sortOrder.indexOf(a);
                 const indexB = sortOrder.indexOf(b);
                 if (indexA === -1) return 1;
                 if (indexB === -1) return -1;
                 return indexA - indexB;
             });
            for (const category of labels) { // Use sorted labels to iterate
                 const count = stats.category_counts[category];
                const percentage = (stats.category_percentages && stats.category_percentages[category] !== undefined) ? stats.category_percentages[category].toFixed(1) : 'N/A';
                const actionRecommended = (stats.recommended_actions && typeof stats.recommended_actions === 'object' && stats.recommended_actions[category] !== undefined) ? (stats.recommended_actions[category] ? 'Yes' : 'No') : 'N/A';
                categoryRows.push(`<tr><td>${category}</td><td>${count}</td><td>${percentage}</td><td>${actionRecommended}</td></tr>`);
            }
        } else {
            console.log("No category_counts data for table.");
             categoryRows.push('<tr><td colspan="4">No category data available.</td></tr>');
        }
        categoryTableBody.innerHTML = categoryRows.join('');

        // --- Display Category Bar Chart ---
        if (categoryCanvas && stats.category_counts && typeof stats.category_counts === 'object' && Object.keys(stats.category_counts).length > 0) {
             categoryCanvas.style.display = 'block'; // Show canvas
             createCategoryChart(categoryCanvas, stats.category_counts, stats.category_percentages);
        } else if (categoryCanvas) {
            categoryCanvas.style.display = 'none';
        }

        // --- Display Importance Distribution Chart (using all_mapped_comments_list) ---
         // This requires the backend to return stats.all_mapped_comments_list
         if (importanceDistributionCanvas && stats.all_mapped_comments_list && Array.isArray(stats.all_mapped_comments_list) && stats.all_mapped_comments_list.length > 0) {
             importanceDistributionCanvas.style.display = 'block'; // Show canvas
             console.log("Creating Importance Distribution Chart...");
             createImportanceDistributionChart(importanceDistributionCanvas, stats.all_mapped_comments_list); // Pass the list of comments
         } else if (importanceDistributionCanvas) {
             console.log("No data or list found for Importance Distribution Chart.");
             importanceDistributionCanvas.style.display = 'none';
         }

         // --- Display Sentiment by Importance Stacked Bar Chart (using all_mapped_comments_list) ---
         // This requires the backend to return stats.all_mapped_comments_list
         if (sentimentImportanceCanvas && stats.all_mapped_comments_list && Array.isArray(stats.all_mapped_comments_list) && stats.all_mapped_comments_list.length > 0) {
             sentimentImportanceCanvas.style.display = 'block'; // Show canvas
             console.log("Creating Sentiment by Importance Chart...");
             createSentimentImportanceChart(sentimentImportanceCanvas, stats.all_mapped_comments_list); // Pass the list of comments
         } else if (sentimentImportanceCanvas) {
             console.log("No data or list found for Sentiment by Importance Chart.");
             sentimentImportanceCanvas.style.display = 'none';
         }


        // --- Display High-Risk Comments (Table) ---
        highRiskCountEl.textContent = `Total High-Risk: ${stats.high_risk_count || 0}`;
         console.log(`High-risk comments count reported by backend: ${stats.high_risk_count || 0}`);
        const highRiskCommentRows = [];
        // Check if high_risk_comments_list is an array and has items
        if (stats.high_risk_comments_list && Array.isArray(stats.high_risk_comments_list) && stats.high_risk_comments_list.length > 0) {
             console.log(`Populating ${stats.high_risk_comments_list.length} high-risk comments table...`);
             // Optional: Sort high-risk comments by importance (high to low)
             const sortedHighRisk = [...stats.high_risk_comments_list].sort((a, b) => (b.Importance || 0) - (a.Importance || 0));

            sortedHighRisk.forEach(comment => {
                 // Ensure each comment object is valid before accessing properties
                if (comment && typeof comment === 'object') {
                    // Safely access properties with defaults
                    const importance = comment.Importance !== undefined ? comment.Importance : 'N/A';
                    const originalComment = comment.OriginalComment || 'No Comment Text';
                    const sentiment = comment.Sentiment || 'N/A';
                    const category = comment.Category || 'N/A';
                    const originalRowIndex = comment.OriginalCsvRowIndex !== undefined ? comment.OriginalCsvRowIndex : 'N/A';

                    highRiskCommentRows.push(`
                        <tr>
                            <td>${importance}</td>
                            <td>${escapeHTML(originalComment)}</td>
                            <td>${sentiment}</td>
                            <td>${category}</td>
                            <td>${originalRowIndex}</td>
                        </tr>`);
                    } else {
                         console.warn("Encountered invalid item in high_risk_comments_list:", comment);
                    }
            });
        } else {
             console.log("No high_risk_comments_list data for table.");
             highRiskCommentRows.push('<tr><td colspan="5">No high-risk comments identified.</td></tr>');
        }
        highRiskTableBody.innerHTML = highRiskCommentRows.join('');


        // --- Display Top Important Comments (Table) ---
        const topImportantCommentRows = [];
         // Check if top_important_comments is an array and has items
         if (stats.top_important_comments && Array.isArray(stats.top_important_comments) && stats.top_important_comments.length > 0) {
            console.log(`Populating ${stats.top_important_comments.length} top important comments table...`);
            // The list is already sorted by importance from the backend
            // Optional: Limit the number of displayed top comments if the list is very long
            // const commentsToDisplay = stats.top_important_comments.slice(0, 20); // Show max 20
            // commentsToDisplay.forEach(comment => { ... });
            stats.top_important_comments.forEach(comment => {
                 // Ensure each comment object is valid before accessing properties
                if (comment && typeof comment === 'object') {
                     // Safely access properties with defaults
                    const importance = comment.Importance !== undefined ? comment.Importance : 'N/A';
                    const originalComment = comment.OriginalComment || 'No Comment Text';
                    const sentiment = comment.Sentiment || 'N/A';
                    const category = comment.Category || 'N/A';
                    const originalRowIndex = comment.OriginalCsvRowIndex !== undefined ? comment.OriginalCsvRowIndex : 'N/A';

                    topImportantCommentRows.push(`
                        <tr>
                            <td>${importance}</td>
                            <td>${escapeHTML(originalComment)}</td>
                            <td>${sentiment}</td>
                            <td>${category}</td>
                            <td>${originalRowIndex}</td>
                        </tr>`);
                    } else {
                         console.warn("Encountered invalid item in top_important_comments:", comment);
                    }
            });
        } else {
             console.log("No top_important_comments data for table.");
             topImportantCommentRows.push('<tr><td colspan="5">No top important comments identified.</td></tr>');
        }
        topImportantTableBody.innerHTML = topImportantCommentRows.join('');


    } catch (error) {
        console.error('Error fetching or processing data:', error); // More general error message
        statusArea.textContent = `Error loading data: ${error.message}`;
        statusArea.className = 'status-message error'; // Add error class for styling

        // Destroy charts on error
        destroyCharts();
        // Hide charts explicitly on error
        const chartCanvasElements = document.querySelectorAll('.chart-container canvas'); // Corrected selector
        chartCanvasElements.forEach(canvas => canvas.style.display = 'none');


        // Display fallback messages in tables if an error occurred at any step
        sentimentTableBody.innerHTML = '<tr><td colspan="3">Error loading data.</td></tr>';
        categoryTableBody.innerHTML = '<tr><td colspan="4">Error loading data.</td></tr>';
        highRiskTableBody.innerHTML = '<tr><td colspan="5">Error loading data.</td></tr>';
        topImportantTableBody.innerHTML = '<tr><tr><td colspan="5">Error loading data.</td></tr>';
    }
}


// --- Chart Creation Functions ---

// Function to create the Sentiment Bar Chart
function createSentimentBarChart(canvasElement, sentimentCounts, sentimentPercentages) {
    // Sort labels alphabetically, putting 'Unknown', 'Skipped', 'Failed' last (Optional but cleaner)
     const sortOrder = ['Positive', 'Negative', 'Neutral', 'Mixed', 'Lecture Content', 'Lecture Materials', 'Operations', 'Other', 'Unknown', 'Skipped - Empty', 'Failed Analysis'];
     const labels = Object.keys(sentimentCounts).sort((a, b) => {
         const indexA = sortOrder.indexOf(a);
         const indexB = sortOrder.indexOf(b);
         if (indexA === -1) return 1; // Put unknown items at the end
         if (indexB === -1) return -1;
         return indexA - indexB;
     });

    const data = labels.map(label => sentimentCounts[label]);
    const percentages = labels.map(label => (sentimentPercentages && sentimentPercentages[label] !== undefined) ? sentimentPercentages[label].toFixed(1) + '%' : 'N/A');

    // Define colors based on sentiment labels, using the JS palette
    const backgroundColors = labels.map(label => chartColors.sentiment[label] || '#adb5bd'); // Fallback gray
    const borderColors = backgroundColors.map(color => color); // Border matches fill


    // Destroy existing chart instance if it exists on this canvas
    if (Chart.getChart(canvasElement)) {
        Chart.getChart(canvasElement).destroy();
    }

    sentimentBarChart = new Chart(canvasElement, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Comment Count',
                data: data,
                backgroundColor: backgroundColors,
                borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false // This chart does not display a legend
                },
                title: {
                    display: true,
                    text: 'Sentiment Distribution',
                    color: '#343a40' // Use hex code directly for robustness if CSS vars fail
                },
                 tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw;
                            const index = context.dataIndex;
                            const percentage = percentages[index];
                            return `${label}: ${value} (${percentage})`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                         color: '#6c757d' // Use hex code directly
                    },
                    title: {
                        display: true,
                        text: 'Count',
                        color: '#343a40' // Use hex code directly
                    }
                },
                x: {
                     ticks: {
                         color: '#6c757d' // Use hex code directly
                     },
                     title: {
                         display: false,
                     }
                }
            }
        }
    });
}


// Function to create the Category Bar Chart
function createCategoryChart(canvasElement, categoryCounts, categoryPercentages) {
    // Sort labels alphabetically, putting 'Unknown', 'Skipped', 'Failed' last
    const sortOrder = ['Lecture Content', 'Lecture Materials', 'Operations', 'Other', 'Positive', 'Negative', 'Neutral', 'Mixed', 'Unknown', 'Skipped - Empty', 'Failed Analysis'];
     const labels = Object.keys(categoryCounts).sort((a, b) => {
         const indexA = sortOrder.indexOf(a);
         const indexB = sortOrder.indexOf(b);
         if (indexA === -1) return 1;
         if (indexB === -1) return -1;
         return indexA - indexB;
     });
    const data = labels.map(label => categoryCounts[label]);
    const percentages = labels.map(label => (categoryPercentages && categoryPercentages[label] !== undefined) ? categoryPercentages[label].toFixed(1) + '%' : 'N/A');

    // Define colors based on category labels, using the JS palette
    const backgroundColors = labels.map(label => chartColors.category[label] || '#adb5bd'); // Fallback gray
    const borderColors = backgroundColors.map(color => color);

    // Destroy existing chart instance if it exists on this canvas
    if (Chart.getChart(canvasElement)) {
        Chart.getChart(canvasElement).destroy();
    }


    categoryBarChart = new Chart(canvasElement, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Comment Count by Category',
                data: data,
                backgroundColor: backgroundColors,
                 borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false // This chart does not display a legend
                },
                title: {
                    display: true,
                    text: 'Category Breakdown',
                    color: '#343a40' // Use hex code directly
                },
                 tooltip: {
                    callbacks: {
                         label: function(context) {
                            const label = context.label || '';
                            const value = context.raw;
                            const index = context.dataIndex;
                            const percentage = percentages[index];
                             return `${label}: ${value} (${percentage})`;
                         }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                         color: '#6c757d' // Use hex code directly
                    },
                    title: {
                        display: true,
                        text: 'Count',
                        color: '#343a40' // Use hex code directly
                    }
                },
                x: {
                     ticks: {
                         color: '#6c757d' // Use hex code directly
                     },
                     title: {
                         display: false,
                     }
                }
            }
        }
    });
}


// Function to create the Importance Distribution Chart (uses all_mapped_comments_list)
function createImportanceDistributionChart(canvasElement, allMappedCommentsList) {
    // Count how many comments have each importance level (1-5)
    const importanceCounts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0};

    allMappedCommentsList.forEach(item => {
        // Get importance, ensuring it's a number between 1 and 5
        const importance = item.Importance !== undefined ? item.Importance : null;
         if (typeof importance === 'number' && importance >= 1 && importance <= 5) {
             importanceCounts[importance]++;
         } else {
             // Log a warning if an item has unexpected importance data, excluding 0 or null
             if (importance !== null && importance !== 0) {
                console.warn("Skipping item with invalid/unexpected importance for distribution chart:", item);
             }
         }
    });

    // Use labels 1 through 5
    const labels = ['1', '2', '3', '4', '5'];
    // Map counts to labels, ensuring 0 for levels with no comments
    const data = labels.map(label => importanceCounts[parseInt(label)] || 0);


    // Define colors for importance levels (e.g., greener for low, redder for high), using the JS palette
     const backgroundColors = labels.map(label => chartColors.importance[parseInt(label)] || '#adb5bd'); // Fallback gray
     const borderColors = backgroundColors.map(color => color);

    // Destroy existing chart instance if it exists on this canvas
    if (Chart.getChart(canvasElement)) {
        Chart.getChart(canvasElement).destroy();
    }

    importanceDistributionChart = new Chart(canvasElement, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Number of Comments',
                data: data,
                backgroundColor: backgroundColors,
                 borderColor: borderColors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false // This chart does not display a legend
                },
                title: {
                    display: true,
                    text: 'Importance Distribution (1-5)',
                    color: '#343a40' // Use hex code directly
                },
                 tooltip: {
                    callbacks: {
                         label: function(context) {
                            const value = context.raw;
                            const importanceLevel = context.label || '';
                             return `Importance ${importanceLevel}: ${value} comments`;
                         }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                         color: '#6c757d' // Use hex code directly
                    },
                     title: {
                        display: true,
                        text: 'Count',
                        color: '#343a40' // Use hex code directly
                    }
                },
                x: {
                     ticks: {
                         color: '#6c757d' // Use hex code directly
                     },
                     title: {
                        display: true,
                        text: 'Importance Level',
                        color: '#343a40' // Use hex code directly
                    }
                }
            }
        }
    });
}


function setupExportButton() {
    const exportButton = document.getElementById('export-button');
    // Check if the button element exists
    if (exportButton) {
        exportButton.addEventListener('click', () => {
            console.log("Export button clicked. Triggering CSV download...");
            // Simply navigate to the export endpoint. The browser handles the download due to Content-Disposition header.
            // Ensure the export Lambda also has CORS headers!
            window.location.href = `${API_BASE_URL}/export/csv`;
        });
    } else {
        console.error("Export button element not found!");
    }
}

// Simple helper function to prevent basic XSS if comments contain HTML/script tags
function escapeHTML(str) {
    // Ensure input is treated as a string
    const stringValue = String(str || ''); // Handle null/undefined by converting to empty string
    const div = document.createElement('div');
    div.appendChild(document.createTextNode(stringValue));
    return div.innerHTML;
}