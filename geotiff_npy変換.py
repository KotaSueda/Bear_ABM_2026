# import rasterio
# import numpy as np

# def convert_tifs_to_numpy(tif_files, output_name=r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\env_data.npy"):
#     combined_data = []
    
#     for f in tif_files:
#         with rasterio.open(f) as src:
#             # データを読み込み (1, 761, 877)
#             data = src.read(1)
            
#             # NoData値（-9999や-3.4e38）を、計算しやすい値に統一
#             # ここでは後の計算を考慮して NaN (float32) に統一
#             data = data.astype(np.float32)
#             data[data == src.nodata] = np.nan
            
#             combined_data.append(data)
#             print(f"Loaded: {f} | Shape: {data.shape}")

#     # (5, 761, 877) の3次元配列にスタック
#     env_array = np.stack(combined_data)
    
#     # NumPy形式で保存
#     np.save(output_name, env_array)
#     print(f"\nSaved successfully: {output_name}")
#     print(f"Final shape: {env_array.shape}")

# # QGISで作成したファイルリスト（順番が重要）
# target_files = [
#     r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\landuse_mask.tif",    # index 0
#     r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\shokusei_mask.tif",   # index 1
#     r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\population_mask.tif", # index 2
#     r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\elevation_mask.tif",  # index 3
#     r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\slopemax_mask.tif"    # index 4
# ]

# convert_tifs_to_numpy(target_files)



# import geopandas as gpd
# import rasterio
# from rasterio.features import rasterize
# import numpy as np
# import os

# # --- 設定部分 ---

# # 1. テンプレートとなるラスタデータ（前回作成したもの）
# # ※このファイルの「位置」と「マス目のサイズ」に合わせて型抜きします
# template_tif = r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\landuse_raster.tif"

# # 2. 出力するnpyファイルのパス
# output_npy = r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\pref_code.npy"

# # 3. 各県のshpファイルパスと、割り当てる値（1〜5）の対応表
# # ※フォルダのベースパスを設定しておき、コードをすっきりさせます
# base_dir = r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\東北版\行政区域"

# pref_files = {
#     1: os.path.join(base_dir, r"N03-20250101_02_GML\N03-20250101_02.shp"), # 青森
#     2: os.path.join(base_dir, r"N03-20250101_03_GML\N03-20250101_03.shp"), # 岩手
#     3: os.path.join(base_dir, r"N03-20250101_04_GML\N03-20250101_04.shp"), # 宮城
#     4: os.path.join(base_dir, r"N03-20250101_05_GML\N03-20250101_05.shp"), # 秋田
#     5: os.path.join(base_dir, r"N03-20250101_06_GML\N03-20250101_06.shp")  # 山形
# }

# # --- 処理部分 ---

# print("テンプレートとなるラスタの空間情報を取得中...")
# with rasterio.open(template_tif) as src:
#     transform = src.transform
#     width = src.width
#     height = src.height
#     target_crs = src.crs

# shapes = []

# # 各県のファイルを順番に読み込んで図形を取り出す
# for code, file_path in pref_files.items():
#     print(f"[{code}] {os.path.basename(file_path)} を読み込み中...")
    
#     # ベクタデータの読み込み
#     gdf = gpd.read_file(file_path)
    
#     # 座標系(CRS)がテンプレートと異なる場合は、自動で合わせて変形する
#     if gdf.crs != target_crs:
#         print(f"  -> 座標系をテンプレート(EPSG:2450)に変換します...")
#         gdf = gdf.to_crs(target_crs)
        
#     # その県のすべてのポリゴンに、対応するコード(1〜5)を割り当ててリストに追加
#     shapes.extend([(geom, code) for geom in gdf.geometry])

# print("\nラスタライズ（画像化）を実行中...")
# # 背景（海や他県など、ポリゴンがない場所）は自動的に「0」になります
# burned_array = rasterize(
#     shapes=shapes,
#     out_shape=(height, width),
#     transform=transform,
#     fill=0, 
#     all_touched=False, # Trueにすると境界線のピクセルが少し太くなります（通常はFalseでOK）
#     dtype=np.int32
# )

# # npyとして保存
# np.save(output_npy, burned_array)
# print(f"完了！ 保存先: {output_npy}")
# print(f"作成された配列のShape: {burned_array.shape}")



# import geopandas as gpd
# import rasterio
# from rasterio.features import rasterize
# from rasterio.transform import from_origin
# import numpy as np
# import os
# import pandas as pd  # ★追加：欠損値判定に使用します

# # --- 設定部分 ---

# dir_path = r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ"

# # ※QGISで修復したファイル名に合わせてください
# file_shokusei = os.path.join(dir_path, "植生統合_fixed.gpkg") 
# file_pop = os.path.join(dir_path, "境界統合結合.gpkg")
# file_landuse = os.path.join(dir_path, "landuse_marge.gpkg")

# resolution = 100.0 
# NODATA_VALUE = -9999

# # --- 処理部分 ---

# print("ベクタレイヤを読み込んでいます...")
# gdf_shokusei = gpd.read_file(file_shokusei)
# gdf_pop = gpd.read_file(file_pop)
# gdf_landuse = gpd.read_file(file_landuse)

# print("人口データのカラム一覧:", gdf_pop.columns)

# # 全体範囲を取得して統合
# minx1, miny1, maxx1, maxy1 = gdf_shokusei.total_bounds
# minx2, miny2, maxx2, maxy2 = gdf_pop.total_bounds
# minx3, miny3, maxx3, maxy3 = gdf_landuse.total_bounds

