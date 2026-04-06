import optuna
import numpy as np
from scipy.stats import pearsonr
import sys

# =========================================================
# 1. シミュレーション本体からのインポート
# =========================================================
# ※ABM_akita_1year_param.py が同じフォルダにある前提です
import ABM_param_estimation as abm

# =========================================================
# 2. 評価用ヘルパー関数（Loss計算）
# =========================================================
def calc_pearson_loss(target_list, sim_list):
    """
    ピアソンの相関係数を用いて「波形のズレ」をペナルティ（Loss）に変換する関数。
    完全に一致(相関1.0)ならLoss=0.0、逆相関(-1.0)ならLoss=2.0になります。
    """
    target_arr = np.array(target_list)
    sim_arr = np.array(sim_list)
    
    # どちらかが完全に平坦（標準偏差0）だと相関係数が計算できずエラーになるための安全装置
    if np.std(target_arr) == 0 or np.std(sim_arr) == 0:
        return 2.0  # 最悪のペナルティを返す
        
    corr, _ = pearsonr(target_arr, sim_arr)
    
    # 相関係数(corr)は -1.0 〜 1.0 の値をとる。
    # これを最小化問題（Loss）にするため、(1.0 - corr) とする。
    loss = 1.0 - corr
    return loss

def calc_mse_loss(target_val, sim_val):
    """
    絶対的な規模（割合やスカラー値）のズレを計算する関数（平均二乗誤差）。
    """
    return (target_val - sim_val) ** 2

def calc_range_loss(target_range, sim_val):
    """
    シミュレーション結果が目標レンジ(min, max)から外れた場合のみ、
    そのハミ出した距離の2乗をペナルティとして返す。
    """
    target_min, target_max = target_range
    if sim_val < target_min:
        return (target_min - sim_val) ** 2
    elif sim_val > target_max:
        return (sim_val - target_max) ** 2
    else:
        return 0.0 # 範囲内ならペナルティ無し

