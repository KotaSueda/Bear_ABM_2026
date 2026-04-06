import numpy as np
import pandas as pd
import os
import math
from dataclasses import dataclass
from multiprocessing import Pool
import datetime

# ==========================================
# [0] シミュレーション基本シナリオ設定（手動変更用）
# ==========================================
# INITIAL_POP_SIZE = 1504            # 初期個体数（ファイル名にも連動）
# MAST_LEVEL = "Great"         # 今年の豊凶ランク ("Great", "Average", "Poor", "ExtremelyPoor")

# ==========================================
# [1] 固定定数（推定対象外）
# ==========================================

# 空間メッシュサイズとシミュレーション期間
X_SIZE, Y_SIZE = 877, 761  # env[:, y, x]
NUM_ENSEMBLE = 1
START_DAY, END_DAY = 1, 365

# 行動モードのコード
HIBERNATION, RESTING, MOVING, FORAGING = -1, 0, 1, 2

# システム設定
OUTPUT_BUFFER_DAYS = 30

# 初期エネルギー
INITIAL_ENERGY_MEAN = 60.0  # 初期エネルギーの平均値
INITIAL_ENERGY_STD = 10.0   # 初期エネルギーの標準偏差
INITIAL_ENERGY_MIN = 40.0   # 初期エネルギーの下限（即死防止用）
INITIAL_ENERGY_MAX = 80.0  # 初期エネルギーの上限

# クマのエネルギー増減・死亡判定に関する固定定数
# [使用関数: update_energy_hibernation, update_energy]
HIBERNATION_ENERGY_COST = 0.25   # 冬眠中の1ステップあたりのベースエネルギー消費量
RESTING_ENERGY_COST = 1.0        # 休息時の消費エネルギー
MOVING_BASE_COST = 1.0           # 移動時の基本消費エネルギー
MOVING_DIST_MULT = 0.1           # 移動距離(パッチ数)にかかる消費エネルギー係数
FORAGING_ENERGY_COST = 2.5       # 採餌時の消費エネルギー
# LACTATING_COST_MULT = 1.2        # 授乳中のメスにかかる消費エネルギー倍率
STARVATION_THRESHOLD = 10.0      # 餓死リスクが発生し始めるエネルギー閾値
MIN_ENERGY = 0.0                 # 個体エネルギーの下限（これ以下にはならない）
MAX_ENERGY = 100.0               # 個体エネルギーの上限（これ以上は太れない）

# クマの冬眠解除（春の目覚め）に関する固定定数
# [使用関数: check_wakeup]
WAKEUP_MIN_DAY = 60         # 冬眠解除が許可される最短日数（3月上旬）
WAKEUP_MAX_DAY = 180        # 冬眠解除が許可される最長日数 ※安全策として設定
WAKEUP_BASE_TEMP = 3.0      # 目覚めを促す基準気温

# クマの冬眠開始（秋の就眠）に関する固定定数
# [使用関数: check_hibernation]
HIBERNATION_MIN_ENERGY = 50.0    # 冬眠を乗り切るための最低エネルギー
HIBERNATION_START_DAY = 290      # 冬眠が許可される最短日数（10/25付近）
HIBERNATION_LANDUSE = 500        # 冬眠可能な植生コード（奥山の広葉樹林など）
HIBERNATION_BASE_TEMP = 8.0      # 冬眠を促す基準気温
HIBERNATION_ENERGY_DROP_RATE = 20.0  # 冬眠基準の引き下げ

# クマの行動決定（モード選択）に関する固定定数
# [使用関数: decide_action]
# 1. 基本となる行動確率（平常時）
BASE_P_REST = 0.55  # 0.592
BASE_P_MOVE = 0.2  # 0.275
BASE_P_FORAGE = 0.25  # 0.133
# 冬眠明けの不活発状態
POST_WAKEUP_DAYS = 20            # 起床直後の不活発な期間（日数）
POST_WAKEUP_MOVE_PENALTY = 0.10  # その期間の移動確率の低下幅（ペナルティ）
# 2. 気象条件によるブースト（休息の増加）
HOT_TEMP_THRESHOLD = 28.0      # 猛暑日（これ以上で休息増）
HEAVY_RAIN_THRESHOLD = 20.0    # 大雨（これ以上で休息増）
WEATHER_REST_BOOST = 0.2       # 悪天候時の休息確率ブースト
# 3. 季節・ライフステージによるブースト
MATING_START_DAY = 160         # 交尾期開始（6月上旬）
MATING_END_DAY = 220           # 交尾期終了（8月上旬）
MATING_MOVE_BOOST = 0.15        # 成獣オスの交尾期移動ブースト
DISPERSAL_MOVE_BOOST = 0.1    # 2歳（独立直後）の分散移動ブースト
# 4. 秋の飽食期（Hyperphagia）による採餌ブースト
FALL_SEP_START = 244           # 9月開始
FALL_OCT_START = 274           # 10月開始
FALL_NOV_START = 304           # 11月開始
FALL_NOV_END = 334             # 11月末
# FALL_SEP_BOOST = 0.1
# FALL_OCT_BOOST = 0.2
# FALL_NOV_BOOST = 0.15
MAX_FALL_BOOST = 0.40
# 5. 飢餓時のブースト（※文献値なし・仮説に基づく設定）
HUNGER_THRESHOLD = 20.0        # 焦り始めるエネルギー閾値
CRITICAL_STARVATION_THRESHOLD = 5.0  # 極限の飢餓状態（エネルギー5以下）を定義
HUNGER_FORAGE_BOOST = 0.2      # 飢餓時の採餌確率ブースト
HUNGER_MOVE_BOOST = 0.1        # 飢餓時の移動確率ブースト
EXTREME_STARVE_FORAGE_BOOST = 0.1  # エネルギー5以下の追加採餌ブースト
EXTREME_STARVE_MOVE_BOOST = 0.1    # エネルギー5以下の追加移動ブースト

# クマの空間探索（探索半径）に関する固定定数
# [使用関数: get_search_radius]
BASE_SEARCH_RADIUS = 18           # 基本の探索半径（メッシュ数）
DISPERSAL_RADIUS_BONUS = 10       # 独立直後の若グマ（Yr, Su）の探索ボーナス
MATING_RADIUS_BONUS = 10          # 成獣オスの交尾期（徘徊）の探索ボーナス
MAX_HUNGER_RADIUS_BONUS = 15      # 飢餓による探索ボーナスの上限値

# [使用関数: decide_destination]
inertia_weight = 0.2
# 絶対的な基準値（例：周囲9マスの豊作時ゲイン想定）
GLOBAL_MAX_GAIN = 10.0

# 空間認識（土地利用判定）に関する固定定数
# [使用関数: update_stay_urban_counts, update_total_experience]
URBAN_LANDUSE_CODES = {100, 200, 700, 901, 902, 1000}  

# クマの人里忌避・学習に関する固定定数
# [使用関数: calculate_avoidance_score]
FEAR_DROP_ENERGY_THRESHOLD = 50.0  # 飢餓によって恐怖心が薄れ始めるエネルギー値
MIN_HUNGER_FEAR_FACTOR = 0.05       # 極限飢餓時の恐怖心の下限（元の5%までは残る）
HUNGER_FEAR_RATIO = 2        # 飢餓による恐怖心減少の開始タイミング（エネルギーがこの割合以下になると減少開始）
MIN_EXPERIENCE_FEAR_FACTOR = 0.05   # 完全なアーバンベアの恐怖心の下限（元の5%までは残る）
GLOBAL_POP_MAX = 1.0              # 最大値232
GLOBAL_LOG_POP_MAX = math.log1p(GLOBAL_POP_MAX)  # あらかじめ対数を計算しておく（232のとき約5.45）

# 空間移動（障壁・渡河）に関する固定定数
# [使用関数: apply_barrier_on_path]
RIVER_LANDUSE_CODE = 1100       # 川（障壁）として判定する植生コード
RIVER_BARRIER_PROB = 0.5        # 川セル1マスにつき、渡るのを諦めて引き返す（阻まれる）確率


# 環境・資源（マスティング）に関する固定定数
# [使用関数: World.__init__]
MAST_LEVEL_FACTORS = {
    "Great": 1.0,           # 豊作
    "Average": 0.8,         # 並作
    "Poor": 0.6,            # 凶作
    "ExtremelyPoor": 0.4  # 大凶作
}

# カレンダー（季節の定義）に関する固定定数
# [使用関数: get_season_name]
SPRING_START_DAY = 91
SPRING_END_DAY = 151
SUMMER_START_DAY = 182
SUMMER_END_DAY = 243
# 秋の開始日は既に FALL_SEP_START (244) として定義済み 
AUTUMN_END_DAY = 365

# 環境・資源（マスティング・ゲイン）に関する固定定数
# [使用関数: calculate_patch_gain]
SEASON_PEAK_MULTIPLIER = 2.0    # 植生が「旬（指定された季節）」の時のゲイン倍率

# 空間探索（採餌）に関する固定定数
# [使用関数: get_area_gain]
FORAGING_NEIGHBORHOOD_RADIUS = 1  # 採餌時に周囲何マス分を面として合算するか（1なら3x3の9パッチ）