# minx = min(minx1, minx2, minx3)
# miny = min(miny1, miny2, miny3)
# maxx = max(maxx1, maxx2, maxx3)
# maxy = max(maxy1, maxy2, maxy3)

# print(f"共通の解析範囲: X({minx} ~ {maxx}), Y({miny} ~ {maxy})")

# width = int(np.ceil((maxx - minx) / resolution))
# height = int(np.ceil((maxy - miny) / resolution))

# print(f"作成されるラスタのサイズ: 幅 {width} px, 高さ {height} px")

# transform = from_origin(minx, maxy, resolution, resolution)

# # ラスタライズ関数
# def vector_to_raster(gdf, value_column, output_filename):
#     print(f"{output_filename} を作成中...")
    
#     # ★修正箇所：pd.notna() を使って NaN (欠損値) を確実に弾く
#     shapes = (
#         (geom, int(val)) 
#         for geom, val in zip(gdf.geometry, gdf[value_column]) 
#         if pd.notna(val) 
#     )

#     burned_array = rasterize(
#         shapes=shapes,
#         out_shape=(height, width),
#         transform=transform,
#         fill=NODATA_VALUE, 
#         all_touched=False, 
#         dtype=rasterio.int32 
#     )

#     with rasterio.open(
#         output_filename, 'w',
#         driver='GTiff',
#         height=height, width=width,
#         count=1, dtype=str(burned_array.dtype),
#         crs=gdf.crs, 
#         transform=transform,
#         nodata=NODATA_VALUE
#     ) as out:
#         out.write(burned_array, 1)
        
#     print(f"-> {output_filename} の保存が完了しました。\n")

# # 実行
# # out_shokusei = os.path.join(dir_path, "shokusei_raster.tif")
# out_pop = os.path.join(dir_path, "population_raster.tif")
# out_landuse = os.path.join(dir_path, "landuse_raster.tif")

# # vector_to_raster(gdf_shokusei, 'shokusei', out_shokusei)
# vector_to_raster(gdf_pop, '人口統合_人口（総数）', out_pop)
# vector_to_raster(gdf_landuse, 'landuse', out_landuse)

# print("すべての処理が完了しました！")



import rasterio
from rasterio.warp import reproject, Resampling
import numpy as np
import os

# --- 設定部分 ---
# 1. テンプレートとなる100mメッシュのラスタ（前回作成したものを指定）
template_tif = r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\landuse_raster.tif"

# 2. 読み込む1kmメッシュの生息適地ラスタ（★実際のファイル名に変更してください）
input_suitability_tif = r"C:\Users\sueda\Downloads\Bear_HS_snow_11km.tif"

# 3. 出力するnpyファイルのパス
output_npy = r"G:\マイドライブ\クマ出没予測\試作\ABM_2\環境データ\initial_habitat_suitability.npy"


# --- 処理部分 ---
print("1. テンプレートの空間情報を取得しています...")
with rasterio.open(template_tif) as tmpl:
    dst_transform = tmpl.transform
    dst_crs = tmpl.crs
    dst_width = tmpl.width
    dst_height = tmpl.height

print(f"  -> ターゲットサイズ: {dst_width} x {dst_height} (100mメッシュ)")

print("\n2. 生息適地データを読み込み、100mメッシュに変換（リサンプリング）します...")
# 出力用の空の配列を作成（すべて NaN で初期化）
dest_array = np.full((dst_height, dst_width), np.nan, dtype=np.float32)

with rasterio.open(input_suitability_tif) as src:
    # 元データのNoData値を取得（設定されていなければ適当な極端な値を仮置き）
    src_nodata = src.nodata if src.nodata is not None else -9999.0
    
    # reproject関数で、1kmメッシュを100mメッシュの枠にピタリと合わせて流し込む
    reproject(
        source=rasterio.band(src, 1),
        destination=dest_array,
        src_transform=src.transform,
        src_crs=src.crs,
        src_nodata=src_nodata,
        dst_transform=dst_transform,
        dst_crs=dst_crs,
        dst_nodata=np.nan, # はみ出た部分やNoDataは np.nan にする
        # ※1kmを100mに分割する際、nearest(ニアレスト)だと10×10マスに同じ値が入り、
        # bilinear(バイリニア)だとグラデーションのように滑らかに補間されます。
        # 生息適地などの連続値は bilinear が適していることが多いです。
        resampling=Resampling.bilinear 
    )

print("\n3. データの最小値・最大値を調べて 0〜1 に正規化します...")
# NaNではない有効なデータ範囲のマスクを取得
valid_mask = ~np.isnan(dest_array)

if np.any(valid_mask):
    min_val = np.nanmin(dest_array)
    max_val = np.nanmax(dest_array)
    print(f"  -> 変換前の値の範囲: Min = {min_val:.4f}, Max = {max_val:.4f}")
    
    # 正規化の計算: (現在の値 - 最小値) / (最大値 - 最小値)
    if max_val > min_val:
        dest_array[valid_mask] = (dest_array[valid_mask] - min_val) / (max_val - min_val)
        print("  -> 0.0 〜 1.0 への正規化が完了しました。")
    else:
        # 万が一、全ての値が同じだった場合の安全対策
        dest_array[valid_mask] = 1.0
        print("  -> ※すべての有効値が同じだったため、1.0で一律に埋めました。")
else:
    print("  -> 警告: 有効なデータが一つも見つかりませんでした。")

# --- 保存処理 ---
np.save(output_npy, dest_array)
print(f"\n完了！ 保存先: {output_npy}")
print(f"作成された配列のShape: {dest_array.shape}")