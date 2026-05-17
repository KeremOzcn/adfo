"""
ui/components/warehouse_plot.py
================================
Plotly ile depo görselleştirmesi.

Üretilen şekiller:
- Depo düzeni (raf blokları, aisle'lar, cross aisle'lar, depot)
- Sipariş lokasyonları (renk = ABC sınıfı veya batch ID)
- Picker rotası (oklarla)
"""

from __future__ import annotations

import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.warehouse import Warehouse


# Renk paleti (batch'ler ve sınıflar için)
CLASS_COLORS = {'A': '#e74c3c', 'B': '#f39c12', 'C': '#3498db'}
BATCH_COLORS = [
    '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
    '#1abc9c', '#e67e22', '#34495e', '#fd79a8', '#00cec9',
    '#fdcb6e', '#6c5ce7', '#e84393', '#00b894', '#0984e3',
    '#a29bfe', '#fab1a0', '#ff7675', '#74b9ff', '#55efc4',
]


def plot_warehouse_layout(
    warehouse: Warehouse,
    show_class_locations: bool = False,
    sample_size_per_class: int = 50,
) -> go.Figure:
    """
    Sadece depo düzenini göster (raflar, aisle'lar, depot).

    show_class_locations: True ise A, B, C sınıf lokasyonlarını noktalarla göster
    """
    fig = go.Figure()

    # Raflar (her aisle'ın iki yanı, her blokta 30 rack)
    rack_w = warehouse.rack_width
    aisle_spacing = warehouse.aisle_spacing
    rack_thickness = (aisle_spacing - 1) / 2  # raf kalınlığı (görsel)

    for aisle_idx in range(warehouse.num_aisles):
        aisle_center_y = warehouse.aisle_y[aisle_idx]
        # Sol ve sağ raf bloğu
        for side in [0, 1]:
            if side == 0:
                y_top = aisle_center_y - 0.5
                y_bot = y_top - rack_thickness
            else:
                y_bot = aisle_center_y + 0.5
                y_top = y_bot + rack_thickness

            # Her blok için raflar
            for block in range(warehouse.num_blocks):
                block_start = warehouse.cross_aisle_x[block]
                if block > 0:
                    block_start += warehouse.cross_aisle_width
                x_left = block_start
                x_right = block_start + warehouse.racks_per_block * rack_w

                fig.add_shape(
                    type="rect",
                    x0=x_left, y0=y_bot, x1=x_right, y1=y_top,
                    fillcolor="#bdc3c7",
                    line=dict(color="#7f8c8d", width=0.5),
                    layer="below",
                )

    # Depot
    fig.add_trace(go.Scatter(
        x=[warehouse.depot_x],
        y=[warehouse.depot_y],
        mode='markers+text',
        marker=dict(size=20, symbol='square', color='#2c3e50'),
        text=['DEPOT'],
        textposition='top right',
        name='Depot',
        hovertemplate='Depot<br>x=%{x:.1f}, y=%{y:.1f}<extra></extra>',
    ))

    # Sınıf lokasyonları (isteğe bağlı)
    if show_class_locations:
        classes = warehouse.assign_locations_to_classes()
        for cls in ['A', 'B', 'C']:
            locs = classes[cls][:sample_size_per_class]  # örnekle
            xs, ys = [], []
            for lid in locs:
                x, y = warehouse.coords(lid)
                xs.append(x)
                ys.append(y)
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode='markers',
                marker=dict(size=4, color=CLASS_COLORS[cls], opacity=0.6),
                name=f'Sınıf {cls} (örnek {len(locs)})',
                hovertemplate=f'Sınıf {cls}<br>loc=%{{customdata}}<br>(%{{x:.1f}}, %{{y:.1f}})<extra></extra>',
                customdata=locs,
            ))

    # Layout
    fig.update_layout(
        title="Depo Düzeni",
        xaxis_title="X (LU)",
        yaxis_title="Y (LU)",
        xaxis=dict(scaleanchor="y", scaleratio=1, gridcolor='#ecf0f1'),
        yaxis=dict(gridcolor='#ecf0f1'),
        plot_bgcolor='white',
        height=500,
        showlegend=True,
        hovermode='closest',
    )
    return fig