# --- 個体群初期化（デモグラフィー）に関する固定定数 ---
# [使用関数: initialize_all_bears]
SPAWN_LANDUSE_CODE = 500          # 初期配置される植生コード（奥山・森林など）
# 1. 構成比率
POP_RATIO_ADULT_FEMALE = 0.258    # 成獣メスの割合
POP_RATIO_ADULT_MALE = 0.258      # 成獣オスの割合
POP_RATIO_SUBADULT = 0.190        # 若獣の割合
# 2. 繁殖・家族構成の確率
PROB_MOTHER_CUBS = 0.392          # メスが当歳子(0歳)を連れている確率
PROB_MOTHER_YEARLINGS = 0.278     # メスが1歳子(1歳)を連れている確率 (元コード: 0.670 - 0.392)
PROB_MOTHER_SINGLE = 0.330        # メスが単独行動の確率 (元コード: 1.0 - 0.670)
LITTER_SIZE_CHOICES = [1, 2]      # 同腹子数（産子数）の選択肢
LITTER_SIZE_PROBS = [0.3, 0.7]    # 1頭連れが30%、2頭連れが70%
# 3. 年齢範囲（※Numpyのrandintは上限未満になるため、実質の最大年齢を定義）
AGE_MIN_ADULT = 4
AGE_MAX_ADULT = 20                
AGE_MIN_SUBADULT = 2
AGE_MAX_SUBADULT = 3

# 0歳〜20歳までの初期配置確率（老化カーブ適用版）
# 安定齢分布（0歳:17.1%, 1歳:12.5%, 2-3歳:20.7%, 4歳以上:49.7%）に準拠
INITIAL_AGE_DISTRIBUTION = [
    # --- 子グマ・若獣（親離れと分散による自然減） ---
    0.1710,  #  0歳 (17.1%)
    0.1250,  #  1歳 (12.5%)
    0.1150,  #  2歳 (11.5%) - ここから親離れ
    0.0920,  #  3歳 (9.2%) 
    
    # --- 成獣・プライム世代（生存率90%で安定） ---
    # ここから下の合計がピッタリ 49.7% になります
    0.0664,  #  4歳 (6.6%)
    0.0598,  #  5歳 (6.0%)
    0.0538,  #  6歳 (5.4%)
    0.0484,  #  7歳 (4.8%)
    0.0436,  #  8歳 (4.4%)
    0.0392,  #  9歳 (3.9%)
    0.0353,  # 10歳 (3.5%)
    0.0318,  # 11歳 (3.2%)
    0.0286,  # 12歳 (2.9%)
    
    # --- 高齢・老化（生存率が年々低下し、寿命へ向かう） ---
    0.0257,  # 13歳 (2.6%) - 生存率85%へ低下
    0.0219,  # 14歳 (2.2%) - 生存率80%へ低下
    0.0175,  # 15歳 (1.8%) - 生存率70%へ低下
    0.0123,  # 16歳 (1.2%) - 生存率60%へ低下
    0.0073,  # 17歳 (0.7%) - 生存率50%へ低下
    0.0037,  # 18歳 (0.4%) - 生存率40%へ低下
    0.0015,  # 19歳 (0.2%) - 生存率30%へ低下
    0.0002   # 20歳 (0.02%) - 寿命（これ以上は生きられない）
]

# --- 人為的死亡（捕殺・駆除）に関する固定定数 ---
# [使用関数: calculate_human_caused_mortality]
# 土地利用ごとの基本ハザード（罠の設置密度や発見されやすさの相対比）
LANDUSE_HAZARD_WEIGHTS = {
    700: 0.5,   # 建物用地
    901: 0.3,   # 道路
    902: 0.3,   # 鉄道
    1000: 0.2   # その他の用地
}
DEFAULT_HAZARD_WEIGHT = 0.5    # 上記以外のアーバンパッチのデフォルト危険度
BASE_TRAP_RISK = 0.01          # 人口0でも存在する基本の捕獲リスク（1%）
MAX_HUMAN_KILL_PROB = 0.1      # 1日あたりの捕殺確率の最大値（10%でカンスト）

# クマのライフサイクル（親離れ）に関する固定定数
# [使用関数: process_incremental_independence]
INDEPENDENCE_AGE = 1              # 親離れ（独立）する年齢
DAILY_INDEPENDENCE_PROB = 0.10    # 解禁日以降、1日あたりに独立する確率（0.1なら約1ヶ月でほぼ全員独立）

# クマのライフステージ・加齢に関する固定定数
# [使用関数: process_end_of_year, Bear.__init__ (必要に応じて)]
AGE_CLASS_YEARLING = 1      # 1歳（Yr: Yearling）
AGE_CLASS_SUBADULT = 2      # 2歳〜（Su: Subadult, 独立）
AGE_CLASS_ADULT = 4         # 4歳〜（Ad: Adult, 繁殖可能）
MAX_LIFESPAN = 20           # 最大寿命（これを超えると老衰死）

# クマのライフサイクル（孤児）に関する固定定数
# [使用関数: process_orphans]
ORPHAN_SURVIVAL_AGE = 1     # 母親死亡時に生き残れる（強制独立する）最低年齢。これ未満は死亡。

# 交尾に関する固定定数
# [使用関数: process_mating]
MATING_SUCCESS_PROB = 0.90    # 同一パッチにオスとメスが揃った場合の交尾成功率

# 全行動のエネルギー消費にかかるマスター係数 α
ENERGY_COST_ALPHA = 0.9

# 授乳中の母親にかかる消費エネルギー倍率
LACTATING_COST_MULT = 1.3274154455652951

# 評価指標 ============================================================
# 1つ目の指標 月別人里滞在個体数
# 人里とみなす土地利用コードの集合
URBAN_LANDUSE_CODES = {100, 200, 700, 901, 902, 1000, 1600}
# カレンダー計算用（Day 1 を 1月1日とする）
SIMULATION_START_DATE = datetime.date(2025, 1, 1)
# ====================================================================

# =========================================================
# Optuna評価用：現実の観測データ（ターゲット）
# =========================================================

TARGET_DATA = {
    # -----------------------------------
    # 豊作年（Good Mast）シナリオの正解
    # -----------------------------------
    "good_mast": {
        # 1. 月別目撃数トレンド（波形評価用）
	"sighting_trend": [
            0.00645526852151458, 0.00660405067490547, 0.0089596058381704,
            0.0436095191900461, 0.160946803930913, 0.259019511744253,
            0.209976435548596, 0.16062373229098, 0.0656876049845815,
            0.031806182067832, 0.0203908948119344, 0.025920390396273
        ],
        
        # 2. 月別親子連れ割合
        "family_ratio": [
            0.0353477765108324, 0.0256556442417332, 0.0632839224629418,
            0.121552919986346, 0.0501710376282782, 0.126427431869406,
            0.163404484018331, 0.12880598062784, 0.214085124205032,
            0.0438996579247434, 0.0176738882554162, 0.0096921322690992
        ],
        
        # 3. 【東北6県】月別捕殺数トレンド
        # ※絶対数は気にせず、波の形だけを合わせるためのデータです
        "kill_trend_tohoku": [0, 0, 0, 16, 45, 72, 96, 82, 39, 20, 24, 12],
        
        # 4. 【秋田県】年間捕殺割合（規模評価用：シミュレーション内の年間捕殺率と比較）
        # 例：秋田県の推定生息数7500頭に対し、年間400頭捕殺されたなら 400/3500 = 0.0533 (5.33%)
        "annual_kill_rate_akita": 0.0533,
        
        # 5. 自然増加率の許容レンジ (min, max)
        "lambda_range": (1.05, 1.2),
        
        # 6. 月別エネルギー収支トレンド (kcal/day)
	# ※ 1〜4月、12月はダミー(0)、5月〜11月の波形だけを評価に使う
        "energy_trend": [0, 0, 0, 0, 900, -1600, -1800, -1700, 3000, 5250, 2600, 0],
    },

    # -----------------------------------
    # 凶作年（Poor Mast）シナリオの正解
    # -----------------------------------
    "poor_mast": {
        # 1. 月別目撃数トレンド
        "sighting_trend": [
            0.00229947751336638, 0.00209764780823155, 0.00237380318338086, 
            0.0171893770016559, 0.0633743322653629, 0.105577116458004, 
            0.11897253043508, 0.0977694438686358, 0.113609069847228, 
            0.273547416515553, 0.174859986293002, 0.0283297988105007
        ], 
        
        # 2. 月別親子連れ割合
        "family_ratio": [
            0.0133565621370499, 0.0, 0.0505226480836237,
            0.0679662763325136, 0.0424699245010159, 0.0504409927144071,
            0.0363081673634233, 0.0629498431894587, 0.175050846583529,
            0.215018463783158, 0.117117436537125, 0.168798838774697
        ],
        
        # 3. 【東北6県】月別捕殺数トレンド
        "kill_trend_tohoku": [0, 0, 0, 29, 26, 62, 181, 323, 526, 818, 336, 16],
        
        # 4. 【秋田県】年間捕殺割合
        # 例：7500頭に対し、年間2000頭捕殺されたなら 2000/7500 = 0.267 (26.7%)  以上な捕殺率なので下方修正する→10.0%
        "annual_kill_rate_akita": 0.10,
        
        # 5. 自然増加率の許容レンジ (min, max)
        "lambda_range": (0.95, 1.15),
        
        # 6. 月別エネルギー収支トレンド
	# ※ 1〜4月、12月はダミー(0)、5月〜11月の波形だけを評価に使う
        "energy_trend": [0, 0, 0, 0, 900, -1600, -1800, -1700, 1850, 4000, 500, 0],
    },

    # -----------------------------------
    # 共通（年次を問わない）正解データ
    # -----------------------------------
    "common": {
        # 7. 捕殺個体の齢分布（0歳〜20歳までの21要素リスト）
        # ※雄雌の捕殺数を合計し、全体を1.0とした割合に変換しておく
        # 例：若獣（1〜3歳）の割合が高く、高齢になるほど減っていく滑らかなカーブ
        "kill_age_distribution": [
            0.0168478755049816, # 0歳 
            0.0677357338633205, # 1歳 
            0.0889482093449203, # 2歳
            0.122553031188704, # 3歳
            0.150968395619812, # 4歳
            0.161970824727537, # 5歳
            0.123238247405271, # 6歳
            0.0719996622630971, # 7歳
            0.0714118701531507, # 8歳
            0.0220730550900848, # 9歳
            0.0600652092020316, # 10歳
            0.00730680799657067, # 11歳
            0.0163217853292285, # 12歳
            0.00873569489367782, # 13歳
            0.0032020056376083, # 14歳
            0.00531610875128275, # 15歳
            0.000435161009573542, # 16歳
            0.000435161009573542, # 17歳
            0.000217580504786771, # 18歳
            0.0, # 19歳
            0.000217580504786771  # 20歳
        ]
    }
}

