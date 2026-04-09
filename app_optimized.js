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
    repro: new Set(['LACTATING', 'SINGLE']),  // SINGLEはMATED+NORMALをまとめたもの
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
        // 1. URLから 'area' パラメータを取得
        const urlParams = new URLSearchParams(window.location.search);
        const area = urlParams.get('area'); // 例: 'miyagi' や 'akita'

        // 2. 読み込むファイル名を決定（パラメータがなければデフォルトを使用）
        const statsFile = area ? `${area}_stats.json` : 'stats.json';
        const dataFile = area ? `${area}_bear_data.json` : 'bear_data.json';

        console.log("現在読み込もうとしているファイル:", statsFile, dataFile);

        // 3. stats.json の読み込みとエラーチェック
        const statsResponse = await fetch(statsFile);
        if (!statsResponse.ok) {
            throw new Error(`${statsFile} が見つかりません (Status: ${statsResponse.status})`);
        }
        stats = await statsResponse.json();

        // 画面のローディング文字を更新
        document.getElementById('loading').querySelector('div:last-child').textContent =
            'データ読み込み中...';

        // 4. bear_data.json の読み込みとエラーチェック
        const dataResponse = await fetch(dataFile);
        if (!dataResponse.ok) {
            throw new Error(`${dataFile} が見つかりません (Status: ${dataResponse.status})`);
        }
        bearData = await dataResponse.json();

        // 5. 画面への反映処理
        document.getElementById('totalCount').textContent = stats.total_records.toLocaleString();

        // エネルギー範囲を表示
        if (stats.min_energy !== undefined) {
            document.getElementById('energyRangeInfo').textContent =
                `${stats.min_energy.toFixed(1)} 〜 ${stats.max_energy.toFixed(1)}`;
        }

        return true;

    } catch (error) {
        // エラー時の処理
        console.error('データ読み込みエラー:', error);
        
        // 元のメッセージと、地域ファイル欠品時のメッセージを組み合わせたアラート
        alert(`JSONファイルの読み込みに失敗しました。\n・URLの地域パラメータが正しいか\n・先に preprocess_with_projection.py などのデータ生成スクリプトを実行したか\nを確認してください。`);
        
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
        // 繁殖状態: LACTATINGは「子連れ」、MATED/NORMALは「単独」
        const reproGroup = r[5] === 'LACTATING' ? 'LACTATING' : 'SINGLE';
        if (!filters.repro.has(reproGroup)) continue;
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

    // スライダー値が大きいほど速い（間隔が短い）
    const sliderVal = parseInt(document.getElementById('speedSlider').value);
    const interval = 2100 - sliderVal; // 100~2000 → 2000~100ms
    playInterval = setInterval(() => {
        currentDay++;
        if (currentDay > 212) currentDay = 91;
        updateHeatmap(currentDay);
    }, interval);
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

    // エネルギー範囲スライダー
    const energyMinSlider = document.getElementById('energyMinSlider');
    const energyMaxSlider = document.getElementById('energyMaxSlider');
    const energyHighlight = document.getElementById('energyHighlight');

    // ハイライトバーの位置を更新
    function updateEnergyHighlight() {
        const min = parseFloat(energyMinSlider.min);
        const max = parseFloat(energyMinSlider.max);
        const range = max - min;
        if (range <= 0) return;
        const leftPct = ((parseFloat(energyMinSlider.value) - min) / range) * 100;
        const rightPct = ((parseFloat(energyMaxSlider.value) - min) / range) * 100;
        energyHighlight.style.left = leftPct + '%';
        energyHighlight.style.width = (rightPct - leftPct) + '%';
    }

    // stats読み込み後にスライダーの範囲を設定
    if (stats.min_energy !== undefined) {
        const eMin = Math.floor(stats.min_energy);
        const eMax = Math.ceil(stats.max_energy);
        energyMinSlider.min = eMin;
        energyMinSlider.max = eMax;
        energyMinSlider.value = eMin;
        energyMaxSlider.min = eMin;
        energyMaxSlider.max = eMax;
        energyMaxSlider.value = eMax;
        document.getElementById('energyMinDisplay').textContent = eMin;
        document.getElementById('energyMaxDisplay').textContent = eMax;
        filters.energyMin = eMin;
        filters.energyMax = eMax;
        updateEnergyHighlight();
    }

    energyMinSlider.addEventListener('input', (e) => {
        let val = parseFloat(e.target.value);
        if (val > parseFloat(energyMaxSlider.value)) {
            val = parseFloat(energyMaxSlider.value);
            e.target.value = val;
        }
        filters.energyMin = val;
        document.getElementById('energyMinDisplay').textContent = val;
        updateEnergyHighlight();
        updateHeatmap(currentDay);
    });

    energyMaxSlider.addEventListener('input', (e) => {
        let val = parseFloat(e.target.value);
        if (val < parseFloat(energyMinSlider.value)) {
            val = parseFloat(energyMinSlider.value);
            e.target.value = val;
        }
        filters.energyMax = val;
        document.getElementById('energyMaxDisplay').textContent = val;
        updateEnergyHighlight();
        updateHeatmap(currentDay);
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
        const sliderVal = parseInt(e.target.value);
        const interval = 2100 - sliderVal;
        document.getElementById('speedDisplay').textContent = interval;
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
            updateHeatmap(Math.max(91, currentDay - 1));
        } else if (e.code === 'ArrowRight') {
            e.preventDefault();
            if (isPlaying) stop();
            updateHeatmap(Math.min(212, currentDay + 1));
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
        updateHeatmap(91);
    }
}

init();
