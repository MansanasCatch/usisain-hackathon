export let trendChartInstance = null;
export let verdictChartInstance = null;

export const centerTextPlugin = {
  id: 'centerText',
  afterDraw: (chart) => {
    if (chart.config.type !== 'doughnut') return;
    const { ctx } = chart;
    const meta = chart.getDatasetMeta(0);
    if (!meta || !meta.data || !meta.data[0]) return;
    
    let total = 0;
    let visibleCount = 0;
    meta.data.forEach((element, index) => {
      if (chart.getDataVisibility(index)) {
        total += chart.data.datasets[0].data[index];
        visibleCount++;
      }
    });
    
    const displayVal = visibleCount > 0 ? total : (window.lastTotalScans || 0);
    const x = meta.data[0].x;
    const y = meta.data[0].y;
    
    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = 'bold 24px "Space Grotesk", sans-serif';
    ctx.fillStyle = '#f3f4f6';
    ctx.fillText(displayVal.toString(), x, y - 8);
    
    ctx.font = '600 9px "Inter", sans-serif';
    ctx.fillStyle = '#9ca3af';
    ctx.fillText('SCANS', x, y + 12);
    ctx.restore();
  }
};

export function renderTrendChart(days, channels, trend) {
  const colors = { extension: "#6366f1", webapp: "#f59e0b", api: "#10b981" };
  const chartColorsGlow = {
    extension: "rgba(99, 102, 241, 0.15)",
    webapp: "rgba(245, 158, 11, 0.15)",
    api: "rgba(16, 185, 129, 0.15)"
  };

  const trendCanvas = document.getElementById("trend-chart");
  if (!trendCanvas) return;
  const trendCtx = trendCanvas.getContext("2d");
  
  if (trendChartInstance) {
    trendChartInstance.destroy();
  }

  const datasets = channels.map(c => {
    const gradient = trendCtx.createLinearGradient(0, 0, 0, 240);
    gradient.addColorStop(0, chartColorsGlow[c] || "rgba(156, 163, 175, 0.15)");
    gradient.addColorStop(1, "rgba(9, 10, 15, 0.0)");

    return {
      label: c.toUpperCase(),
      data: days.map(d => (trend.find(t => t.day === d && t.channel === c) || {}).c || 0),
      borderColor: colors[c] || "#9ca3af",
      backgroundColor: gradient,
      fill: true,
      tension: 0.4,
      borderWidth: 2,
      pointBackgroundColor: colors[c] || "#9ca3af",
      pointBorderColor: "rgba(255, 255, 255, 0.1)",
      pointHoverRadius: 6,
      pointRadius: 3
    };
  });

  trendChartInstance = new Chart(trendCanvas, {
    type: "line",
    data: {
      labels: days.map(d => {
        const dateObj = new Date(d);
        return isNaN(dateObj.getTime()) ? d : dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      }),
      datasets: datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 0,
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            color: "#9ca3af",
            font: { family: "Inter", size: window.innerWidth < 550 ? 9 : 11, weight: 500 },
            boxWidth: 8,
            boxHeight: 8,
            usePointStyle: true,
            pointStyle: 'circle'
          }
        },
        tooltip: {
          backgroundColor: "#11131e",
          borderColor: "rgba(255, 255, 255, 0.08)",
          borderWidth: 1,
          titleColor: "#f3f4f6",
          bodyColor: "#9ca3af",
          titleFont: { family: "Inter", weight: 600, size: window.innerWidth < 550 ? 10 : 12 },
          bodyFont: { family: "Inter", size: window.innerWidth < 550 ? 9 : 11 },
          padding: 10,
          cornerRadius: 8
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.03)", drawBorder: false },
          ticks: { 
            color: "#9ca3af", 
            font: { family: "Inter", size: window.innerWidth < 550 ? 8 : 10 },
            maxRotation: 45,
            minRotation: 0
          }
        },
        y: {
          grid: { color: "rgba(255, 255, 255, 0.03)", drawBorder: false },
          ticks: { 
            color: "#9ca3af", 
            font: { family: "Inter", size: window.innerWidth < 550 ? 8 : 10 }, 
            precision: 0 
          }
        }
      }
    },
  });
}

export function renderVerdictChart(verdicts) {
  const verdictCanvas = document.getElementById("verdict-chart");
  if (!verdictCanvas) return;

  if (verdictChartInstance) {
    verdictChartInstance.destroy();
  }

  const verdictKeys = Object.keys(verdicts);
  const verdictVals = Object.values(verdicts);

  const verdictColors = {
    likely_true: "#10b981",
    likely_authentic: "#10b981",
    inconclusive: "#f59e0b",
    flagged: "#ef4444",
    likely_ai_generated: "#ef4444",
    likely_edited: "#ef4444"
  };

  const bgColors = verdictKeys.map(k => verdictColors[k] || "#4f46e5");

  verdictChartInstance = new Chart(verdictCanvas, {
    type: "doughnut",
    data: {
      labels: verdictKeys.map(k => k.replace(/_/g, " ").toUpperCase()),
      datasets: [{
        data: verdictVals,
        backgroundColor: bgColors,
        borderWidth: 0,
        hoverOffset: 4
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 0,
      cutout: "76%",
      plugins: {
        legend: {
          display: true,
          position: window.innerWidth < 650 ? 'bottom' : 'right',
          labels: {
            color: "#9ca3af",
            font: { family: "Inter", size: window.innerWidth < 550 ? 9 : 10, weight: 500 },
            boxWidth: 8,
            boxHeight: 8,
            usePointStyle: true,
            pointStyle: 'circle',
            padding: window.innerWidth < 550 ? 6 : 10
          }
        },
        tooltip: {
          backgroundColor: "#11131e",
          borderColor: "rgba(255, 255, 255, 0.08)",
          borderWidth: 1,
          titleColor: "#f3f4f6",
          bodyColor: "#9ca3af",
          padding: 10,
          cornerRadius: 8
        }
      },
    },
    plugins: [centerTextPlugin]
  });
}