# ==========================================
# [2] 推定対象パラメータ
# ==========================================
@dataclass
class SimConfig:
    """
    シミュレーションの挙動を制御するコア・パラメータ群。
    パラメータ推定（最適化）を回す際は、このクラスのインスタンスを生成し、
    数値を書き換えて各個体（Bear）や環境（World）に渡す。
    """
    # 飢餓時の死亡確率を決める係数 k
    starvation_mortality_k: float = 0.0002

    # 冬眠解除における気温の影響度 (k_temp)
    wakeup_k_temp: float = 0.02

    # 冬眠開始における気温の影響度 (k_enter_temp)
    hibernation_k_temp: float = 0.07

    # 飢餓による探索半径の拡大係数 (hunger_radius_k)
    hunger_radius_k: float = 2.0

    # 人口に対するベース忌避係数 (base_avoidance_k)
    base_avoidance_k: float = 3.0

    # 人里経験による慣れ（恐怖心減少）のスピード (urban_habituation_k)
    urban_habituation_k: float = 0.05

    # 目的地選択のソフトマックス逆温度（合理性の強さ）
    decision_softmax_beta: float = 0.2

    # 1日あたりの資源回復割合 (resource_recovery_rate)
    resource_recovery_rate: float = 0.1

    # 人為的死亡（捕殺）リスクの増加係数
    kill_pop_k: float = 0.001 

    # # 同じ場所に滞在し続けることによるリスク増加率（罠の学習、パトロール強化など）
    # kill_duration_k: float = 0.001

    # 秋の焦り閾値引き上げ幅 (autumn_panic_offset) 20→30
    autumn_panic_offset: float = 20.0


