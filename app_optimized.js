// グローバル変数
let map;
let heatLayer;
let bearData = {};  // 生データ: bearData[day] = [[lat, lng, energy, age_class, gender, repro_status], ...]
let stats = {};
let currentDay = 1;
let isPlaying = false;
let playInterval;

// フィルタ状態
const filters = {
    ageClass: new Set(['Cu', 'Yr', 'Su', 'Ad']),
    gender: new Set(['F', 'M']),
    repro: new Set(['LACTATING', 'MATED', 'NORMAL']),
    energyMin: -Infinity,
    energyMax: Infinity
};

// 日付計算関数
function formatDate(day) {
    const date = new Date(2026, 0, 1);
    date.setDate(date.getDate() + day - 1);
    return `${date.getFullYear()}年${date.getMonth() + 1}月${date.getDate()}日`;
}

// JSONデータ読み込み
async function loadData() {
    try {
        // 1. URLからパラメータを取得 (例: ?data=akita)
        const urlParams = new URLSearchParams(window.location.search);
        const dataPrefix = urlParams.get('data') || ''; // パラメータがない場合は空文字
        
        // 2. 読み込むファイル名を決定
        // パラメータがあれば 'akita_stats.json'、なければ 'stats.json' を読み込む設計
        const statsFile = dataPrefix ? `${dataPrefix}_stats.json` : 'stats.json';
        const dataFile = dataPrefix ? `${dataPrefix}_bear_data.json` : 'bear_data.json';

        console.log(`Loading: ${statsFile} and ${dataFile}`);

        const statsResponse = await fetch(statsFile);
        stats = await statsResponse.json();

        document.getElementById('loading').querySelector('div:last-child').textContent =
            'データ読み込み中...';

        const dataResponse = await fetch(dataFile);
        bearData = await dataResponse.json();

        // (以下、既存の処理と同じ)
        document.getElementById('totalCount').textContent = stats.total_records.toLocaleString();

        if (stats.min_energy !== undefined) {
            document.getElementById('energyRangeInfo').textContent =
                `${stats.min_energy.toFixed(1)} 〜 ${stats.max_energy.toFixed(1)}`;
        }

        return true;
    } catch (error) {
        console.error('データ読み込みエラー:', error);
        alert('指定された地域のJSONファイルが見つかりません。');
        return false;
    }
}

// 地図初期化
function initMap() {
    map = L.map('map');

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    heatLayer = L.heatLayer([], {
        radius: 25,
        blur: 35,
        maxZoom: 17,
        max: 1.0,
        minOpacity: 0.7,
        gradient: {
            0.0: 'blue', 0.3: 'cyan', 0.5: 'lime', 0.7: 'yellow', 1.0: 'red'
        }
    }).addTo(map);

    const bounds = [
        [stats.min_lat, stats.min_lng],
        [stats.max_lat, stats.max_lng]
    ];
    map.fitBounds(bounds);
}

// フィルタリング適用してヒートマップ用座標を返す
function getFilteredData(day) {
    const raw = bearData[day.toString()] || [];
    const filtered = [];

    for (let i = 0; i < raw.length; i++) {
        const r = raw[i];
        // r = [lat, lng, energy, age_class, gender, repro_status]
        if (!filters.ageClass.has(r[3])) continue;
        if (!filters.gender.has(r[4])) continue;
        if (!filters.repro.has(r[5])) continue;
        if (r[2] < filters.energyMin || r[2] > filters.energyMax) continue;
        filtered.push([r[0], r[1]]);
    }
    return filtered;
}

// ヒートマップ更新
function updateHeatmap(day) {
    currentDay = day;

    const data = getFilteredData(day);
    heatLayer.setLatLngs(data);

    document.getElementById('currentDay').textContent = day;
    document.getElementById('dateDisplay').textContent = formatDate(day);
    document.getElementById('daySlider').value = day;
    document.getElementById('displayCount').textContent = data.length.toLocaleString();
}

