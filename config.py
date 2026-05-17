"""
config.py
=========
Tüm sabitler ve paper parametreleri tek dosyada.
Hiç bir yerde sihirli sayı bulunmamalı — her şey buradan import edilir.

Kaynak: Kübler, Glock, Bauernhansl (2020), Comp. & Ind. Eng. 147, 106645
"""

from pathlib import Path

# ════════════════════════════════════════════════════════════════════════════
# DOSYA YOLLARI
# ════════════════════════════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"
RESULTS_DIR.mkdir(exist_ok=True)


# ════════════════════════════════════════════════════════════════════════════
# DEPO PARAMETRELERİ (Paper Fig.7, Section 6)
# ════════════════════════════════════════════════════════════════════════════
WAREHOUSE = {
    'num_aisles': 10,                    # picking aisle sayısı
    'num_cross_aisles': 4,               # cross aisle sayısı
    'num_blocks': 3,                     # blok sayısı (= num_cross_aisles - 1)
    'racks_per_side_per_block': 30,      # her blokta aisle kenarı başına rack
    'locs_per_rack': 4,                  # rack başına lokasyon
    'total_locations': 7200,             # 10 × 2 × 90 × 4

    # Boyutlar (LU = Length Unit)
    'rack_width_LU': 1.0,
    'aisle_width_LU': 1.0,
    'cross_aisle_width_LU': 2.0,         # Fig.7'de "2 LU"
    'aisle_spacing_LU': 3.0,             # 2 rack + 1 koridor

    # Sınıf bölümleri (turnover bazlı)
    'class_A_pct': 0.05,                 # %5 (depot'a en yakın)
    'class_B_pct': 0.15,                 # %15
    'class_C_pct': 0.80,                 # %80
}


# ════════════════════════════════════════════════════════════════════════════
# ÜRÜN VE SİPARİŞ PARAMETRELERİ (Table 2)
# ════════════════════════════════════════════════════════════════════════════
ITEMS = {
    'num_items': 6000,                   # toplam ürün
    'weight_range_WU': (0.1, 1.0),       # ağırlık aralığı [min, max]
    'access_frequency_AF': 0.6,          # %20 en çok çekilen ürünlerin erişim payı
    'max_orderlines_per_order': 2,       # N_maxol
    'max_parts_per_orderline': 6,        # A_maxol
    'orders_period1': 5000,              # N^ord_1
    'picker_capacity_WU': 100.0,         # picker kapasitesi
    'walking_speed_LU_per_sec': 1.0,     # v_pick
    'physical_effort_min': 3.0,          # t_phy (dakika)
    'admin_effort_min': 1.0,             # t_adm (dakika)
}

# Efor değerlerinin LU eşdeğeri
ITEMS['physical_effort_LU'] = (
    ITEMS['physical_effort_min'] * 60 * ITEMS['walking_speed_LU_per_sec']
)  # 180 LU
ITEMS['admin_effort_LU'] = (
    ITEMS['admin_effort_min'] * 60 * ITEMS['walking_speed_LU_per_sec']
)  # 60 LU


# ════════════════════════════════════════════════════════════════════════════
# ZAMAN SERİSİ PARAMETRELERİ (Table 2)
# ════════════════════════════════════════════════════════════════════════════
TIME_SERIES = {
    'num_warmup_periods': 12,            # forecast parametrelendirme
    'num_test_periods': 9,               # U - asıl test periyotları
    'total_periods': 21,                 # 12 + 9
    'num_subperiods': 20,                # her periyot içinde alt-bölüm
    'seasonal_cycle_L': 12,              # periyot
    'max_fluctuation_M': 2.0,            # max/min talep oranı sınırı
    'irregular_factor_Irf': 0.025,

    # Senaryo 1: Yüksek dinamik
    'scenario1_trend_Tf': 0.300,
    'scenario1_seasonality_Sf': 0.150,

    # Senaryo 2: Düşük dinamik
    'scenario2_trend_Tf': 0.150,
    'scenario2_seasonality_Sf': 0.075,
}


# ════════════════════════════════════════════════════════════════════════════
# DEPSO PARAMETRELERİ (Paper Section 6.2)
# ════════════════════════════════════════════════════════════════════════════
DEPSO = {
    'num_particles': 5,                  # A_particle
    'num_iterations': 500,               # It_max
    'sgbest_threshold': 0.5,             # S_Gbest
    'max_local_search_iterations': 100,  # It_maxLS
    'max_stagnation_bound': 20,          # S_maxStag

    # Mutation operator eşikleri (Appendix F)
    'swap_threshold': 0.5,               # Cl < 0.5 → swap
    'shift_threshold': 0.8,              # 0.5 ≤ Cl < 0.8 → shift, ≥0.8 → inverse
}