def plot_batch_routes(
    warehouse: Warehouse,
    batches: list,
    max_batches_to_show: int = 5,
    show_warehouse_outline: bool = True,
) -> go.Figure:
    """
    Birden çok batch'in rotalarını görselleştir.

    batches: Batch nesneleri listesi (route alanı dolu olmalı)
    """
    fig = go.Figure()

    # Depo düzeni (sönük arka plan)
    if show_warehouse_outline:
        _add_warehouse_outline(fig, warehouse)

    # Depot
    fig.add_trace(go.Scatter(
        x=[warehouse.depot_x], y=[warehouse.depot_y],
        mode='markers+text',
        marker=dict(size=18, symbol='square', color='black'),
        text=['DEPOT'], textposition='top right',
        name='Depot',
        showlegend=False,
    ))

    # Her batch için rota
    for i, batch in enumerate(batches[:max_batches_to_show]):
        color = BATCH_COLORS[i % len(BATCH_COLORS)]
        route = batch.route
        if not route:
            continue
        xs, ys = [], []
        for loc in route:
            x, y = warehouse.coords(loc)
            xs.append(x)
            ys.append(y)

        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode='lines+markers',
            line=dict(color=color, width=2),
            marker=dict(size=8, color=color, line=dict(color='white', width=1)),
            name=f"Batch {batch.batch_id} ({batch.travel_distance:.0f} LU)",
            hovertemplate='Batch %{text}<br>(%{x:.1f}, %{y:.1f})<extra></extra>',
            text=[f'{batch.batch_id}'] * len(xs),
        ))

    total_shown = sum(b.travel_distance for b in batches[:max_batches_to_show])
    fig.update_layout(
        title=f"Picker Rotaları (ilk {min(max_batches_to_show, len(batches))} batch, "
              f"toplam {total_shown:.0f} LU)",
        xaxis_title="X (LU)",
        yaxis_title="Y (LU)",
        xaxis=dict(scaleanchor="y", scaleratio=1, gridcolor='#ecf0f1'),
        yaxis=dict(gridcolor='#ecf0f1'),
        plot_bgcolor='white',
        height=600,
        hovermode='closest',
    )
    return fig


def plot_convergence(history: list[float], title: str = "DEPSO Yakınsama") -> go.Figure:
    """DEPSO'nun iterasyon başına Gbest grafiği."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        y=history,
        mode='lines',
        line=dict(color='#3498db', width=2),
        name='Gbest',
        hovertemplate='İterasyon %{x}<br>Gbest = %{y:.1f} LU<extra></extra>',
    ))
    fig.update_layout(
        title=title,
        xaxis_title="İterasyon",
        yaxis_title="Travel Distance (LU)",
        plot_bgcolor='white',
        height=350,
        showlegend=False,
    )
    return fig


def plot_comparison_bar(rows, title: str = "Algoritma Karşılaştırması") -> go.Figure:
    """Algoritmaların travel distance'larını yan yana bar olarak göster."""
    names = [r.algorithm for r in rows]
    distances = [r.travel_distance_LU for r in rows]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=names,
        y=distances,
        marker=dict(color=[BATCH_COLORS[i % len(BATCH_COLORS)] for i in range(len(rows))]),
        text=[f"{d:.0f}" for d in distances],
        textposition='outside',
        hovertemplate='%{x}<br>%{y:.1f} LU<extra></extra>',
    ))
    fig.update_layout(
        title=title,
        yaxis_title="Total Travel Distance (LU)",
        plot_bgcolor='white',
        height=400,
        showlegend=False,
    )
    return fig


def _add_warehouse_outline(fig: go.Figure, warehouse: Warehouse) -> None:
    """Depo iskeletini sönük olarak çiz (rota görselleştirmesinin arka planına)."""
    rack_w = warehouse.rack_width
    aisle_spacing = warehouse.aisle_spacing
    rack_thickness = (aisle_spacing - 1) / 2

    for aisle_idx in range(warehouse.num_aisles):
        aisle_center_y = warehouse.aisle_y[aisle_idx]
        for side in [0, 1]:
            if side == 0:
                y_top = aisle_center_y - 0.5
                y_bot = y_top - rack_thickness
            else:
                y_bot = aisle_center_y + 0.5
                y_top = y_bot + rack_thickness
            for block in range(warehouse.num_blocks):
                block_start = warehouse.cross_aisle_x[block]
                if block > 0:
                    block_start += warehouse.cross_aisle_width
                x_left = block_start
                x_right = block_start + warehouse.racks_per_block * rack_w
                fig.add_shape(
                    type="rect",
                    x0=x_left, y0=y_bot, x1=x_right, y1=y_top,
                    fillcolor="#ecf0f1",
                    line=dict(color="#bdc3c7", width=0.3),
                    layer="below",
                )


if __name__ == "__main__":
    # Hızlı test (plotly kullanılabilir bir ortamda)
    wh = Warehouse()
    fig = plot_warehouse_layout(wh, show_class_locations=True)
    print("Warehouse layout figure oluşturuldu")
    print(f"  Traces: {len(fig.data)}")
    print(f"  Shapes: {len(fig.layout.shapes) if fig.layout.shapes else 0}")