class Bear:
    def __init__(self, bid, age, gender, x, y, mother_id=-1, config=None):
        self.id = int(bid)
        self.age = int(age)
        self.gender = str(gender)
        self.x, self.y = int(x), int(y)
        self.config = config if config else SimConfig()

        # 慣性用（毎日更新する）
        self.prev_x, self.prev_y = int(x), int(y)

        self.mother_id = int(mother_id)
        self.is_alive = True
        self.mode = HIBERNATION
        self.repro_status = "NORMAL"  # NORMAL, MATED, LACTATING
        
        # 初期エネルギーの生成（正規分布 ＋ 安全装置クリッピング)
        raw_energy = np.random.normal(INITIAL_ENERGY_MEAN, INITIAL_ENERGY_STD)
        self.energy = float(np.clip(raw_energy, INITIAL_ENERGY_MIN, INITIAL_ENERGY_MAX))

        # 2歳以上 or 母不在なら独立
        self.is_independent = True if (self.age >= 2 or self.mother_id == -1) else False
        self.cub_count = 0

        self.update_age_class()

        # 人里滞在カウンター
        self.stay_urban_counts = 0
        self.total_urban_experience = 0

        self.wakeup_day = None
        self.death_cause = None  # "ENERGY" or "HUMAN"

    def update_age_class(self):
        if self.age == 0:
            self.age_class = "Cu"
        elif self.age == 1:
            self.age_class = "Yr"
        elif 2 <= self.age <= 3:
            self.age_class = "Su"
        else:
            self.age_class = "Ad"

    def get_dominance_rank(self):
        # M_Ad(5) > F_Ad(4) > M_Su(3) > F_Su(2) > Yr(1) > Cu(0)
        if self.age_class == "Ad":
            return 5 if self.gender == "M" else 4
        if self.age_class == "Su":
            return 3 if self.gender == "M" else 2
        if self.age_class == "Yr":
            return 1
        return 0
    
    def update_energy_hibernation(self):
        """冬眠中の低代謝消費"""
        # Configからパラメータを読み込む
        alpha = ENERGY_COST_ALPHA
        k = self.config.starvation_mortality_k

        self.energy -= (HIBERNATION_ENERGY_COST * alpha)
        self.energy = float(np.clip(self.energy, MIN_ENERGY, MAX_ENERGY))
        
        if self.energy < STARVATION_THRESHOLD:
            risk_factor = STARVATION_THRESHOLD - self.energy
            if np.random.random() < (1.0 - np.exp(-k * risk_factor)):
                self.is_alive = False
                self.death_cause = "ENERGY"

    def update_energy(self, action, dx, dy, world, day):
        """エネルギー更新（独立・非独立の全個体共通）"""
        # 死亡している場合は何もしない
        if not self.is_alive:
            return

        # Configからパラメータを読み込む
        alpha = ENERGY_COST_ALPHA
        k = self.config.starvation_mortality_k

        dist = float(np.sqrt(dx**2 + dy**2))

        # --- 行動ごとの消費エネルギー（αを掛ける） ---
        if action == HIBERNATION:
            cost = HIBERNATION_ENERGY_COST * alpha
        elif action == RESTING:
            cost = RESTING_ENERGY_COST * alpha
        elif action == MOVING:
            cost = (MOVING_BASE_COST + (dist * MOVING_DIST_MULT)) * alpha
        elif action == FORAGING:
            cost = FORAGING_ENERGY_COST * alpha
        else:
            cost = RESTING_ENERGY_COST * alpha

        # 授乳中の母親のみコスト1.6倍（子グマやオスはLACTATINGにならないので自動スルーされる）
        if self.repro_status == "LACTATING":
            cost *= LACTATING_COST_MULT

        # --- ゲイン（獲得エネルギー） ---
        gain = 0.0
        if action == FORAGING:
            gain = world.get_area_gain(self.x, self.y, day)

        # --- エネルギーの更新 ---
        self.energy = float(np.clip(self.energy + (gain - cost), MIN_ENERGY, MAX_ENERGY))

        # --- 飢餓による死亡判定 ---
        if self.energy < STARVATION_THRESHOLD:
            risk_factor = STARVATION_THRESHOLD - self.energy
            death_probability = 1.0 - np.exp(-k * risk_factor)
            if np.random.random() < death_probability:
                self.is_alive = False
                self.death_cause = "ENERGY"

    def check_wakeup(self, day, temp):
        """冬眠解除判定"""
        # すでに冬眠から明けている場合はTrueを返す
        if self.mode != HIBERNATION:
            return True
        
        # 定数を参照：指定日数（3月上旬）以前は気温によらず絶対に起きない（固定ルール）
        if day < WAKEUP_MIN_DAY or day > WAKEUP_MAX_DAY:
            return False

        # Configから推定パラメータ(k_temp)を読み込む
        k_temp = self.config.wakeup_k_temp

        # 気温が基準気温を超えた分だけ、目覚める確率が上がる
        # ※ 基準気温は生態学的な固定値として扱う
        p_wakeup = min(1.0, max(0.0, temp - WAKEUP_BASE_TEMP) * k_temp)

        # 確率判定
        if np.random.random() < p_wakeup:
            self.mode = RESTING
            self.wakeup_day = day
            return True
            
        return False

    def check_hibernation(self, day, temp, landuse, mast_factor):
        """冬眠開始判定"""
        # 既に冬眠中、または非独立個体（母の行動に従うため自身では判定しない）ならスキップ
        if self.mode == HIBERNATION or (not self.is_independent):
            return False
        
        dynamic_min_energy = HIBERNATION_MIN_ENERGY - (1.0 - mast_factor) * HIBERNATION_ENERGY_DROP_RATE

        # 冬眠を乗り切るためのエネルギーを満たしていないと、寒くても冬眠できない
        if self.energy < dynamic_min_energy:
            return False
            
        # Day290より前は、一時的に冷え込んでも絶対に冬眠しない（固定ルール）
        if day < HIBERNATION_START_DAY:
            return False
            
        # 指定の植生（例：500=奥山の広葉樹林など、冬眠適地）にいないと冬眠穴を掘れない
        if landuse != HIBERNATION_LANDUSE:
            return False

        # Configから推定パラメータ(k_enter_temp)を読み込む
        k_enter_temp = self.config.hibernation_k_temp

        # 気温が基準気温を下回った分だけ、冬眠に入る確率が上がる（最大90%）
        p_enter = min(0.9, max(0.0, HIBERNATION_BASE_TEMP - temp) * k_enter_temp)

        # 確率判定
        if np.random.random() < p_enter:
            self.mode = HIBERNATION
            self.stay_urban_counts = 0  # 街にいた場合は滞在日数をリセット
            return True
            
        return False
    
    def decide_action(self, day, temp, precip, mother_mode=None):
        """1日の行動モード決定"""
        if (not self.is_independent) and (mother_mode is not None):
            self.mode = mother_mode
            return self.mode

        if self.mode == HIBERNATION:
            return HIBERNATION

        # 基本確率のロード
        p_rest, p_move, p_forage = BASE_P_REST, BASE_P_MOVE, BASE_P_FORAGE

        # 起床直後ブースト（冬眠明け20日間はあまり動かない）
        if self.wakeup_day is not None and (day - self.wakeup_day) <= POST_WAKEUP_DAYS:
            p_move -= POST_WAKEUP_MOVE_PENALTY

        # 悪天候（猛暑・大雨）時は休む
        if temp >= HOT_TEMP_THRESHOLD or precip >= HEAVY_RAIN_THRESHOLD:
            p_rest += WEATHER_REST_BOOST
            
        # 成獣オスの交尾期の徘徊
        if MATING_START_DAY <= day <= MATING_END_DAY and self.gender == "M" and self.age >= 4:
            p_move += MATING_MOVE_BOOST
            
        # 2歳若グマの親離れ（分散）移動
        if self.age == 2 and self.is_independent:
            p_move += DISPERSAL_MOVE_BOOST

        # # 秋の飽食期（月ごとの採餌欲求の高まり）
        # if FALL_SEP_START <= day < FALL_OCT_START:
        #     p_forage += FALL_SEP_BOOST
        # elif FALL_OCT_START <= day < FALL_NOV_START:
        #     p_forage += FALL_OCT_BOOST
        # elif FALL_NOV_START <= day <= FALL_NOV_END:
        #     p_forage += FALL_NOV_BOOST
 
        # 基本の飢餓閾値（HUNGER_THRESHOLD = 20.0）
        current_hunger_threshold = HUNGER_THRESHOLD

        # # 秋（9月: Day 244 以降）は冬眠準備のため、焦りのハードル（閾値）が上がる
        # if day >= FALL_SEP_START:
        #     current_hunger_threshold += self.config.autumn_panic_offset

        if FALL_SEP_START <= day <= FALL_NOV_END:
            # 秋の進行度を 0.0 ～ 1.0 で計算 (9/1 -> 0.0, 11/30 -> 1.0)
            progress = (day - FALL_SEP_START) / (FALL_NOV_END - FALL_SEP_START)

            # ① 採餌確率のブースト：緩やかなシグモイド（S字）カーブ
            # コサイン波の下半分（0〜π）を使い、0.0 から 1.0 へ滑らかに遷移させます
            curve_factor = (1.0 - math.cos(progress * math.pi)) / 2.0

            p_forage += MAX_FALL_BOOST * curve_factor

            # ② 焦りのハードル（閾値）の引き上げ：こちらは冬眠に向けて直線的に焦っていく
            current_hunger_threshold += self.config.autumn_panic_offset * progress
        
        elif day > FALL_NOV_END:
            # 12月以降（冬眠に入れず起きている場合）はMAXで焦っている状態
            current_hunger_threshold += self.config.autumn_panic_offset

        # 現在のエネルギーが閾値を下回っていれば、リスクを冒して採餌・移動に走る
        if self.energy <= current_hunger_threshold:
            p_forage += HUNGER_FORAGE_BOOST
            p_move += HUNGER_MOVE_BOOST
            
            # さらにエネルギーが極限の飢餓状態（CRITICAL_STARVATION_THRESHOLD = 5.0）を下回っていれば、最後の力を振り絞る
            if self.energy <= CRITICAL_STARVATION_THRESHOLD:
                p_forage += EXTREME_STARVE_FORAGE_BOOST
                p_move += EXTREME_STARVE_MOVE_BOOST

        # 確率の正規化（0未満をカットし、合計を1にする）
        probs = np.array([p_rest, p_move, p_forage], dtype=float)
        probs = np.maximum(probs, 0.0)
        probs_sum = probs.sum()
        
        if probs_sum <= 0:
            self.mode = RESTING
            return self.mode
            
        probs /= probs_sum

        # モードの決定
        self.mode = int(np.random.choice([RESTING, MOVING, FORAGING], p=probs))
        return self.mode
    
    def get_search_radius(self, day):
        """探索半径（メッシュ単位）"""
        radius = BASE_SEARCH_RADIUS

        # 独立直後の若グマの放浪（分散）
        if self.is_independent and (self.age_class in ["Yr", "Su"]):
            radius += DISPERSAL_RADIUS_BONUS
            
        # 成獣オスの交尾期の徘徊（前回の定数を再利用）
        if MATING_START_DAY <= day <= MATING_END_DAY and self.age_class == "Ad" and self.gender == "M":
            radius += MATING_RADIUS_BONUS

        # 飢餓による探索範囲の拡大（秋のHyperphagiaを連動）
        current_hunger_threshold = HUNGER_THRESHOLD

        # 秋（9月以降）は焦り始めるエネルギー閾値が上がる（前回ロジックの再利用）
        if day >= FALL_SEP_START:
            current_hunger_threshold += self.config.autumn_panic_offset

        # 現在のエネルギーが閾値を下回っていれば、探索半径を広げる
        if self.energy < current_hunger_threshold:
            # Configから推定パラメータを読み込む
            hunger_radius_k = self.config.hunger_radius_k
            
            # 閾値からどれだけ下回っているか × 拡大係数
            hunger_bonus = int((current_hunger_threshold - self.energy) * hunger_radius_k)
            
            # ボーナスを追加（ただし上限値 MAX_HUNGER_RADIUS_BONUS まで）
            radius += min(MAX_HUNGER_RADIUS_BONUS, hunger_bonus)
            
        return int(radius)

    def update_stay_urban_counts(self, current_landuse):
        """人里への連続滞在日数の更新"""
        # 定数を参照して判定
        if current_landuse in URBAN_LANDUSE_CODES:
            self.stay_urban_counts += 1
        else:
            self.stay_urban_counts = 0

    def update_total_experience(self, current_landuse):
        """人里での累積経験（生涯）の更新"""
        # 定数（URBAN_LANDUSE_CODES）を参照して判定
        if current_landuse in URBAN_LANDUSE_CODES:
            self.total_urban_experience += 1

    def _bresenham_cells(self, x0, y0, x1, y1):
        """
        (x0,y0)→(x1,y1) を結ぶ直線上の格子セルを順に返す（Bresenham）。
        始点(x0,y0)は除外し、終点(x1,y1)は含めます。
        """
        x0 = int(x0); y0 = int(y0); x1 = int(x1); y1 = int(y1)

        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy

        x, y = x0, y0
        while not (x == x1 and y == y1):
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
            yield x, y

    def apply_barrier_on_path(self, target_x, target_y, world):
        """
        現在地(self.x,self.y)→(target_x,target_y) の直線上を走査し、
        途中セルに川があれば、セルごとに一定確率で障壁として機能する。（川幅が広い＝川セルが連続するほど、渡り切る確率は自然に低くなる）
        """
        x0, y0 = self.x, self.y
        prev_x, prev_y = x0, y0

        # ブレゼンハム・アルゴリズムで直線上を走査
        for cx, cy in self._bresenham_cells(x0, y0, target_x, target_y):
            lu = world.env[0, cy, cx]

            # 定数を参照して川かどうか判定
            is_river = (int(lu) == RIVER_LANDUSE_CODE)

            if is_river:
                # 川セルごとにサイコロを振る
                # 定数の確率（0.5）で「渡るのを諦める（障壁として機能）」
                if np.random.random() < RIVER_BARRIER_PROB:
                    return int(prev_x), int(prev_y)
                # 残りの確率を引いた場合はそのまま（次のセルへループ継続）

            prev_x, prev_y = cx, cy

        # 川がない、またはすべての川セルで関門を突破した場合は目的地へ到達
        return int(target_x), int(target_y)
    
    def decide_destination(
        self, day, world, world_bear_map,
        top_n=20, max_trials=10, sample_size=20
    ):
        """
        候補をランダムサンプルし、gain/avoidance/inertia をベクトル化計算。
        競合チェックは候補ごとに必要なのでループ。
        """
        radius = self.get_search_radius(day)

        min_x = max(0, self.x - radius)
        max_x = min(X_SIZE - 1, self.x + radius)
        min_y = max(0, self.y - radius)
        max_y = min(Y_SIZE - 1, self.y + radius)

        # --------------------------------------------------
        # --- 1. 候補点生成（重複排除、円内のみ）---
        # --------------------------------------------------
        oversample = 3
        need = int(sample_size)
        cand_set = set()
        tries = 0
        max_tries = 10

        while len(cand_set) < need and tries < max_tries:
            n = (need - len(cand_set)) * oversample
            xs = np.random.randint(min_x, max_x + 1, size=n)
            ys = np.random.randint(min_y, max_y + 1, size=n)

            dxs = xs - self.x
            dys = ys - self.y
            inside = (dxs * dxs + dys * dys) <= (radius * radius)

            xs = xs[inside]
            ys = ys[inside]

            for tx, ty in zip(xs.tolist(), ys.tolist()):
                if tx == self.x and ty == self.y:
                    continue
                cand_set.add((tx, ty))

            tries += 1

        if not cand_set:
            return 0, 0

        candidates = np.array(list(cand_set), dtype=np.int32)  # shape (K,2) [x,y]
        tx = candidates[:, 0]
        ty = candidates[:, 1]

        # --------------------------------------------------
        # --- 2. Gain（獲得エネルギー）の計算 ---
        # --------------------------------------------------
        veg_codes = world.env[1, ty, tx]
        # ここで pops（人口データ）を定義して取得しておく！
        pops = world.env[2, ty, tx].astype(np.float32, copy=False) 

        gains = np.empty(len(veg_codes), dtype=np.float32)
        for i in range(len(tx)):
            gains[i] = world.get_area_gain(cx=int(tx[i]), cy=int(ty[i]), day=day)

        # --------------------------------------------------
        # --- 3. Avoidance（忌避スコア）のベクトル化 ---
        # --------------------------------------------------
        base_k = self.config.base_avoidance_k
        habituation_k = self.config.urban_habituation_k

        # 秋のパニック閾値の計算（定数 FEAR_DROP_ENERGY_THRESHOLD = 50.0 などを使用）
        current_fear_drop_threshold = FEAR_DROP_ENERGY_THRESHOLD
        if day >= FALL_SEP_START:
            current_fear_drop_threshold += self.config.autumn_panic_offset    
       
        # 人口（pops）の対数を計算
        raw_avoid = np.log1p(pops)
        
        # 固定定数（全域の最大値の対数）で割って 0.0 ~ 1.0 に正規化
        norm_raw_avoid = raw_avoid / GLOBAL_LOG_POP_MAX
        
        # 飢餓・経験の割引率を計算
        e_ratio = max(0.0, min(1.0, self.energy / MAX_ENERGY))
        curve_value = 2.0 * (1.0 - (1.0 - e_ratio)**HUNGER_FEAR_RATIO) + 30.0 * (e_ratio ** 6)
        hunger_factor = max(MIN_HUNGER_FEAR_FACTOR, curve_value)
        # hunger_factor = max(MIN_HUNGER_FEAR_FACTOR, min(1.0, self.energy / current_fear_drop_threshold))
        experience_factor = max(MIN_EXPERIENCE_FEAR_FACTOR, 1.0 - (self.total_urban_experience * habituation_k))
        
        # ④ 係数を掛けて最終忌避スコアにする
        avoidances = norm_raw_avoid * base_k * hunger_factor * experience_factor

        # --------------------------------------------------
        # --- 4. Inertia (慣性) のベクトル化 ---
        # --------------------------------------------------
        v_prev = np.array([self.x - self.prev_x, self.y - self.prev_y], dtype=np.float32)
        prev_norm = float(np.linalg.norm(v_prev))
        
        if prev_norm > 0:
            v_curr = np.stack([tx - self.x, ty - self.y], axis=1).astype(np.float32, copy=False)
            curr_norm = np.linalg.norm(v_curr, axis=1)
            denom = prev_norm * curr_norm
            cos_theta = np.zeros_like(curr_norm, dtype=np.float32)
            mask = denom > 0
            cos_theta[mask] = (v_curr[mask] @ v_prev) / denom[mask]
            
            # 直接 0.0 ~ 1.0 に正規化
            norm_inertia = (cos_theta + 1.0) / 2.0
        else:
            norm_inertia = np.full(len(tx), 0.5, dtype=np.float32)

        # --------------------------------------------------
        # --- 5. 各スコアの正規化---
        # --------------------------------------------------
        # 局所的Min-Maxを廃止し、絶対基準で割るだけ（クリップなし）
        norm_gains = gains / GLOBAL_MAX_GAIN

        # そのまま足し引き！
        total_scores = norm_gains - avoidances + (norm_inertia * inertia_weight)
        
        finite_mask = np.isfinite(total_scores)
        if not np.any(finite_mask):
            return 0, 0

        candidates = candidates[finite_mask]
        total_scores = total_scores[finite_mask]

        # --------------------------------------------------
        # --- 6. 上位 top_n の抽出とソート ---
        # --------------------------------------------------
        # ★ここで top_candidates と top_scores が定義される
        if len(total_scores) > top_n:
            idx_part = np.argpartition(-total_scores, top_n - 1)[:top_n]
            top_candidates = candidates[idx_part]
            top_scores = total_scores[idx_part]
            
            order = np.argsort(-top_scores)
            top_candidates = top_candidates[order]
            top_scores = top_scores[order]
        else:
            order = np.argsort(-total_scores)
            top_candidates = candidates[order]
            top_scores = total_scores[order]

        # --------------------------------------------------
        # --- 7. Softmax （確率分布への変換）---
        # --------------------------------------------------
        # ★Configから推定パラメータ(decision_softmax_beta)を読み込む！
        beta = self.config.decision_softmax_beta 
        
        scores = top_scores.astype(np.float64) * beta
        exps = np.exp(scores - np.max(scores))
        s = exps.sum()
        
        if (not np.isfinite(s)) or s <= 0:
            target_x, target_y = int(top_candidates[0, 0]), int(top_candidates[0, 1])
            return target_x - self.x, target_y - self.y
            
        probs = exps / s
        
        if np.any(~np.isfinite(probs)):
            target_x, target_y = int(top_candidates[0, 0]), int(top_candidates[0, 1])
            return target_x - self.x, target_y - self.y

        # --------------------------------------------------
        # --- 8. 競合チェック（Dominance Rank）付きの移動試行 ---
        # --------------------------------------------------
        my_rank = self.get_dominance_rank()

        for trial in range(max_trials):
            idx = int(np.random.choice(len(top_candidates), p=probs))
            target_x = int(top_candidates[idx, 0])
            target_y = int(top_candidates[idx, 1])

            other_infos = world_bear_map.get((target_x, target_y), [])
            if not other_infos:
                new_tx, new_ty = self.apply_barrier_on_path(target_x, target_y, world)
                return new_tx - self.x, new_ty - self.y

            conflict = False
            for other in other_infos:
                # 定数（MATING_START_DAY, MATING_END_DAY）を使用して交尾期の重複を許可
                is_breeding_pair = (
                    MATING_START_DAY <= day <= MATING_END_DAY
                    and self.age_class == "Ad"
                    and other["age_class"] == "Ad"
                    and self.gender != other["gender"]
                    and (self.repro_status == "NORMAL" or other["repro_status"] == "NORMAL")
                )
                if is_breeding_pair:
                    continue

                if other["rank"] > my_rank:
                    conflict = True
                    break

            if not conflict:
                new_tx, new_ty = self.apply_barrier_on_path(target_x, target_y, world)
                return new_tx - self.x, new_ty - self.y

        #試行回数を超えても移動先が見つからなかった場合は移動しない
        return 0, 0