// 再生制御
function play() {
    if (isPlaying) return;
    isPlaying = true;
    document.getElementById('playBtn').style.display = 'none';
    document.getElementById('stopBtn').style.display = 'block';

    const speed = parseInt(document.getElementById('speedSlider').value);
    playInterval = setInterval(() => {
        currentDay++;
        if (currentDay > 365) currentDay = 1;
        updateHeatmap(currentDay);
    }, speed);
}

function stop() {
    isPlaying = false;
    clearInterval(playInterval);
    document.getElementById('playBtn').style.display = 'block';
    document.getElementById('stopBtn').style.display = 'none';
}

// フィルタボタンの初期化
function setupFilterButtons() {
    // トグルボタンの共通処理
    function setupToggleGroup(containerId, filterSet) {
        const container = document.getElementById(containerId);
        container.querySelectorAll('.filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const val = btn.dataset.value;
                if (filterSet.has(val)) {
                    filterSet.delete(val);
                    btn.classList.add('inactive');
                } else {
                    filterSet.add(val);
                    btn.classList.remove('inactive');
                }
                updateHeatmap(currentDay);
            });
        });
    }

    setupToggleGroup('ageClassFilter', filters.ageClass);
    setupToggleGroup('genderFilter', filters.gender);
    setupToggleGroup('reproFilter', filters.repro);

    // エネルギー範囲フィルタ
    document.getElementById('energyApply').addEventListener('click', () => {
        const minVal = document.getElementById('energyMin').value;
        const maxVal = document.getElementById('energyMax').value;
        filters.energyMin = minVal !== '' ? parseFloat(minVal) : -Infinity;
        filters.energyMax = maxVal !== '' ? parseFloat(maxVal) : Infinity;
        updateHeatmap(currentDay);
    });

    // Enterキーでもエネルギーフィルタ適用
    ['energyMin', 'energyMax'].forEach(id => {
        document.getElementById(id).addEventListener('keydown', (e) => {
            if (e.key === 'Enter') document.getElementById('energyApply').click();
        });
    });
}

// イベントリスナー設定
function setupEventListeners() {
    document.getElementById('daySlider').addEventListener('input', (e) => {
        if (isPlaying) stop();
        updateHeatmap(parseInt(e.target.value));
    });

    document.getElementById('playBtn').addEventListener('click', play);
    document.getElementById('stopBtn').addEventListener('click', stop);

    document.getElementById('speedSlider').addEventListener('input', (e) => {
        document.getElementById('speedDisplay').textContent = e.target.value;
        if (isPlaying) { stop(); play(); }
    });

    // 透過度調整
    document.getElementById('opacitySlider').addEventListener('input', (e) => {
        const opacity = parseInt(e.target.value) / 100;
        document.getElementById('opacityDisplay').textContent = e.target.value;
        heatLayer.setOptions({ minOpacity: opacity });
        updateHeatmap(currentDay);
    });

    // 半径調整
    document.getElementById('radiusSlider').addEventListener('input', (e) => {
        const radius = parseInt(e.target.value);
        document.getElementById('radiusDisplay').textContent = e.target.value;
        heatLayer.setOptions({ radius: radius, blur: radius * 1.4 });
        updateHeatmap(currentDay);
    });

    // キーボードショートカット
    document.addEventListener('keydown', (e) => {
        // 入力欄にフォーカスがある場合はスキップ
        if (e.target.tagName === 'INPUT') return;

        if (e.code === 'Space') {
            e.preventDefault();
            isPlaying ? stop() : play();
        } else if (e.code === 'ArrowLeft') {
            e.preventDefault();
            if (isPlaying) stop();
            updateHeatmap(Math.max(1, currentDay - 1));
        } else if (e.code === 'ArrowRight') {
            e.preventDefault();
            if (isPlaying) stop();
            updateHeatmap(Math.min(365, currentDay + 1));
        }
    });

    setupFilterButtons();
}

// 初期化
async function init() {
    const success = await loadData();
    if (success) {
        document.getElementById('loading').style.display = 'none';
        initMap();
        setupEventListeners();
        updateHeatmap(1);
    }
}

init();
