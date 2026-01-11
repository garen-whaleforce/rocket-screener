"""Supply chain chart generation (v8).

Generates PNG charts for industry supply chain visualization.
Uses matplotlib for rendering (no external dependencies like Graphviz).
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ChartNode:
    """Node in supply chain chart."""

    position: str  # upstream, midstream, downstream (or Chinese equivalent)
    segment: str
    companies: str
    notes: str


# Position ordering for layout
POSITION_ORDER = {
    "上游": 0,
    "upstream": 0,
    "中游": 1,
    "midstream": 1,
    "平台層": 1,
    "基礎層": 0,
    "下游": 2,
    "downstream": 2,
    "應用層": 2,
    "全棧": 1,
}

# Colors for positions
POSITION_COLORS = {
    0: "#e3f2fd",  # Light blue for upstream
    1: "#fff3e0",  # Light orange for midstream
    2: "#e8f5e9",  # Light green for downstream
}

POSITION_LABELS = {
    0: "上游 Upstream",
    1: "中游 Midstream",
    2: "下游 Downstream",
}


def generate_supply_chain_chart(
    theme: str,
    theme_display: str,
    supply_chain: list,  # list of SupplyChainLayer
    output_path: Path,
) -> Optional[str]:
    """Generate supply chain chart as PNG.

    Creates a horizontal flow chart showing industry layers.

    Args:
        theme: Theme ID
        theme_display: Display name of theme
        supply_chain: List of SupplyChainLayer objects
        output_path: Path to save PNG

    Returns:
        Path to generated PNG, or None if failed
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as patches
        from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
        from matplotlib.font_manager import FontProperties, findfont, FontManager
        import matplotlib

        # Find a Chinese font that exists on the system
        chinese_fonts = [
            'PingFang TC',      # macOS Traditional Chinese
            'Heiti TC',         # macOS Traditional Chinese
            'Arial Unicode MS', # macOS fallback
            'Microsoft JhengHei',  # Windows Traditional Chinese
            'Noto Sans CJK TC',    # Linux/Google Fonts
            'WenQuanYi Zen Hei',   # Linux
        ]

        # Find first available font
        font_prop = None
        for font_name in chinese_fonts:
            try:
                fp = FontProperties(family=font_name)
                font_path = findfont(fp, fallback_to_default=False)
                if font_path and 'LastResort' not in font_path:
                    font_prop = FontProperties(fname=font_path)
                    logger.info(f"Using Chinese font: {font_name} ({font_path})")
                    # Also set as default
                    matplotlib.rcParams['font.sans-serif'] = [font_name] + matplotlib.rcParams['font.sans-serif']
                    matplotlib.rcParams['axes.unicode_minus'] = False
                    break
            except Exception:
                continue

        if font_prop is None:
            logger.warning("No Chinese font found, text may not render correctly")
            font_prop = FontProperties()

    except ImportError:
        logger.warning("matplotlib not available, skipping chart generation")
        return None

    if not supply_chain:
        logger.warning("No supply chain data provided")
        return None

    try:
        # Group by position
        position_groups: dict[int, list] = {0: [], 1: [], 2: []}
        for layer in supply_chain:
            pos_key = POSITION_ORDER.get(layer.position, 1)
            position_groups[pos_key].append(layer)

        # Calculate dimensions
        max_items = max(len(v) for v in position_groups.values() if v)
        if max_items == 0:
            logger.warning("No valid supply chain items")
            return None

        fig_height = max(6, 2 + max_items * 1.8)
        fig_width = 16  # Wider to prevent left cutoff
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))
        ax.set_xlim(0, fig_width)
        ax.set_ylim(0, fig_height)
        ax.axis('off')

        # Title
        ax.text(
            fig_width / 2, fig_height - 0.5,
            f"{theme_display} 產業鏈",
            fontsize=18,
            fontweight='bold',
            ha='center',
            fontproperties=font_prop,
        )

        # Draw columns - shifted right to avoid left cutoff
        col_positions = [2.5, 7.0, 11.5]  # X centers for upstream, midstream, downstream
        col_width = 4.0
        header_height = 0.7
        item_height = 1.5
        item_padding = 0.3

        # Draw each position column
        for pos_idx, (x_center, items) in enumerate(zip(col_positions, [
            position_groups[0], position_groups[1], position_groups[2]
        ])):
            if not items:
                continue

            # Column header
            header_y = fig_height - 1.5
            header_rect = FancyBboxPatch(
                (x_center - col_width/2, header_y - header_height/2),
                col_width, header_height,
                boxstyle="round,pad=0.05,rounding_size=0.1",
                facecolor=POSITION_COLORS[pos_idx],
                edgecolor="#333",
                linewidth=2,
            )
            ax.add_patch(header_rect)
            ax.text(
                x_center, header_y,
                POSITION_LABELS[pos_idx],
                fontsize=14,
                fontweight='bold',
                ha='center',
                va='center',
                fontproperties=font_prop,
            )

            # Draw items
            for i, layer in enumerate(items):
                item_y = header_y - 1.2 - i * (item_height + item_padding)

                # Item box
                item_rect = FancyBboxPatch(
                    (x_center - col_width/2 + 0.1, item_y - item_height/2),
                    col_width - 0.2, item_height,
                    boxstyle="round,pad=0.03,rounding_size=0.1",
                    facecolor="white",
                    edgecolor=POSITION_COLORS[pos_idx].replace('f', 'c'),
                    linewidth=1.5,
                )
                ax.add_patch(item_rect)

                # Segment name
                ax.text(
                    x_center, item_y + 0.4,
                    layer.segment,
                    fontsize=12,
                    fontweight='bold',
                    ha='center',
                    va='center',
                    fontproperties=font_prop,
                )

                # Companies
                companies_text = layer.companies if len(layer.companies) < 28 else layer.companies[:25] + "..."
                ax.text(
                    x_center, item_y,
                    companies_text,
                    fontsize=11,
                    ha='center',
                    va='center',
                    color='#1976d2',
                    fontproperties=font_prop,
                )

                # Notes
                notes_text = layer.notes if len(layer.notes) < 22 else layer.notes[:19] + "..."
                ax.text(
                    x_center, item_y - 0.4,
                    notes_text,
                    fontsize=10,
                    ha='center',
                    va='center',
                    color='#666',
                    fontproperties=font_prop,
                )

        # Draw arrows between columns
        arrow_y = fig_height - 1.5
        arrow_style = "Simple, tail_width=0.5, head_width=1.5, head_length=1"

        if position_groups[0] and position_groups[1]:
            arrow1 = FancyArrowPatch(
                (col_positions[0] + col_width/2 + 0.2, arrow_y),
                (col_positions[1] - col_width/2 - 0.2, arrow_y),
                arrowstyle=arrow_style,
                color='#9e9e9e',
                mutation_scale=10,
            )
            ax.add_patch(arrow1)

        if position_groups[1] and position_groups[2]:
            arrow2 = FancyArrowPatch(
                (col_positions[1] + col_width/2 + 0.2, arrow_y),
                (col_positions[2] - col_width/2 - 0.2, arrow_y),
                arrowstyle=arrow_style,
                color='#9e9e9e',
                mutation_scale=10,
            )
            ax.add_patch(arrow2)

        # Disclaimer
        ax.text(
            fig_width / 2, 0.3,
            "資料來源：公開資訊整理 | 僅供參考，非投資建議",
            fontsize=10,
            ha='center',
            color='gray',
            fontproperties=font_prop,
        )

        # Save with padding to prevent cutoff
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight', pad_inches=0.3, facecolor='white')
        plt.close()

        logger.info(f"Generated supply chain chart: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"Failed to generate supply chain chart: {e}")
        return None


def generate_supply_chain_chart_from_evidence(
    evidence,  # Article3Evidence
    output_dir: Path,
) -> Optional[str]:
    """Generate supply chain chart from Article 3 Evidence Pack.

    Args:
        evidence: Article3Evidence with supply chain data
        output_dir: Directory to save chart

    Returns:
        Path to generated PNG, or None
    """
    if not evidence.supply_chain:
        logger.warning("No supply chain data in evidence")
        return None

    output_path = output_dir / f"supply_chain_{evidence.theme}.png"
    return generate_supply_chain_chart(
        theme=evidence.theme,
        theme_display=evidence.theme_display,
        supply_chain=evidence.supply_chain,
        output_path=output_path,
    )


def generate_simple_text_chart(supply_chain: list) -> str:
    """Generate a simple text-based supply chain representation.

    Fallback when matplotlib is not available.

    Args:
        supply_chain: List of SupplyChainLayer objects

    Returns:
        Text representation of supply chain
    """
    lines = []
    lines.append("=" * 60)
    lines.append("產業鏈 Supply Chain")
    lines.append("=" * 60)

    # Group by position
    position_groups: dict[int, list] = {0: [], 1: [], 2: []}
    for layer in supply_chain:
        pos_key = POSITION_ORDER.get(layer.position, 1)
        position_groups[pos_key].append(layer)

    for pos_idx in [0, 1, 2]:
        items = position_groups[pos_idx]
        if not items:
            continue

        lines.append("")
        lines.append(f"【{POSITION_LABELS[pos_idx]}】")
        lines.append("-" * 40)

        for layer in items:
            lines.append(f"  {layer.segment}")
            lines.append(f"    公司: {layer.companies}")
            lines.append(f"    備註: {layer.notes}")

    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)