class World:
    def __init__(self, world_id, env_data, veg_csv_path, initial_pop_size, mast_level, config=None):
        self.world_id = int(world_id)
        
        # ★推定パラメータ(Config)をWorld自身も保持する（クマ生成時に渡すため）
        self.config = config if config else SimConfig()

        self.env = env_data  # [Land, Veg, Pop, Elev, Slope]
        if self.env.shape[1] != Y_SIZE or self.env.shape[2] != X_SIZE:
            raise ValueError(f"env_data shape mismatch: got {self.env.shape}, expected (5,{Y_SIZE},{X_SIZE})")

        df = pd.read_csv(veg_csv_path)
        self.veg_master = df.set_index("veg_code").to_dict("index")

        self.mast_level = mast_level
        # ★定数ブロックから豊凶の係数を取得する（デフォルトはAverage(0.7)の安全設計）
        self.current_mast_factor = float(MAST_LEVEL_FACTORS.get(mast_level, 0.7))

        self.current_temp = 0.0
        self.current_precip = 0.0

        # ★注意：この関数の中で Bear(..., config=self.config) のように渡すようにしてください！
        self.bears = self.initialize_all_bears(initial_pop_size)
        
        # bear_dict を正式採用（get_bear_by_idはこれを使う）
        self.bear_dict = {b.id: b for b in self.bears}

        # 日次の資源枯渇管理マップ（1.0=未消費、0.0=枯渇）
        self.daily_resource = np.ones((Y_SIZE, X_SIZE), dtype=np.float32)

    def get_bear_by_id(self, bear_id):
        """O(1)辞書引き版（重複定義を排除）"""
        return self.bear_dict.get(int(bear_id))
    
    def get_season_name(self, day):
        """シミュレーション内カレンダーに基づく季節判定"""
        if SPRING_START_DAY <= day <= SPRING_END_DAY:
            return "spring"
        if SUMMER_START_DAY <= day <= SUMMER_END_DAY:
            return "summer"
        if FALL_SEP_START <= day <= AUTUMN_END_DAY:
            return "autumn"
            
        return "other"
    
    def calculate_patch_gain(self, veg_code, day):
        """指定された植生のベースとなるGainの算出（気象ノイズ排除）"""
        if veg_code is None:
            return 0.0
        if isinstance(veg_code, float) and np.isnan(veg_code):
            return 0.0
            
        try:
            veg_code_int = int(veg_code)
        except (ValueError, TypeError, OverflowError):
            return 0.0

        veg = self.veg_master.get(veg_code_int)
        if not veg:
            return 0.0

        # 基本ゲインの取得
        gain = float(veg["base_gain"])
        season = self.get_season_name(day)

        # 1. 旬（シーズン）による倍率ボーナス
        if season != "other" and veg.get(season) == 1:
            gain *= SEASON_PEAK_MULTIPLIER

        # 2. 秋のマスティング（豊凶）による変動
        if season == "autumn" and veg.get("is_mast_affected", 0) == 1:
            gain *= self.current_mast_factor

        # 3. ランダムボーナス
        if veg.get("random_bonus", 0) == 1:
            if np.random.random() < float(veg["bonus_prob"]):
                bonus = float(veg["bonus_gain"])
                
                # ボーナス分も秋の豊凶の影響を受ける場合
                if season == "autumn" and veg.get("is_mast_affected", 0) == 1:
                    bonus *= self.current_mast_factor
                    
                gain += bonus

        return float(gain)

    def get_area_gain(self, cx, cy, day):
        """指定座標周辺の『得られる実質Gain合計（面的ゲイン）』を計算"""
        # 中心パッチ自体が完全に無効（海や場外など）ならゼロとして弾く
        center_veg = self.env[1, cy, cx]
        if np.isnan(center_veg):
            return 0.0
            
        total_gain = 0.0

        # 定数を使って走査範囲を決定（通常は radius=1 で 3x3=9パッチ）
        min_x = max(0, cx - FORAGING_NEIGHBORHOOD_RADIUS)
        max_x = min(X_SIZE - 1, cx + FORAGING_NEIGHBORHOOD_RADIUS)
        min_y = max(0, cy - FORAGING_NEIGHBORHOOD_RADIUS)
        max_y = min(Y_SIZE - 1, cy + FORAGING_NEIGHBORHOOD_RADIUS)
        
        # 面全体のゲインを合算
        for ny in range(min_y, max_y + 1):
            for nx in range(min_x, max_x + 1):
                # そのパッチの資源がまだ残っている（誰にも食べられていない）場合のみ計算
                if self.daily_resource[ny, nx] > 0:
                    n_veg = self.env[1, ny, nx]
                   
                    patch_max_gain = self.calculate_patch_gain(n_veg, day)
                    total_gain += patch_max_gain * self.daily_resource[ny, nx]

        return float(total_gain)
    
    def consume_resources(self, cx, cy):
        """クマが採餌した後のパッチ（および周辺）を枯渇（0.0）状態にする"""
        # 中心が場外・無効値なら何もしない
        center_veg = self.env[1, cy, cx]
        if np.isnan(center_veg):
            return

        # ゲイン評価時と全く同じ定数（半径）を使って消費範囲を決定
        min_x = max(0, cx - FORAGING_NEIGHBORHOOD_RADIUS)
        max_x = min(X_SIZE - 1, cx + FORAGING_NEIGHBORHOOD_RADIUS)
        min_y = max(0, cy - FORAGING_NEIGHBORHOOD_RADIUS)
        max_y = min(Y_SIZE - 1, cy + FORAGING_NEIGHBORHOOD_RADIUS)
        
        # 範囲内の資源を一律で枯渇させる（面消費）
        # ※ゲイン計算で無効なパッチは弾かれるため、ここでは無条件で0.0を入れてOK（高速化）
        for ny in range(min_y, max_y + 1):
            for nx in range(min_x, max_x + 1):
                self.daily_resource[ny, nx] = 0.0

    def recover_resources(self):
        """
        日次の資源回復処理（メインループの1日の終わりに呼び出す）
        マップ全体の枯渇した資源を、Configで指定された割合だけ回復させる。
        """
        # Configから推定パラメータ(回復割合)を読み込む
        rate = self.config.resource_recovery_rate
        
        # マップ全体(daily_resource)に rate を足し合わせ、最大値 1.0 でクリップする
        self.daily_resource = np.clip(self.daily_resource + rate, 0.0, 1.0)

    # def initialize_all_bears(self, total_n):
    #     """シミュレーション開始時の全個体の生成と初期配置"""
    #     landuse = self.env[0]
    #     # 定数を参照して初期配置可能なセル（森林など）を取得
    #     forest_y, forest_x = np.where(landuse == SPAWN_LANDUSE_CODE)
    #     num_forest = len(forest_y)
        
    #     if num_forest == 0:
    #         raise ValueError(f"No spawn cells (landuse=={SPAWN_LANDUSE_CODE}) found.")

    #     bears = []
    #     bid_counter = 0

    #     # =========================================================
    #     # A. 成獣メス + 非独立子グマ（0歳、1歳）
    #     # =========================================================
    #     num_f_ad = int(total_n * POP_RATIO_ADULT_FEMALE)
    #     for _ in range(num_f_ad):
    #         idx = np.random.randint(0, num_forest)
    #         x, y = int(forest_x[idx]), int(forest_y[idx])

    #         # ★最重要：config=self.config を渡す！
    #         mother = Bear(
    #             bid_counter, 
    #             age=np.random.randint(AGE_MIN_ADULT, AGE_MAX_ADULT + 1), 
    #             gender="F", x=x, y=y, 
    #             config=self.config
    #         )
    #         bid_counter += 1

    #         # 家族構成の決定（ルーレット選択）
    #         family_status = np.random.choice(
    #             ["CUBS", "YEARLINGS", "SINGLE"], 
    #             p=[PROB_MOTHER_CUBS, PROB_MOTHER_YEARLINGS, PROB_MOTHER_SINGLE]
    #         )

    #         if family_status in ["CUBS", "YEARLINGS"]:
    #             mother.repro_status = "LACTATING"
    #             num_cubs = int(np.random.choice(LITTER_SIZE_CHOICES, p=LITTER_SIZE_PROBS))
    #             mother.cub_count = num_cubs
                
    #             # 子グマの年齢（CUBSなら0歳、YEARLINGSなら1歳）
    #             cub_age = 0 if family_status == "CUBS" else 1

    #             for _ in range(num_cubs):
    #                 # ★子グマにも config を渡す！
    #                 child = Bear(
    #                     bid_counter, age=cub_age, 
    #                     gender=np.random.choice(["M", "F"]),
    #                     x=x, y=y, mother_id=mother.id, 
    #                     config=self.config
    #                 )
    #                 bears.append(child)
    #                 bid_counter += 1
    #         else:
    #             mother.repro_status = "NORMAL"
    #             mother.cub_count = 0

    #         bears.append(mother)

    #     # =========================================================
    #     # B. 成獣オス
    #     # =========================================================
    #     num_m_ad = int(total_n * POP_RATIO_ADULT_MALE)
    #     for _ in range(num_m_ad):
    #         idx = np.random.randint(0, num_forest)
    #         bears.append(Bear(
    #             bid_counter, 
    #             age=np.random.randint(AGE_MIN_ADULT, AGE_MAX_ADULT + 1), 
    #             gender="M", x=int(forest_x[idx]), y=int(forest_y[idx]), 
    #             config=self.config  # ★追加
    #         ))
    #         bid_counter += 1

    #     # =========================================================
    #     # C. 若獣（独立済みサブアダルト）
    #     # =========================================================
    #     num_su = int(total_n * POP_RATIO_SUBADULT)
    #     for _ in range(num_su):
    #         idx = np.random.randint(0, num_forest)
    #         bears.append(Bear(
    #             bid_counter, 
    #             age=np.random.randint(AGE_MIN_SUBADULT, AGE_MAX_SUBADULT + 1), 
    #             gender=np.random.choice(["M", "F"]),
    #             x=int(forest_x[idx]), y=int(forest_y[idx]), 
    #             config=self.config  # ★追加
    #         ))
    #         bid_counter += 1

    #     return bears

    def initialize_all_bears(self, total_n):
        """シミュレーション開始時の全個体の生成と初期配置"""
        landuse = self.env[0]
        forest_y, forest_x = np.where(landuse == SPAWN_LANDUSE_CODE)
        num_forest = len(forest_y)
        
        if num_forest == 0:
            raise ValueError(f"No spawn cells found.")

        bears = []
        bid_counter = 0

        # =========================================================
        # 1. 全頭の「年齢」と「性別」を確率に従って一括生成する
        # =========================================================
        ages = np.arange(21) # 0歳〜20歳
        # INITIAL_AGE_DISTRIBUTION の確率に従って total_n 頭分の年齢を決定
        assigned_ages = np.random.choice(ages, size=total_n, p=INITIAL_AGE_DISTRIBUTION)
        
        # 性別はオス・メスを 50:50 で割り当てる
        assigned_genders = np.random.choice(["M", "F"], size=total_n)

        # =========================================================
        # 2. 年齢ごとにクマを生成し、属性を割り当てる
        # =========================================================
        # ※子グマ（0歳、1歳）は、後で母グマに紐づけるために一時的にリストに分けておきます
        orphaned_cubs = []

        for age, gender in zip(assigned_ages, assigned_genders):
            idx = np.random.randint(0, num_forest)
            x, y = int(forest_x[idx]), int(forest_y[idx])

            bear = Bear(
                bid_counter, age=age, gender=gender,
                x=x, y=y, config=self.config
            )
            bid_counter += 1

            # --- 年齢による属性の振り分け ---
            if age <= 1:
                # 0歳・1歳の子グマ（とりあえず孤児としてリストに追加）
                orphaned_cubs.append(bear)
            
            elif age >= 4 and gender == "F":
                # 成獣メス（一定確率で子連れ母グマになる）
                # ※子グマはすでに orphaned_cubs にプールされているので、そこから引き取る形にします
                bear.repro_status = "NORMAL"
                bears.append(bear)
            
            else:
                # 成獣オス、若獣（2〜3歳）、子を持たない成獣メス
                bears.append(bear)

        # =========================================================
        # 3. 孤児の子グマ（0〜1歳）を成獣メスに紐づける（改良版）
        # =========================================================
        # リストにいる成獣メス（4歳以上）を抽出
        adult_females = [b for b in bears if b.gender == "F" and b.age >= 4]

        for cub in orphaned_cubs:
            # まだ子グマを2頭未満しか持っていない母グマ候補を絞り込む
            available_mothers = [m for m in adult_females if m.cub_count < 2]
            
            if not available_mothers:
                # 候補がいなければ単独でリストへ（自然界の孤児）
                bears.append(cub)
                continue
            
            # ランダムな母グマ候補を1頭選ぶ
            mother = np.random.choice(available_mothers)
            
            # 母グマと子グマのリンク処理
            cub.mother_id = mother.id
            cub.x, cub.y = mother.x, mother.y # 位置を母親に合わせる
            mother.repro_status = "LACTATING"
            mother.cub_count += 1
            
            # 紐づけが終わった子グマを全体のリストに戻す
            bears.append(cub)

        return bears
    
    def calculate_human_caused_mortality(self, bear):
        """人里への出没に伴う人為的死亡（捕殺・駆除）の判定"""
        # 人里にいない、または既に死亡している場合は判定しない
        if bear.stay_urban_counts == 0 or (not bear.is_alive):
            return False

        landuse = int(self.env[0, bear.y, bear.x])
        pop = float(self.env[2, bear.y, bear.x])

        # Configと定数の読み込み
        pop_k = self.config.kill_pop_k
        lu_hazard = LANDUSE_HAZARD_WEIGHTS.get(landuse, DEFAULT_HAZARD_WEIGHT)

        # 1. 人口リスク：基本の罠リスク + (人口の対数 × 推定係数)
        # ※限界集落(pop=0)でも BASE_TRAP_RISK により最低限の罠リスクは存在する
        pop_risk = BASE_TRAP_RISK + (np.log1p(pop) * pop_k)

        # 2. 最終確率の計算（上限値でクリップ）
        # ※滞在日数による倍率(duration_factor)を撤廃。
        # 毎日同じ確率が適用されるが、滞在日数が延びるほど累積の死亡率は自然に高まる。
        final_prob = min(MAX_HUMAN_KILL_PROB, pop_risk * lu_hazard)

        # 確率判定（死亡）
        if np.random.random() < final_prob:
            bear.is_alive = False
            bear.death_cause = "HUMAN"
            return True
            
        return False

    def process_incremental_independence(self, day):
        """子グマの段階的な親離れ（独立）処理"""
        # 夏の開始日（Day 182）より前は親離れしない（定数を再利用！）
        if day < SUMMER_START_DAY:
            return
            
        for bear in self.bears:
            # 対象：生存している独立年齢（1歳）の非独立個体
            if bear.age == INDEPENDENCE_AGE and (not bear.is_independent) and bear.mother_id != -1 and bear.is_alive:
                
                # 毎日の一定確率で親離れが発生
                if np.random.random() < DAILY_INDEPENDENCE_PROB:
                    bear.is_independent = True
                    
                    mother = self.get_bear_by_id(bear.mother_id)
                    bear.mother_id = -1
                    
                    if mother:
                        # 他にまだ独立していない兄弟（同腹子）がいるか確認
                        other_cubs = [
                            b for b in self.bears
                            if b.mother_id == mother.id and (not b.is_independent) and b.is_alive
                        ]
                        # 兄弟が全員独立したら、母グマは子育てを終えて通常ステータス（次の繁殖が可能）に戻る
                        if len(other_cubs) == 0:
                            mother.repro_status = "NORMAL"
                            mother.cub_count = 0

    def process_end_of_year(self):
        """
        1年の終わり（12/31など）に全個体の年齢・ステータスを更新する。
        将来の複数年シミュレーションに向けた年越し処理。
        """
        for bear in self.bears:
            # 既に死亡している個体はスキップ
            if not bear.is_alive:
                continue

            # 1. 全員等しく年齢を +1
            bear.age += 1

            # 2. 寿命（老衰）の判定
            # 定数（MAX_LIFESPAN）を超えたら自然死とする
            if bear.age > MAX_LIFESPAN:
                bear.is_alive = False
                bear.death_cause = "OLD_AGE"
                continue

            # 3. 年齢に応じたライフステージ（age_class）の昇格処理
            if bear.age == AGE_CLASS_YEARLING:
                # 0歳 -> 1歳（当歳子から1歳子へ）
                bear.age_class = "Yr"

            elif bear.age == AGE_CLASS_SUBADULT:
                # 1歳 -> 2歳（若獣へ昇格）
                bear.age_class = "Su"
                
                # 【フェイルセーフ】
                # 夏の独立処理（process_incremental_independence）で確率の網目を
                # 潜り抜けて独立しそびれていた場合でも、2歳になったら強制的に完全独立させる
                if not bear.is_independent:
                    bear.is_independent = True
                    bear.mother_id = -1

            elif bear.age == AGE_CLASS_ADULT:
                # 3歳 -> 4歳（成獣へ昇格）
                bear.age_class = "Ad"
                
            # ※ 5歳以上などは "Ad" のままなので何もしない

    def process_orphans(self):
        """
        母親が死亡した非独立個体（孤児）の処理。
        毎日、全個体の行動が終わった後などに呼び出す。
        """
        for bear in self.bears:
            # 既に死亡している、独立済み、またはそもそも母親が設定されていない個体はスキップ
            if (not bear.is_alive) or bear.is_independent or bear.mother_id == -1:
                continue

            mother = self.get_bear_by_id(bear.mother_id)
            
            # 母親がシステム上に存在しない、または「死亡」している場合
            if mother is None or not mother.is_alive:
                
                # 0歳（当歳子）は自活できず死亡する
                if bear.age < ORPHAN_SURVIVAL_AGE:
                    bear.is_alive = False
                    bear.death_cause = "ORPHANED"  # 死因：孤児化（餓死/捕食）
                
                # 1歳以上（1歳子）は強制的に独立して生き延びる
                else:
                    bear.is_independent = True
                    bear.mother_id = -1

    def process_mating(self, day):
        """交尾期における繁殖行動（ステータス変更）の処理"""
        # 定数を使って交尾期かどうかを判定
        if not (MATING_START_DAY <= day <= MATING_END_DAY):
            return

        # 同じセルにいる個体をまとめる辞書
        pos_map = {}
        for bear in self.bears:
            # 生存かつ独立済みの個体を収集
            if bear.is_alive and bear.is_independent:
                pos_map.setdefault((bear.x, bear.y), []).append(bear)

        # 各セルごとに交尾判定
        for residents in pos_map.values():
            if len(residents) < 2:
                continue
                
            # 成獣オスと、繁殖可能な成獣メスを抽出
            males = [b for b in residents if b.gender == "M" and b.age_class == "Ad"]
            females = [b for b in residents if b.gender == "F" and b.age_class == "Ad" and b.repro_status == "NORMAL"]
            
            # 両方が揃っていれば交尾イベント発生
            if males and females:
                for female in females:
                    # 定数の確率で交尾成功（MATEDへ移行）
                    if np.random.random() < MATING_SUCCESS_PROB:
                        female.repro_status = "MATED"

    def move_all_bears(self, day, temp, precip):
        """強者順に、行動→移動→更新→死亡判定→依存個体同期を行う1日のメインループ"""
        self.current_temp = float(temp)
        self.current_precip = float(precip)
        
        # ★改善1：Config連動の爆速メソッドでマップ全体の資源を回復
        self.recover_resources()

        next_world_map = {}

        # 親子関係辞書（mother_id -> [child,...]）
        children_map = {}
        for b in self.bears:
            if b.is_alive and (not b.is_independent) and (b.mother_id != -1):
                children_map.setdefault(b.mother_id, []).append(b)

        # 独立・生存個体のみ、第1条件:ランク(降順)、第2条件:エネルギー(降順) でソート
        sorted_bears = sorted(
            [b for b in self.bears if b.is_alive and b.is_independent],
            key=lambda b: (b.get_dominance_rank(), b.energy),
            reverse=True
        )

        for bear in sorted_bears:
            # 毎日 prev を更新するため、「今日の開始時点の位置」を退避
            old_x, old_y = bear.x, bear.y

            dx, dy = 0, 0
            action = bear.mode

            # --- 1. 行動の決定と移動 ---
            if bear.mode == HIBERNATION:
                woke = bear.check_wakeup(day, self.current_temp)
                if not woke:
                    bear.update_energy_hibernation()
                action = bear.mode
                dx, dy = 0, 0
            else:
                bear.decide_action(day, self.current_temp, self.current_precip)

                if bear.mode == MOVING:
                    dx, dy = bear.decide_destination(day, self, next_world_map)
                    bear.x = int(np.clip(bear.x + dx, 0, X_SIZE - 1))
                    bear.y = int(np.clip(bear.y + dy, 0, Y_SIZE - 1))
                else:
                    dx, dy = 0, 0

                # エネルギー更新と冬眠チェック
                bear.update_energy(bear.mode, dx, dy, self, day)
                lu = int(self.env[0, bear.y, bear.x])
                current_mast_factor = MAST_LEVEL_FACTORS[self.mast_level]
                bear.check_hibernation(day, self.current_temp, lu, current_mast_factor)

            # 移動しない日も含めて prev を更新（「昨日位置」を保持する）
            bear.prev_x, bear.prev_y = old_x, old_y

            # --- 2. 経験更新と人為的死亡（捕殺）判定 ---
            if bear.is_alive:
                lu_at_pos = int(self.env[0, bear.y, bear.x])
                bear.update_stay_urban_counts(lu_at_pos)
                bear.update_total_experience(lu_at_pos)
                self.calculate_human_caused_mortality(bear)

            # --- 3. 競合判定用マップへの登録 ---
            if bear.is_alive:
                pos = (bear.x, bear.y)
                next_world_map.setdefault(pos, []).append({
                    "id": bear.id,
                    "rank": bear.get_dominance_rank(),
                    "age_class": bear.age_class,
                    "gender": bear.gender,
                    "repro_status": bear.repro_status
                })

                # --- 4. 非独立の子グマ（Cu, Yr）の同期 ---
                my_children = children_map.get(bear.id, [])
                for child in my_children:
                    # 子の開始位置も保持して prev 更新したいので退避
                    child_old_x, child_old_y = child.x, child.y

                    # 母親と同じ位置・モードに同期
                    child.x, child.y = bear.x, bear.y
                    child.mode = bear.mode

                    child.update_energy(
                        action=bear.mode,
                        dx=dx,
                        dy=dy,
                        world=self,
                        day=day
                    )

                    # 子も prev を毎日更新
                    child.prev_x, child.prev_y = child_old_x, child_old_y

                    if child.is_alive:
                        lu_at_pos_child = int(self.env[0, child.y, child.x])
                        child.update_stay_urban_counts(lu_at_pos_child)
                        child.update_total_experience(lu_at_pos_child)
                        self.calculate_human_caused_mortality(child)

            # --- 5. 資源の消費（枯渇）処理 ---
            # 強者から順に消費するため、同じ場所に来た弱者はエサにありつけない
            if bear.mode == FORAGING:
                # ★改善2：不要になった引数(day)を削除
                self.consume_resources(bear.x, bear.y)

        # --- 6. 孤児の処理 ---
        # ★改善3：先ほど作成した堅牢な孤児判定メソッドに一任する
        self.process_orphans()




