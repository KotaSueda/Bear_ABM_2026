// 経路レイヤー管理
let routeLayer = null;
let routeData = null;
let routeOpacity = 0.6;
let routeWeight = 2;

// bear_idごとに色を生成（HSLで均等に分散）
const bearColorCache = {};
function getBearColor(bearId) {
    if (bearColorCache[bearId]) return bearColorCache[bearId];
    // bear_idからハッシュ的に色相を決定
    const hue = (bearId * 137.508) % 360;
    const color = `hsl(${Math.round(hue)}, 70%, 50%)`;
    bearColorCache[bearId] = color;
    return color;
}

// 経路データを読み込み
async function loadRouteData() {
    if (routeData) return routeData;

    const btn = document.getElementById('loadRouteBtn');
    btn.textContent = '読み込み中...';
    btn.disabled = true;

    try {
        // 1. URLから 'area' パラメータを取得
        const urlParams = new URLSearchParams(window.location.search);
        const area = urlParams.get('area'); // 例: 'aomori'

        // 2. 読み込むファイル名を決定
        const baseFileName = 'result_ensemble_tohoku_0_12002_G_epsg2450_segments.geojson';
        const fileName = area ? `${area}_${baseFileName}` : baseFileName;

        console.log("読み込むGeoJSONファイル:", fileName);

        // 3. fetchで読み込み、ファイルが存在するかチェック
        const response = await fetch(fileName);
        if (!response.ok) {
            throw new Error(`${fileName} が見つかりません (Status: ${response.status})`);
        }
        
        routeData = await response.json();

        // 統計情報を更新
        const bearIds = new Set();
        routeData.features.forEach(f => {
            const bid = f.properties.bear_id;
            if (bid !== undefined) bearIds.add(bid);
        });
        document.getElementById('routeCount').textContent = routeData.features.length.toLocaleString();
        document.getElementById('bearCount').textContent = bearIds.size.toLocaleString();

        btn.textContent = '📍 経路を表示';
        btn.disabled = false;
        return routeData;

    } catch (error) {
        console.error('GeoJSON読み込みエラー:', error);
        btn.textContent = '📍 経路データを読み込む';
        btn.disabled = false;
        
        // ファイルが見つからなかった時のメッセージ
        alert(`経路データの読み込みに失敗しました。\n対象のファイルがGitHubにアップロードされているか確認してください。`);
        return null;
    }
}

// 経路レイヤーを地図に追加
function showRoutes() {
    if (!routeData || !map) return;

    // 既存レイヤーを削除
    clearRoutes();

    routeLayer = L.geoJSON(routeData, {
        style: function(feature) {
            const bearId = feature.properties.bear_id;
            return {
                color: getBearColor(bearId),
                weight: routeWeight,
                opacity: routeOpacity
            };
        }
    }).addTo(map);
}

// 経路レイヤーを削除
function clearRoutes() {
    if (routeLayer) {
        map.removeLayer(routeLayer);
        routeLayer = null;
    }
}

// 経路のスタイルを更新
function updateRouteStyle() {
    if (!routeLayer) return;
    routeLayer.setStyle({
        weight: routeWeight,
        opacity: routeOpacity
    });
}

// タブ切り替え処理
function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // タブボタンのアクティブ状態を切り替え
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            // タブコンテンツの表示を切り替え
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const tabId = 'tab-' + btn.dataset.tab;
            document.getElementById(tabId).classList.add('active');
        });
    });
}

// 経路タブのイベントリスナー
function setupRouteControls() {
    // 経路読み込み・表示ボタン
    document.getElementById('loadRouteBtn').addEventListener('click', async () => {
        const data = await loadRouteData();
        if (data) showRoutes();
    });

    // 経路非表示ボタン
    document.getElementById('clearRouteBtn').addEventListener('click', clearRoutes);

    // 透過度スライダー
    document.getElementById('routeOpacitySlider').addEventListener('input', (e) => {
        routeOpacity = parseInt(e.target.value) / 100;
        document.getElementById('routeOpacityDisplay').textContent = e.target.value;
        updateRouteStyle();
    });

    // 線の太さスライダー
    document.getElementById('routeWeightSlider').addEventListener('input', (e) => {
        routeWeight = parseFloat(e.target.value);
        document.getElementById('routeWeightDisplay').textContent = e.target.value;
        updateRouteStyle();
    });
}

// 初期化（DOMContentLoaded後に実行）
document.addEventListener('DOMContentLoaded', () => {
    setupTabs();
    setupRouteControls();
});