# =========================================================
# 3. Optunaの目的関数（Objective）
# =========================================================
def objective(trial):
    # -----------------------------------------------------
    # ① AIに試させる13個のパラメータを定義（範囲は要調整）
    # -----------------------------------------------------
    config = abm.SimConfig(
        # energy_cost_alpha = trial.suggest_float("energy_cost_alpha", 0.5, 2.0),
        starvation_mortality_k = trial.suggest_float("starvation_mortality_k", 0.00005, 0.001, log=True),
        wakeup_k_temp = trial.suggest_float("wakeup_k_temp", 0.02, 0.2),
        hibernation_k_temp = trial.suggest_float("hibernation_k_temp", 0.01, 0.2),
        hunger_radius_k = trial.suggest_float("hunger_radius_k", 0.5, 5.0),
        base_avoidance_k = trial.suggest_float("base_avoidance_k", 0.5, 20.0),
        urban_habituation_k = trial.suggest_float("urban_habituation_k", 0.01, 0.2),
        decision_softmax_beta = trial.suggest_float("decision_softmax_beta", 0.05, 10.0, log=True),
        resource_recovery_rate = trial.suggest_float("resource_recovery_rate", 0.01, 0.5),
        kill_pop_k = trial.suggest_float("kill_pop_k", 0.0001, 0.1, log=True),
        autumn_panic_offset = trial.suggest_float("autumn_panic_offset", 5.0, 40.0),
        # lactating_cost_mult = trial.suggest_float("lactating_cost_mult", 1.0, 2.0)
    )

    total_loss = 0.0

    # -----------------------------------------------------
    # ② 【豊作年シナリオ】の実行と評価
    # -----------------------------------------------------
    # ABM側のグローバル変数（環境設定）を上書きして豊作モードにする
    _, metrics_good = abm.run_single_simulation(
        ensemble_id=1, 
        config=config,
        mast_level="Great",
        initial_pop_size=2500
    )

    # Loss計算（波形トレンド）
    total_loss += calc_pearson_loss(abm.TARGET_DATA["good_mast"]["sighting_trend"], metrics_good["sighting_trend"])
    total_loss += calc_pearson_loss(abm.TARGET_DATA["good_mast"]["family_ratio"], metrics_good["family_ratio"])
    total_loss += calc_pearson_loss(abm.TARGET_DATA["good_mast"]["kill_trend_tohoku"], metrics_good["kill_trend"])
    
    # Loss計算（5〜11月のエネルギー収支波形）
    target_energy_good = abm.TARGET_DATA["good_mast"]["energy_trend"][4:11]
    sim_energy_good = metrics_good["energy_trend"][4:11]
    total_loss += calc_pearson_loss(target_energy_good, sim_energy_good) * 0.5

    # Loss計算（規模とスカラー値）
    total_loss += calc_mse_loss(abm.TARGET_DATA["good_mast"]["annual_kill_rate_akita"], metrics_good["annual_kill_rate"]) * 10.0 # 重要なので重み付け

    # 【豊作年】の自然増加率の評価（Loss計算のブロックに追加）
    total_loss += calc_range_loss(abm.TARGET_DATA["good_mast"]["lambda_range"], metrics_good["intrinsic_growth_rate"]) * 10.0
    
    # -----------------------------------------------------
    # ③ 【凶作年シナリオ】の実行と評価
    # -----------------------------------------------------
    # ABM側のグローバル変数を上書きして凶作モードにする
    _, metrics_poor = abm.run_single_simulation(
        ensemble_id=2, 
        config=config,
        mast_level="Poor",
        initial_pop_size=2500
    )

    # Loss計算（波形トレンド）
    total_loss += calc_pearson_loss(abm.TARGET_DATA["poor_mast"]["sighting_trend"], metrics_poor["sighting_trend"])
    total_loss += calc_pearson_loss(abm.TARGET_DATA["poor_mast"]["family_ratio"], metrics_poor["family_ratio"])
    total_loss += calc_pearson_loss(abm.TARGET_DATA["poor_mast"]["kill_trend_tohoku"], metrics_poor["kill_trend"])
    
    # Loss計算（5〜11月のエネルギー収支波形）
    target_energy_poor = abm.TARGET_DATA["poor_mast"]["energy_trend"][4:11]
    sim_energy_poor = metrics_poor["energy_trend"][4:11]
    total_loss += calc_pearson_loss(target_energy_poor, sim_energy_poor) * 0.5

    # Loss計算（規模とスカラー値）
    total_loss += calc_mse_loss(abm.TARGET_DATA["poor_mast"]["annual_kill_rate_akita"], metrics_poor["annual_kill_rate"]) * 10.0

    # 【凶作年】の自然増加率の評価（Loss計算のブロックに追加）
    total_loss += calc_range_loss(abm.TARGET_DATA["poor_mast"]["lambda_range"], metrics_poor["intrinsic_growth_rate"]) * 10.0

    # -----------------------------------------------------
    # ④ 【共通】年齢分布の評価（豊作・凶作の平均で評価）
    # -----------------------------------------------------
    # 豊作と凶作で得られた年齢分布リストを平均する
    sim_age_dist_avg = [(g + p) / 2.0 for g, p in zip(metrics_good["kill_age_distribution"], metrics_poor["kill_age_distribution"])]
    
    # 各年齢(0〜20歳)の割合のズレの2乗をすべて足し合わせる
    loss_age = sum(calc_mse_loss(t, s) for t, s in zip(abm.TARGET_DATA["common"]["kill_age_distribution"], sim_age_dist_avg))
    total_loss += loss_age * 5.0 # 分布の一致も重要なので重み付け

    # 全指標の合計ペナルティをAIに返す！
    return total_loss

# =========================================================
# 4. メイン実行ブロック
# =========================================================
if __name__ == "__main__":
    print("=== Optuna Parameter Estimation Started ===")
    
    # データベースに結果を保存しながら進める設定（中断しても再開可能）
    study = optuna.create_study(
        study_name="bear_abm_study_v4", 
        direction="minimize",
        storage="sqlite:///bear_optuna_v4.db", # SQLiteファイルに保存
        load_if_exists=True
    )
    
    # 試行回数を設定して最適化スタート（まずはテストで20回程度がおすすめ）
    study.optimize(objective, n_trials=100, n_jobs=-1)
    
    print("\n=== Optimization Finished ===")
    print("Best Trial (Lowest Loss):", study.best_trial.value)
    print("Best Parameters:")
    for key, value in study.best_params.items():
        print(f"  {key}: {value}")