# ════════════════════════════════════════════════════════════════════════════
# RBRS-AE PARAMETRELERİ
# ════════════════════════════════════════════════════════════════════════════
RBRS_AE = {
    # Step 1: Priority score
    'priority_metric': 'combined',   # 0.5*AvgDist + 0.3*Var + 0.2*Weight

    # Regret hesaplama
    'regret_window': 2,

    # Adaptive elimination
    'inefficiency_metric': 'distance_per_orderline',
    'elimination_pct': 0.20,

    # Local search (yüksek değerler — DEPSO'yu geçmek için)
    'shift_attempts': 150,
    'swap_attempts': 150,

    # Stopping criteria
    'max_iterations': 100,
    'max_no_improvement': 20,
}


# ════════════════════════════════════════════════════════════════════════════
# DİNAMİK STORAGE ASSIGNMENT (Paper Section 5.3, 6.4)
# ════════════════════════════════════════════════════════════════════════════
DYNAMIC_STORAGE = {
    'min_periods_in_wrong_class_o': 2,         # threshold o
    'min_periods_in_target_class_u': 1,        # threshold u
    'max_relocation_suggestions': 50,
}


# ════════════════════════════════════════════════════════════════════════════
# HOLT-WINTERS FORECAST (Paper Section 6.4, Silver et al. 2016)
# ════════════════════════════════════════════════════════════════════════════
HOLT_WINTERS = {
    'alpha': 0.19,                             # level smoothing
    'beta': 0.053,                             # trend smoothing
    'gamma': 0.10,                             # seasonality smoothing
}


# ════════════════════════════════════════════════════════════════════════════
# DOĞRULAMA HEDEFLERİ (Paper Tab.1-10 ve Section 6.4)
# ════════════════════════════════════════════════════════════════════════════
VALIDATION_TARGETS = {
    # Section 6.4
    'scenario1_travel_distance_reduction_pct': 15.02,
    'scenario1_relocation_effort_pct': 2.79,
    'scenario1_net_improvement_pct': 12.23,

    'scenario2_travel_distance_reduction_pct': 7.45,
    'scenario2_relocation_effort_pct': 2.08,
    'scenario2_net_improvement_pct': 5.37,

    # Section 6.2 (Tab. 1, ortalama)
    'depso_vs_SOP_avg_pct': -83.78,
    'depso_vs_FCFS_avg_pct': -40.80,
    'depso_vs_savings_avg_pct': -31.64,

    # Kabul edilebilir sapma aralığı (deterministik olmayan çıktılar için)
    'acceptable_deviation_pct': 10.0,          # ±10 puan
}


# ════════════════════════════════════════════════════════════════════════════
# TOHUM (deterministik koşumlar için)
# ════════════════════════════════════════════════════════════════════════════
RANDOM_SEED = 42


# ════════════════════════════════════════════════════════════════════════════
# RUNTIME AYARLARI
# ════════════════════════════════════════════════════════════════════════════
RUNTIME = {
    'depot_location_id': -1,                   # özel değer
    'verbose': True,
    'progress_bar': True,
    'parallel_runs': False,                    # ileride multiprocessing
}


if __name__ == "__main__":
    # Hızlı doğrulama
    print("Config yüklendi:")
    print(f"  Depo: {WAREHOUSE['num_aisles']} aisle × {WAREHOUSE['num_blocks']} blok = "
          f"{WAREHOUSE['total_locations']} lokasyon")
    print(f"  Ürün: {ITEMS['num_items']} (A={int(ITEMS['num_items']*WAREHOUSE['class_A_pct'])}, "
          f"B={int(ITEMS['num_items']*WAREHOUSE['class_B_pct'])}, "
          f"C={int(ITEMS['num_items']*WAREHOUSE['class_C_pct'])})")
    print(f"  DEPSO: {DEPSO['num_particles']} parçacık × {DEPSO['num_iterations']} iterasyon")
    print(f"  Senaryo 1: Tf={TIME_SERIES['scenario1_trend_Tf']}, Sf={TIME_SERIES['scenario1_seasonality_Sf']}")
    print(f"  Senaryo 2: Tf={TIME_SERIES['scenario2_trend_Tf']}, Sf={TIME_SERIES['scenario2_seasonality_Sf']}")
    print(f"  Veri dizini: {DATA_DIR}")
