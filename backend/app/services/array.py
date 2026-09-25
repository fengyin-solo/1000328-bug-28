"""光伏方阵业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Any

from app.store import store

MODULE = "array"
LIST_FIELDS = ["方阵编号", "方阵名称", "组件型号", "组件数量", "安装倾角", "朝向方位", "所属电站", "方阵状态"]
REQUIRED_FIELDS = ["方阵编号", "方阵名称", "组件型号"]
SHADING_REQUIRED_FIELDS = ["遮挡原因"]
STATUS_ORDER = ["待验收", "已投运", "遮挡异常", "已拆除"]
ACTION_RULES = {"提交验收": "已投运", "登记遮挡": "遮挡异常", "拆除方阵": "已拆除"}
NEGATIVE_ACTIONS = ["登记遮挡"]

_write_lock = Lock()


class ArrayService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        name: str | None = None,
        model: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("方阵编号", ""))]
        if name:
            rows = [row for row in rows if name in str(row.get("方阵名称", ""))]
        if model:
            rows = [row for row in rows if model in str(row.get("组件型号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._display(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = store.find(MODULE, entry_id)
        return self._display(row) if row is not None else None

    def stats(self) -> list[dict[str, Any]]:
        """统计卡片直接按库存数据实时计算，保证和列表口径一致。"""
        rows = store.rows(MODULE)
        modules_total = 0
        for row in rows:
            try:
                modules_total += int(float(str(row.get("组件数量") or 0)))
            except ValueError:
                continue
        return [
            {"label": "在运方阵", "value": sum(1 for row in rows if row.get("status") == "已投运")},
            {"label": "遮挡异常方阵", "value": sum(1 for row in rows if row.get("status") == "遮挡异常")},
            {"label": "组件总块数", "value": modules_total},
        ]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], bool]:
        """登记方阵。返回 (记录, 缺失字段, 是否新建)；方阵编号重复时不重复建行。"""
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, False
        with _write_lock:
            code = str(values.get("方阵编号")).strip()
            rows = store.rows(MODULE)
            for row in rows:
                if str(row.get("方阵编号", "")).strip() == code:
                    return self._display(row), [], False
            entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
            for field in LIST_FIELDS:
                if field == "方阵状态":
                    continue
                if field in values:
                    entry[field] = values[field]
            entry["status"] = STATUS_ORDER[0]
            entry["方阵状态"] = STATUS_ORDER[0]
            entry["pending"] = True
            entry["abnormal"] = False
            rows.append(entry)
            return self._display(entry), [], True

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于光伏方阵可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        with _write_lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"方阵 {entry_id} 不存在或已归档"
            if action == "登记遮挡":
                if entry.get("status") == "遮挡异常":
                    return self._display(entry), "该方阵已登记过遮挡，保持原登记不变"
                missing = [field for field in SHADING_REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
                if missing:
                    return None, f"缺少必填字段：{'、'.join(missing)}"
                entry["遮挡原因"] = str(values.get("遮挡原因")).strip()
                entry["遮挡登记时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry["status"] = target
            entry["方阵状态"] = target
            entry["pending"] = target != STATUS_ORDER[-1]
            entry["abnormal"] = action in NEGATIVE_ACTIONS
            return self._display(entry), f"方阵已{action}"

    def _display(self, row: dict[str, Any]) -> dict[str, Any]:
        """列表/详情统一把内部 status 同步到「方阵状态」列，状态流转在页面上看得见。"""
        item = dict(row)
        item["方阵状态"] = str(row.get("status") or item.get("方阵状态") or "")
        return item
