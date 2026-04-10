// 統計グラフの描画
async function loadAndDrawCharts() {
    try {
        // 1. URLからパラメータを取得
        const urlParams = new URLSearchParams(window.location.search);
        const area = urlParams.get('area'); // 例: 'aomori'
        
        // 2. 変数の接頭辞を作成（areaがあれば 'aomori_'、なければ空文字）
        const prefix = area ? `${area}_` : '';

        const response = await fetch('metrics_ensemble_tohoku_0_12002_Great.json');
        const data = await response.json();

        // 3. 各描画関数にプレフィックスを渡す
        drawSightingChart(data, prefix);
        drawKillChart(data, prefix);
        drawAgeDistChart(data, prefix);
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
function drawSightingChart(data, prefix) {
    // 例: aomori_sighting_trend などのキー名を作成してデータを取得
    const key = `${prefix}sighting_trend`;
    const values = data.slice(0, 12).map(d => d[key]);

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
function drawKillChart(data, prefix) {
    const key = `${prefix}kill_trend`;
    const values = data.slice(0, 12).map(d => d[key]);

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
