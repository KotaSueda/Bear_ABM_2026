// 統計グラフの描画
async function loadAndDrawCharts() {
    try {
        const response = await fetch('metrics_ensemble_tohoku_0_12002_Great.json');
        const data = await response.json();

        drawSightingChart(data);
        drawKillChart(data);
        drawAgeDistChart(data);
    } catch (error) {
        console.error('統計JSONの読み込みエラー:', error);
    }
}

// 月別ラベル
const monthLabels = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];

// ツールチップ・ホバー無効の共通設定
const noInteraction = {
    tooltip: { enabled: false },
    legend: { display: false }
};

// 月別市街地出没トレンド
function drawSightingChart(data) {
    const values = data.slice(0, 12).map(d => d.sighting_trend);

    new Chart(document.getElementById('sightingChart'), {
        type: 'bar',
        data: {
            labels: monthLabels,
            datasets: [{
                data: values,
                backgroundColor: 'rgba(231, 76, 60, 0.7)',
                borderColor: 'rgba(231, 76, 60, 1)',
                borderWidth: 1,
                hoverBackgroundColor: 'rgba(231, 76, 60, 0.7)',
                hoverBorderColor: 'rgba(231, 76, 60, 1)'
            }]
        },
        options: {
            responsive: true,
            events: [],
            plugins: noInteraction,
            scales: {
                y: { beginAtZero: true, ticks: { display: false }, title: { display: false } },
                x: { title: { display: true, text: '月' } }
            }
        }
    });
}

// 月別捕殺数トレンド
function drawKillChart(data) {
    const values = data.slice(0, 12).map(d => d.kill_trend);

    new Chart(document.getElementById('killChart'), {
        type: 'bar',
        data: {
            labels: monthLabels,
            datasets: [{
                data: values,
                backgroundColor: 'rgba(52, 152, 219, 0.7)',
                borderColor: 'rgba(52, 152, 219, 1)',
                borderWidth: 1,
                hoverBackgroundColor: 'rgba(52, 152, 219, 0.7)',
                hoverBorderColor: 'rgba(52, 152, 219, 1)'
            }]
        },
        options: {
            responsive: true,
            events: [],
            plugins: noInteraction,
            scales: {
                y: { beginAtZero: true, ticks: { display: false }, title: { display: false } },
                x: { title: { display: true, text: '月' } }
            }
        }
    });
}

// 捕殺年齢分布
function drawAgeDistChart(data) {
    const ageLabels = Array.from({length: 21}, (_, i) => `${i}歳`);
    const values = data.map(d => d.kill_age_distribution);

    new Chart(document.getElementById('ageDistChart'), {
        type: 'bar',
        data: {
            labels: ageLabels,
            datasets: [{
                data: values,
                backgroundColor: 'rgba(46, 204, 113, 0.7)',
                borderColor: 'rgba(46, 204, 113, 1)',
                borderWidth: 1,
                hoverBackgroundColor: 'rgba(46, 204, 113, 0.7)',
                hoverBorderColor: 'rgba(46, 204, 113, 1)'
            }]
        },
        options: {
            responsive: true,
            events: [],
            plugins: noInteraction,
            scales: {
                y: { beginAtZero: true, title: { display: true, text: '割合' } },
                x: { title: { display: true, text: '年齢' } }
            }
        }
    });
}

// ページ読み込み時に実行
loadAndDrawCharts();
