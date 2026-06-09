"""组合选股器基类。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

import pandas as pd


class PortfolioSelector(ABC):
    """多标的截面选股器。"""

    @property
    @abstractmethod
    def warmup_period(self) -> int:
        """开始调仓前所需的最少历史 K 线根数。"""

    @abstractmethod
    def select(self, close_panel: pd.DataFrame, time_idx: int) -> List[str]:
        """返回调仓日应持有的标的代码列表。"""

    @abstractmethod
    def label(self) -> str:
        """策略描述。"""

    def score_snapshot(
        self,
        close_panel: pd.DataFrame,
        time_idx: int,
        symbols: List[str],
    ) -> Dict[str, float]:
        """调仓日志中的得分快照，子类可覆盖。"""
        return {}
