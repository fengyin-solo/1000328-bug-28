"""光伏方阵业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "array"
REQUIRED_FIELDS = ["方阵编号", "方阵名称", "组件型号"]
EDITABLE_FIELDS = ["方阵编号", "方阵名称", "组件型号", "组件数量", "安装倾角", "朝向方位", "所属电站"]
STATUS_ORDER = ["待验收", "已投运", "遮挡异常", "已拆除"]
ACTION_RULES = {"提交验收": "已投运", "登记遮挡": "遮挡异常", "拆除方阵": "已拆除"}
ABNORMAL_STATUSES = {"遮挡异常"}
SHADE_ACTION = "登记遮挡"


class ArrayService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("方阵编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str], str]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing, ""
        rows = store.rows(MODULE)
        code = str(values.get("方阵编号") or "").strip()
        existing = next(
            (row for row in rows if str(row.get("方阵编号", "")).strip() == code),
            None,
        )
        if existing is not None:
            # 同一方阵编号重复登记时合并到原记录，列表里始终只保留一条
            for field in EDITABLE_FIELDS:
                if field in values and str(values.get(field) or "").strip():
                    existing[field] = values.get(field)
            return existing, [], f"方阵编号 {code} 已登记过，已合并到原记录"
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in EDITABLE_FIELDS:
            entry[field] = values.get(field)
        entry["status"] = STATUS_ORDER[0]
        entry["方阵状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, [], "方阵已登记"

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
        remark: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"方阵 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于光伏方阵可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["方阵状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = target in ABNORMAL_STATUSES
        if action == SHADE_ACTION:
            # 遮挡登记结果留在记录上，刷新列表后仍然看得到
            values = values or {}
            reason = str(values.get("遮挡原因") or "").strip()
            if reason:
                entry["遮挡原因"] = reason
            note = str(remark or values.get("遮挡说明") or "").strip()
            if note:
                entry["遮挡说明"] = note
        return entry, f"方阵已{action}"