# --- 入出力パス ---
VEG_CSV = r"G:\マイドライブ\クマ出没予測\試作\ABM_2\vegetation_gain_table.csv"
WEATHER_CSV = r"G:\マイドライブ\クマ出没予測\試作\ABM_2\wether_akita_2025.csv"
ENV_NPY = r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\env_data.npy"

# （※START_DAY, END_DAY, NUM_ENSEMBLE, OUTPUT_BUFFER_DAYS 等の定数は上部で定義されている前提です）


def flush_buffer_to_csv(buffer_rows, output_csv, first_write):
    """バッファをまとめてCSVに書き出し、first_writeを更新して返す"""
    if not buffer_rows:
        return first_write
    df = pd.DataFrame.from_records(buffer_rows)
    df.to_csv(output_csv, mode="a", header=first_write, index=False, encoding="utf-8-sig")
    buffer_rows.clear()
    return False

def run_single_simulation(ensemble_id: int, config: SimConfig = None, mast_level: str = "Great", initial_pop_size: int = 1504, write_csv: bool = False):
    print(f"Starting Ensemble {ensemble_id}...")

    if config is None:
        config = SimConfig()

    env_data = np.load(ENV_NPY)  # shape: (5, Y, X)
    env_data = np.nan_to_num(env_data, nan=0.0).astype(np.float32, copy=False)

    weather_df = pd.read_csv(WEATHER_CSV)
    weather_table = weather_df[["temp", "precip"]].values

    world = World(
        world_id=ensemble_id,
        env_data=env_data,
        veg_csv_path=VEG_CSV,
        initial_pop_size=initial_pop_size,
        mast_level=mast_level,
        config=config
    )

    output_csv = f"result_ensemble_{ensemble_id}_{initial_pop_size}_{mast_level}.csv"
    if write_csv:
        if os.path.exists(output_csv):
            os.remove(output_csv)

    first_write = True
    buffer_rows = []
    buffer_day_counter = 0

    # ========================================================
    # ★Optuna評価用の集計リスト（すべて12ヶ月分の0初期化リスト）
    # ※インデックス0が1月、インデックス11が12月を表します
    # ========================================================
    monthly_urban_appearances = [0] * 12
    monthly_urban_lactating = [0] * 12
    monthly_human_kills = [0] * 12
    monthly_energy_sum = [0.0] * 12
    monthly_days_count = [0] * 12
    
    # 【追加】捕殺された個体の年齢カウント用（0歳〜20歳以上の 21要素リスト）
    killed_ages_count = [0] * 21

    known_dead_bears = set()  # 重複カウント防止用

    # 開始時点の総個体数と内訳を取得（指標4と5で使用）
    initial_cu_count = sum(1 for b in world.bears if b.age == 0)
    initial_non_cu_count = sum(1 for b in world.bears if b.age > 0)
    initial_total_bears = initial_cu_count + initial_non_cu_count
    
    annual_natural_deaths = 0

    for day in range(START_DAY, END_DAY + 1):
        temp = float(weather_table[day - 1, 0])
        precip = float(weather_table[day - 1, 1])

        # メイン処理
        world.move_all_bears(day, temp, precip)

        if day >= SUMMER_START_DAY:
            world.process_incremental_independence(day)
        if MATING_START_DAY <= day <= MATING_END_DAY:
            world.process_mating(day)
        if day == 365:
            world.process_end_of_year()
        
        # カレンダーの「月」を計算
        current_date = SIMULATION_START_DATE + datetime.timedelta(days=day - 1)
        # リストのインデックス（0〜11）に変換
        m_idx = current_date.month - 1 

        alive_bears_count = 0
        daily_energy_total = 0.0

        for b in world.bears:
            # CSVバッファ追加
            if write_csv:
                buffer_rows.append({
                    "day": day,
                    "bear_id": b.id,
                    "x": b.x,
                    "y": b.y,
                    "mode": b.mode,
                    "energy": b.energy,
                    "age_class": b.age_class,
                    "age": b.age,
                    "gender": b.gender,
                    "repro_status": b.repro_status,
                    "cub_count": b.cub_count,
                    "is_independent": b.is_independent,
                    "is_alive": b.is_alive,
                    "death_cause": b.death_cause
                })

            # --- 生存個体の集計 ---
            if b.is_alive:
                alive_bears_count += 1
                daily_energy_total += b.energy

                lu = int(world.env[0, b.y, b.x])
                if lu in URBAN_LANDUSE_CODES:
                    # 【指標1】目撃数トレンド
                    monthly_urban_appearances[m_idx] += 1
                    
                    # 【指標2】親子連れトレンド
                    if b.repro_status == "LACTATING":
                        monthly_urban_lactating[m_idx] += 1

            # --- 死亡個体の集計 ---
            else:
                if b.id not in known_dead_bears:
                    known_dead_bears.add(b.id)
                    
                    # 【指標3＆6＆7】人為的死亡（捕殺）
                    if b.death_cause == "HUMAN":
                        monthly_human_kills[m_idx] += 1
                        
                        # 死亡時の年齢を記録（20歳以上はすべてインデックス20にまとめる）
                        age_idx = min(int(b.age), 20)
                        killed_ages_count[age_idx] += 1
                        
                    # 【指標5】自然死亡
                    elif b.death_cause in ["ENERGY", "ORPHANED", "OLD_AGE"]:
                        annual_natural_deaths += 1

        # 【指標6】その日の「集団の平均エネルギー」を加算
        if alive_bears_count > 0:
            monthly_energy_sum[m_idx] += (daily_energy_total / alive_bears_count)
        monthly_days_count[m_idx] += 1

        buffer_day_counter += 1

        # 指定日数ごとにフラッシュ
        if write_csv and buffer_day_counter >= OUTPUT_BUFFER_DAYS:
            first_write = flush_buffer_to_csv(buffer_rows, output_csv, first_write)
            buffer_day_counter = 0

        # 進捗の表示
        if day % 30 == 0:
            print(f"Ensemble {ensemble_id}: Day {day}, Alive Bears: {alive_bears_count}")

    # 最後の残りをフラッシュ
    if write_csv:
        first_write = flush_buffer_to_csv(buffer_rows, output_csv, first_write)

    # ========================================================
    # ★ ループ終了後：Optunaで評価しやすい形に最終計算
    # ========================================================

    # 1. 月別目撃数トレンド
    sighting_trend = monthly_urban_appearances

    # 2. 月別親子連れ割合
    family_ratio = [
        (monthly_urban_lactating[i] / sighting_trend[i]) if sighting_trend[i] > 0 else 0.0 
        for i in range(12)
    ]

    # 3. 月別捕殺数トレンド
    kill_trend = monthly_human_kills

    # 4. 年間捕殺割合（総捕殺数 ÷ 初期総個体数）
    total_kills = sum(kill_trend)
    annual_kill_rate = (total_kills / initial_total_bears) if initial_total_bears > 0 else 0.0

    # 5. 内的自然増加率
    if initial_non_cu_count > 0:
        intrinsic_growth_rate = (initial_cu_count - annual_natural_deaths) / initial_non_cu_count + 1.0
    else:
        intrinsic_growth_rate = 1.0

    # 6. 月別エネルギー収支トレンド
    energy_trend = [
        (monthly_energy_sum[i] / monthly_days_count[i]) if monthly_days_count[i] > 0 else 0.0 
        for i in range(12)
    ]

    # 7. 捕殺個体の齢分布（割合に変換）
    if total_kills > 0:
        kill_age_distribution = [count / total_kills for count in killed_ages_count]
    else:
        # 1頭も捕殺されなかった場合のフォールバック（0埋め）
        kill_age_distribution = [0.0] * 21

    # まとめて評価指標として返す
    metrics = {
        "sighting_trend": sighting_trend,
        "family_ratio": family_ratio,
        "kill_trend": kill_trend,
        "annual_kill_rate": annual_kill_rate,
        "intrinsic_growth_rate": intrinsic_growth_rate,
        "energy_trend": energy_trend,
        "kill_age_distribution": kill_age_distribution
    }

    return f"Ensemble {ensemble_id} completed.", metrics

# --- 【並列実行用ラッパー関数】 ---
# pool.map は引数を1つしか渡せないため、タプルで受け取る関数を用意しておきます。
def wrapper_run_single_simulation(args):
    ensemble_id, config = args
    return run_single_simulation(ensemble_id, config)

if __name__ == "__main__":
    num_cpu = os.cpu_count() or 1
    num_processes = max(1, min(NUM_ENSEMBLE, max(1, num_cpu - 1)))

    print(f"Running {NUM_ENSEMBLE} ensembles using {num_processes} processes...")

    current_config = SimConfig() 
    tasks = [(i, current_config) for i in range(NUM_ENSEMBLE)]

    with Pool(processes=num_processes) as pool:
        # wrapper関数を使って並列処理
        results = pool.map(wrapper_run_single_simulation, tasks)

    print("All simulations completed.")

    all_ensemble_metrics = []

    for r, metrics in results:
        print(r)
        all_ensemble_metrics.append(metrics)