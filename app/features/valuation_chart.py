"""Valuation chart generation (v4).

Generates PNG charts for valuation models.
All numbers are deterministic - no LLM-generated values.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ValuationChartData:
    """Data for valuation chart."""

    ticker: str
    company_name: str
    current_price: float

    # Valuation cases
    bear_price: float
    bear_assumption: str
    base_price: float
    base_assumption: str
    bull_price: float
    bull_assumption: str

    # Key metrics
    forward_pe: Optional[float] = None
    eps_estimate: Optional[float] = None
    revenue_growth: Optional[str] = None


def generate_valuation_chart_png(
    data: ValuationChartData,
    output_path: Path,
) -> Optional[str]:
    """Generate valuation chart as PNG.

    Creates a professional-looking valuation table image.
    All numbers are from data input, not generated.

    Args:
        data: Valuation data
        output_path: Path to save PNG

    Returns:
        Path to generated PNG, or None if failed
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        from matplotlib.table import Table
    except ImportError:
        logger.warning("matplotlib not available, skipping chart generation")
        return None

    try:
        # Create figure
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')

        # Title
        fig.suptitle(
            f"{data.ticker} 估值分析",
            fontsize=16,
            fontweight='bold',
            y=0.95,
        )

        # Subtitle
        ax.text(
            0.5, 0.92,
            f"現價: ${data.current_price:,.2f}",
            transform=ax.transAxes,
            fontsize=12,
            ha='center',
        )

        # Create table data
        cell_text = [
            ["情境", "假設", "目標價", "潛在空間"],
            [
                "🐻 Bear",
                data.bear_assumption[:30] + "..." if len(data.bear_assumption) > 30 else data.bear_assumption,
                f"${data.bear_price:,.0f}",
                f"{((data.bear_price / data.current_price) - 1) * 100:+.1f}%",
            ],
            [
                "⚖️ Base",
                data.base_assumption[:30] + "..." if len(data.base_assumption) > 30 else data.base_assumption,
                f"${data.base_price:,.0f}",
                f"{((data.base_price / data.current_price) - 1) * 100:+.1f}%",
            ],
            [
                "🐂 Bull",
                data.bull_assumption[:30] + "..." if len(data.bull_assumption) > 30 else data.bull_assumption,
                f"${data.bull_price:,.0f}",
                f"{((data.bull_price / data.current_price) - 1) * 100:+.1f}%",
            ],
        ]

        # Create table
        table = ax.table(
            cellText=cell_text,
            cellLoc='center',
            loc='center',
            colWidths=[0.15, 0.45, 0.2, 0.2],
        )

        # Style table
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 2)

        # Header styling
        for j in range(4):
            cell = table[(0, j)]
            cell.set_facecolor('#2c3e50')
            cell.set_text_props(color='white', fontweight='bold')

        # Row colors
        colors = ['#ffcdd2', '#fff9c4', '#c8e6c9']  # red, yellow, green
        for i, color in enumerate(colors, start=1):
            for j in range(4):
                table[(i, j)].set_facecolor(color)

        # Add disclaimer
        ax.text(
            0.5, 0.08,
            "資料來源：FMP / 公司財報 | 僅供參考，非投資建議",
            transform=ax.transAxes,
            fontsize=8,
            ha='center',
            color='gray',
        )

        # Add metrics if available
        metrics_text = []
        if data.forward_pe:
            metrics_text.append(f"Forward P/E: {data.forward_pe:.1f}x")
        if data.eps_estimate:
            metrics_text.append(f"EPS Est: ${data.eps_estimate:.2f}")
        if data.revenue_growth:
            metrics_text.append(f"Rev Growth: {data.revenue_growth}")

        if metrics_text:
            ax.text(
                0.5, 0.15,
                " | ".join(metrics_text),
                transform=ax.transAxes,
                fontsize=9,
                ha='center',
            )

        # Save
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        logger.info(f"Generated valuation chart: {output_path}")
        return str(output_path)

    except Exception as e:
        logger.error(f"Failed to generate valuation chart: {e}")
        return None


def generate_valuation_chart_from_evidence(
    evidence,  # Article2Evidence
    output_dir: Path,
) -> Optional[str]:
    """Generate valuation chart from Article 2 Evidence Pack.

    Args:
        evidence: Article2Evidence with valuation cases
        output_dir: Directory to save chart

    Returns:
        Path to generated PNG, or None
    """
    if not evidence.valuation_cases or len(evidence.valuation_cases) < 3:
        logger.warning("Insufficient valuation cases for chart")
        return None

    # Find cases by scenario
    cases = {c.scenario: c for c in evidence.valuation_cases}

    if not all(s in cases for s in ["bear", "base", "bull"]):
        logger.warning("Missing required valuation scenarios")
        return None

    data = ValuationChartData(
        ticker=evidence.ticker,
        company_name=evidence.company_name,
        current_price=evidence.current_price,
        bear_price=cases["bear"].target_price,
        bear_assumption=cases["bear"].assumption,
        base_price=cases["base"].target_price,
        base_assumption=cases["base"].assumption,
        bull_price=cases["bull"].target_price,
        bull_assumption=cases["bull"].assumption,
        forward_pe=evidence.forward_pe,
    )

    output_path = output_dir / f"valuation_{evidence.ticker.lower()}.png"
    return generate_valuation_chart_png(data, output_path)
