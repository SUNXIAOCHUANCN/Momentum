from datetime import datetime, timedelta
from typing import Any
import json
import os
import re
import uuid

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

try:
    import dashscope
except ImportError:
    dashscope = None

def load_local_env() -> None:
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


load_local_env()

app = FastAPI()

# ⚠️ 必须配置跨域，否则前端无法调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AI_SYSTEM_PROMPT = """你是「大学生课表」编辑助手，负责根据用户自然语言调整日程。

【输出格式（必须严格遵守）】
只输出一个 JSON 对象，不要 Markdown，不要解释文字。格式：
{"summary":"一句话说明本轮调整思路","actions":[...]}

每个 action 只能是以下之一：
- {"action":"add","target_date":"YYYY-MM-DD","title":"...","start_min":整数,"end_min":整数,"note":"可选","fixed":false,"category":"学习","priority":1|2|3}
- {"action":"edit","id":"必须来自输入里的真实id","source_date":"YYYY-MM-DD","target_date":"YYYY-MM-DD","start_min":可选,"end_min":可选,"title":可选,"note":可选,"priority":可选}
- {"action":"delete","id":"...","source_date":"YYYY-MM-DD"}
- {"action":"complete","id":"...","source_date":"YYYY-MM-DD"}

【时间】start_min/end_min 为当天 0-1440 的分钟。跨天必须同时给出 source_date 与 target_date。

【硬规则】
1) 只能引用输入 schedule 里已存在的 event id，禁止编造 id。
2) fixed=true 的事件：禁止修改其 start_min/end_min（可改标题备注等元信息，但一般不要动）。
3) 优先保护高优先级（priority 数字越小越高）。
4) 若用户只说「今晚有事/临时占用」但未给具体时间：使用输入里的 default_busy_block 作为占用块（add + fixed=true）。
5) 若无法安全调整：输出 actions 为空数组，并在 summary 说明缺少什么信息（例如占用时长）。
6) 尽量利用 free_slots 把被挤占的学习任务挪到空档或明天（edit 改时间或跨天 target_date）。

【少样本（日期必须用输入里的 today_date / tomorrow_date，勿编造）】
用户：我今晚临时有事，帮我处理今天的课表。
输出：先 add 默认晚间占用（见 default_busy_block_if_unspecified），再 edit 把与占用冲突的可挪动任务挪到 tomorrow_free_slots 或今天剩余空档。

用户：把「高数复习」挪到明天晚上。
输出：edit 指定 id，source_date=today_date，target_date=tomorrow_date，并给出明天晚上的具体 start_min/end_min。
"""


class EventCreate(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    title: str
    start_min: int = Field(..., ge=0, le=1439)
    end_min: int = Field(..., ge=1, le=1440)
    note: str = ""
    fixed: bool = False
    category: str = "学习"
    location: str = ""
    description: str = ""
    priority: int = Field(default=2, ge=1, le=3)


class EventUpdate(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    title: str | None = None
    start_min: int | None = Field(default=None, ge=0, le=1439)
    end_min: int | None = Field(default=None, ge=1, le=1440)
    note: str | None = None
    fixed: bool | None = None
    category: str | None = None
    location: str | None = None
    description: str | None = None
    priority: int | None = Field(default=None, ge=1, le=3)


class CompleteRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    completed: bool = True


class AiReplanRequest(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    prompt: str


class DaySchedule(BaseModel):
    date: str
    events: list[dict[str, Any]]
    completed: list[dict[str, Any]]


schedule_store: dict[str, DaySchedule] = {}


def min_to_hhmm(mins: int) -> str:
    h = mins // 60
    m = mins % 60
    return f"{h:02d}:{m:02d}"


def snapshot_store() -> dict[str, Any]:
    return {k: v.model_dump() for k, v in schedule_store.items()}


def restore_store(snap: dict[str, Any]) -> None:
    schedule_store.clear()
    for key, val in snap.items():
        schedule_store[key] = DaySchedule.model_validate(val)


def compute_free_slots(events: list[dict[str, Any]], window_start: int, window_end: int) -> list[dict[str, Any]]:
    occupied: list[tuple[int, int]] = []
    for event in sort_events(events):
        start = max(int(event["start_min"]), window_start)
        end = min(int(event["end_min"]), window_end)
        if start < end:
            occupied.append((start, end))
    if not occupied:
        if window_start < window_end:
            return [{"start_min": window_start, "end_min": window_end, "duration_min": window_end - window_start}]
        return []

    occupied.sort()
    merged: list[tuple[int, int]] = []
    for start, end in occupied:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    gaps: list[dict[str, Any]] = []
    cursor = window_start
    for start, end in merged:
        if start > cursor:
            gaps.append(
                {
                    "start_min": cursor,
                    "end_min": start,
                    "duration_min": start - cursor,
                    "start_clock": min_to_hhmm(cursor),
                    "end_clock": min_to_hhmm(start),
                }
            )
        cursor = max(cursor, end)
    if cursor < window_end:
        gaps.append(
            {
                "start_min": cursor,
                "end_min": window_end,
                "duration_min": window_end - cursor,
                "start_clock": min_to_hhmm(cursor),
                "end_clock": min_to_hhmm(window_end),
            }
        )
    return [g for g in gaps if g["duration_min"] > 0]


def compact_events_for_llm(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for event in sort_events(events):
        out.append(
            {
                "id": event["id"],
                "title": event.get("title", ""),
                "start_min": int(event["start_min"]),
                "end_min": int(event["end_min"]),
                "start_clock": min_to_hhmm(int(event["start_min"])),
                "end_clock": min_to_hhmm(int(event["end_min"])),
                "duration_min": int(event["end_min"]) - int(event["start_min"]),
                "priority": int(event.get("priority", 2)),
                "fixed": bool(event.get("fixed", False)),
                "category": str(event.get("category", "学习")),
            }
        )
    return out


def build_schedule_summary(base_date: str, day: DaySchedule) -> dict[str, Any]:
    next_date = (datetime.strptime(base_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    next_day = ensure_day(next_date)
    window_start = int(os.getenv("DAY_WINDOW_START_MIN", "360"))
    window_end = int(os.getenv("DAY_WINDOW_END_MIN", "1320"))
    busy_start = int(os.getenv("BUSY_DEFAULT_START_MIN", "1140"))
    busy_end = int(os.getenv("BUSY_DEFAULT_END_MIN", "1260"))
    return {
        "today_date": base_date,
        "tomorrow_date": next_date,
        "day_window": {"start_min": window_start, "end_min": window_end},
        "today_events": compact_events_for_llm(day.events),
        "today_free_slots": compute_free_slots(day.events, window_start, window_end),
        "tomorrow_events": compact_events_for_llm(next_day.events),
        "tomorrow_free_slots": compute_free_slots(next_day.events, window_start, window_end),
        "default_busy_block_if_unspecified": {
            "start_min": busy_start,
            "end_min": busy_end,
            "start_clock": min_to_hhmm(busy_start),
            "end_clock": min_to_hhmm(busy_end),
            "hint": "用户只说今晚有事但未给具体时间时，可用此默认占用块",
        },
    }


def build_intent_hints(prompt: str) -> dict[str, Any]:
    hints: dict[str, Any] = {
        "mentions_tonight_busy": bool(re.search(r"今晚|今天晚上|夜里", prompt)),
        "mentions_tomorrow": bool(re.search(r"明天|翌日", prompt)),
        "mentions_move": bool(re.search(r"挪|移|顺延|改到|调到", prompt)),
        "mentions_busy_no_time": bool(re.search(r"有事|占用|突发|临时", prompt))
        and not re.search(r"\d{1,2}[:：]\d{2}", prompt),
    }
    hints["likely_need_default_busy"] = hints["mentions_tonight_busy"] and hints["mentions_busy_no_time"]
    return hints


def validate_date(date_str: str) -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="date 必须是 YYYY-MM-DD") from exc
    return date_str


def resolve_relative_date(value: Any, base_date: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None

    if re.match(r"^\d{4}-\d{2}-\d{2}$", text):
        return text

    base_dt = datetime.strptime(base_date, "%Y-%m-%d")
    if text in {"today", "今天"}:
        return base_date
    if text in {"tomorrow", "明天"}:
        return (base_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    if text in {"后天"}:
        return (base_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    if text in {"yesterday", "昨天"}:
        return (base_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    slash = re.match(r"^(\d{1,2})[/-](\d{1,2})$", text)
    if slash:
        m, d = map(int, slash.groups())
        return datetime(base_dt.year, m, d).strftime("%Y-%m-%d")
    return None


def ensure_day(date_str: str) -> DaySchedule:
    validate_date(date_str)
    if date_str not in schedule_store:
        schedule_store[date_str] = DaySchedule(date=date_str, events=[], completed=[])
    return schedule_store[date_str]


def validate_time_range(start_min: int, end_min: int) -> None:
    if start_min >= end_min:
        raise HTTPException(status_code=400, detail="时间范围非法：start_min 必须小于 end_min")


def has_conflict(candidate: dict[str, Any], events: list[dict[str, Any]], exclude_id: str | None = None) -> dict[str, Any] | None:
    for item in events:
        if exclude_id and item["id"] == exclude_id:
            continue
        if candidate["start_min"] < item["end_min"] and item["start_min"] < candidate["end_min"]:
            return item
    return None


def sort_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(events, key=lambda x: (x["start_min"], x["end_min"]))


def find_event(events: list[dict[str, Any]], event_id: str) -> dict[str, Any] | None:
    for item in events:
        if item["id"] == event_id:
            return item
    return None


def extract_json_block(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _dashscope_chat(messages: list[dict[str, str]]) -> tuple[str, str, str]:
    """Returns (content_text, used_model, error_reason)."""
    if dashscope is None:
        return "", "", "dashscope-missing"

    api_key = (
        os.getenv("DASHSCOPE_API_KEY", "").strip()
        or os.getenv("QWEN_API_KEY", "").strip()
    )
    if not api_key:
        return "", "", "missing-api-key"

    preferred_model = (
        os.getenv("DASHSCOPE_MODEL", "").strip()
        or os.getenv("QWEN_MODEL", "").strip()
        or "qwen3.6-plus"
    )
    candidate_models: list[str] = []
    for m in [preferred_model, "qwen-plus", "qwen-turbo"]:
        if m and m not in candidate_models:
            candidate_models.append(m)

    text = ""
    used_model = ""
    last_code = ""

    for model_name in candidate_models:
        try:
            response_data = dashscope.Generation.call(
                api_key=api_key,
                model=model_name,
                messages=messages,
                result_format="message",
            )
        except Exception:
            last_code = "sdk-call-failed"
            continue

        if isinstance(response_data, dict):
            code = response_data.get("code")
            if code:
                last_code = code
                continue
            text = (
                response_data.get("output", {})
                .get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
        else:
            try:
                code = getattr(response_data, "code", None)
                if code:
                    last_code = code
                    continue
                output = getattr(response_data, "output", None) or {}
                choices = output.get("choices", []) if isinstance(output, dict) else []
                text = ""
                if choices:
                    msg = choices[0].get("message", {})
                    if isinstance(msg, dict):
                        text = msg.get("content", "")
            except Exception:
                last_code = "sdk-parse-failed"
                continue

        if text:
            used_model = model_name
            break

    if not text:
        return "", "", last_code or "empty-response"
    return text, used_model, ""


def call_qwen_for_actions(
    date: str,
    prompt: str,
    day: DaySchedule,
    repair_context: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], str, str, str]:
    """
    Returns (actions, model_used, raw_text, llm_summary).
    """
    summary = build_schedule_summary(date, day)
    hints = build_intent_hints(prompt)
    user_payload: dict[str, Any] = {
        "current_date": date,
        "user_prompt": prompt,
        "intent_hints": hints,
        "schedule_summary": summary,
        "completed_today": compact_events_for_llm(day.completed),
    }
    if repair_context:
        user_payload["repair_request"] = repair_context

    messages = [
        {"role": "system", "content": AI_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]

    text, used_model, err = _dashscope_chat(messages)
    if not text:
        return [], f"rule-fallback ({err})", "", ""

    parsed = extract_json_block(text) or {}
    actions = parsed.get("actions", [])
    if not isinstance(actions, list):
        actions = []
    llm_summary = str(parsed.get("summary", "")).strip()
    return actions, f"dashscope:{used_model}", text, llm_summary


def fallback_actions_from_prompt(prompt: str, day: DaySchedule) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    base_date = day.date
    span = re.search(r"(\d{1,2})[:：](\d{2})\s*[-~到]\s*(\d{1,2})[:：](\d{2})", prompt)
    if span:
        s_h, s_m, e_h, e_m = span.groups()
        start_min = int(s_h) * 60 + int(s_m)
        end_min = int(e_h) * 60 + int(e_m)
        actions.append(
            {
                "action": "add",
                "target_date": base_date,
                "title": "突发事项",
                "start_min": start_min,
                "end_min": end_min,
                "note": prompt[:50],
                "fixed": True,
            }
        )
        return actions

    if build_intent_hints(prompt).get("likely_need_default_busy"):
        busy_start = int(os.getenv("BUSY_DEFAULT_START_MIN", "1140"))
        busy_end = int(os.getenv("BUSY_DEFAULT_END_MIN", "1260"))
        actions.append(
            {
                "action": "add",
                "target_date": base_date,
                "title": "临时占用",
                "start_min": busy_start,
                "end_min": busy_end,
                "note": prompt[:80],
                "fixed": True,
                "category": "其他",
                "priority": 1,
            }
        )
        return actions

    mins = re.search(r"(\d{1,3})\s*分钟", prompt)
    if mins and day.events:
        budget = int(mins.group(1))
        for event in sort_events(day.events):
            duration = event["end_min"] - event["start_min"]
            if duration <= budget:
                actions.append(
                    {
                        "action": "edit",
                        "id": event["id"],
                        "title": f"{event['title']}（优先执行）",
                    }
                )
                break
    return actions


def normalize_ai_actions(raw_actions: list[dict[str, Any]], base_date: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []

    def pick_event_id_by_time(date_str: str, start_min: int | None, end_min: int | None) -> str | None:
        if start_min is None or end_min is None:
            return None
        for item in sort_events(ensure_day(date_str).events):
            if start_min < item["end_min"] and item["start_min"] < end_min:
                return item["id"]
        return None

    for raw in raw_actions:
        if not isinstance(raw, dict):
            continue
        action = dict(raw)
        act = str(action.get("action", "")).lower().strip()
        if act == "move":
            act = "edit"
        action["action"] = act

        src = (
            resolve_relative_date(action.get("source_date"), base_date)
            or resolve_relative_date(action.get("date"), base_date)
            or base_date
        )
        tgt = (
            resolve_relative_date(action.get("target_date"), base_date)
            or resolve_relative_date(action.get("date"), base_date)
            or src
        )
        action["source_date"] = src
        action["target_date"] = tgt

        # Common key aliases from model output
        if "start_min" not in action:
            for key in ("start", "time_start", "startTime"):
                if key in action:
                    action["start_min"] = action[key]
                    break
        if "end_min" not in action:
            for key in ("end", "time_end", "endTime"):
                if key in action:
                    action["end_min"] = action[key]
                    break

        # Normalize numeric fields
        for key in ("start_min", "end_min"):
            if key in action:
                try:
                    action[key] = int(action[key])
                except (TypeError, ValueError):
                    action.pop(key, None)

        # If id missing for edit/delete/complete, try infer by time overlap.
        if act in {"edit", "delete", "complete"} and not action.get("id"):
            inferred_id = pick_event_id_by_time(src, action.get("start_min"), action.get("end_min"))
            if inferred_id:
                action["id"] = inferred_id

        # If still missing id, fallback by title exact match in source day.
        if act in {"edit", "delete", "complete"} and not action.get("id") and action.get("title"):
            title = str(action.get("title")).strip()
            day_events = ensure_day(src).events
            exact = next((e for e in day_events if e.get("title") == title), None)
            if exact:
                action["id"] = exact["id"]

        # Normalize priority bounds
        if "priority" in action:
            try:
                action["priority"] = max(1, min(3, int(action["priority"])))
            except (TypeError, ValueError):
                action.pop("priority", None)

        # Ensure date format validity
        try:
            validate_date(action["source_date"])
            validate_date(action["target_date"])
        except HTTPException:
            action["source_date"] = base_date
            action["target_date"] = base_date

        if act == "add" and "date" in action:
            # keep target_date as authoritative for add
            action.pop("date", None)

        if act in {"delete", "complete"} and "target_date" not in action:
            action["target_date"] = action["source_date"]

        if act == "edit" and ("start_min" not in action and "end_min" not in action):
            # allow cross-day move without time change
            pass

        if act in {"delete", "complete"} and not action.get("id"):
            # reject ambiguous delete/complete without target id
            action["action"] = "invalid"

        if act == "add" and ("start_min" not in action or "end_min" not in action):
            action["action"] = "invalid"

        if act == "edit" and not action.get("id"):
            action["action"] = "invalid"

        if action["action"] == "invalid":
            normalized.append({"action": "invalid", "reason": "无法确定操作目标", "raw": raw})
            continue

        normalized.append(action)

    return normalized


def apply_actions(date: str, actions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    applied: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for action in actions:
        act = action.get("action")
        try:
            if act == "add":
                target_date = action.get("target_date", date)
                day = ensure_day(target_date)
                title = str(action.get("title", "未命名事件")).strip() or "未命名事件"
                start_min = int(action["start_min"])
                end_min = int(action["end_min"])
                validate_time_range(start_min, end_min)
                candidate = {
                    "id": str(uuid.uuid4()),
                    "title": title,
                    "start_min": start_min,
                    "end_min": end_min,
                    "status": "todo",
                    "note": str(action.get("note", "")),
                    "fixed": bool(action.get("fixed", False)),
                    "category": str(action.get("category", "学习")),
                    "location": str(action.get("location", "")),
                    "description": str(action.get("description", "")),
                    "priority": int(action.get("priority", 2)),
                }
                conflict = has_conflict(candidate, day.events)
                if conflict:
                    raise HTTPException(
                        status_code=409,
                        detail=f"与事件 {conflict['title']} 冲突（{conflict['start_min']}-{conflict['end_min']}）",
                    )
                day.events.append(candidate)
                day.events = sort_events(day.events)
                applied.append(
                    {
                        "action": "add",
                        "event_id": candidate["id"],
                        "title": candidate["title"],
                        "target_date": target_date,
                    }
                )
            elif act == "edit":
                source_date = action.get("source_date", date)
                target_date = action.get("target_date", source_date)
                source_day = ensure_day(source_date)
                target_day = ensure_day(target_date)
                target_id = str(action.get("id", ""))
                target = find_event(source_day.events, target_id)
                if not target:
                    raise HTTPException(status_code=404, detail=f"未找到事件 {target_id}")
                if target.get("fixed") and any(k in action for k in ("start_min", "end_min")):
                    raise HTTPException(status_code=400, detail=f"事件 {target_id} 为 fixed，不允许改时间")

                updated = dict(target)
                for field in ("title", "note", "fixed", "category", "location", "description"):
                    if field in action:
                        updated[field] = action[field]
                if "priority" in action:
                    updated["priority"] = int(action["priority"])
                if "start_min" in action:
                    updated["start_min"] = int(action["start_min"])
                if "end_min" in action:
                    updated["end_min"] = int(action["end_min"])
                validate_time_range(updated["start_min"], updated["end_min"])
                exclude_id = target_id if source_date == target_date else None
                conflict = has_conflict(updated, target_day.events, exclude_id=exclude_id)
                if conflict:
                    raise HTTPException(status_code=409, detail=f"编辑后与 {conflict['title']} 冲突")
                if source_date == target_date:
                    target.update(updated)
                    source_day.events = sort_events(source_day.events)
                else:
                    source_day.events.remove(target)
                    target_day.events.append(updated)
                    source_day.events = sort_events(source_day.events)
                    target_day.events = sort_events(target_day.events)
                applied.append(
                    {
                        "action": "edit",
                        "event_id": target_id,
                        "source_date": source_date,
                        "target_date": target_date,
                    }
                )
            elif act == "delete":
                source_date = action.get("source_date", date)
                day = ensure_day(source_date)
                target_id = str(action.get("id", ""))
                target = find_event(day.events, target_id)
                if not target:
                    raise HTTPException(status_code=404, detail=f"未找到事件 {target_id}")
                day.events.remove(target)
                day.events = sort_events(day.events)
                applied.append({"action": "delete", "event_id": target_id, "source_date": source_date})
            elif act == "complete":
                source_date = action.get("source_date", date)
                day = ensure_day(source_date)
                target_id = str(action.get("id", ""))
                target = find_event(day.events, target_id)
                if not target:
                    raise HTTPException(status_code=404, detail=f"未找到事件 {target_id}")
                day.events.remove(target)
                target["status"] = "done"
                day.completed.append(target)
                day.events = sort_events(day.events)
                day.completed = sort_events(day.completed)
                applied.append({"action": "complete", "event_id": target_id, "source_date": source_date})
            else:
                errors.append({"action": action, "error": "不支持的 action"})
        except HTTPException as exc:
            errors.append({"action": action, "error": exc.detail})
        except (TypeError, ValueError, KeyError) as exc:
            errors.append({"action": action, "error": f"动作参数非法: {exc}"})

    return applied, errors


@app.get("/")
def home():
    return {"message": "Momentum backend running ✅"}


@app.get("/api/ai/config")
def get_ai_config():
    model = (
        os.getenv("DASHSCOPE_MODEL", "").strip()
        or os.getenv("QWEN_MODEL", "").strip()
        or "qwen-plus"
    )
    return {
        "success": True,
        "data": {
            "model": model,
            "system_prompt": AI_SYSTEM_PROMPT,
            "policy": {
                "day_window_start_min": int(os.getenv("DAY_WINDOW_START_MIN", "360")),
                "day_window_end_min": int(os.getenv("DAY_WINDOW_END_MIN", "1320")),
                "busy_default_start_min": int(os.getenv("BUSY_DEFAULT_START_MIN", "1140")),
                "busy_default_end_min": int(os.getenv("BUSY_DEFAULT_END_MIN", "1260")),
            },
        },
    }


@app.get("/api/schedule")
def get_schedule(date: str = Query(..., description="YYYY-MM-DD")):
    day = ensure_day(date)
    day.events = sort_events(day.events)
    day.completed = sort_events(day.completed)
    return {"success": True, "data": day.model_dump()}


@app.post("/api/events")
def add_event(payload: EventCreate):
    day = ensure_day(payload.date)
    validate_time_range(payload.start_min, payload.end_min)
    new_event = {
        "id": str(uuid.uuid4()),
        "title": payload.title.strip() or "未命名事件",
        "start_min": payload.start_min,
        "end_min": payload.end_min,
        "status": "todo",
        "note": payload.note,
        "fixed": payload.fixed,
        "category": payload.category,
        "location": payload.location,
        "description": payload.description,
        "priority": payload.priority,
    }
    conflict = has_conflict(new_event, day.events)
    if conflict:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TIME_CONFLICT",
                "message": "时间冲突",
                "conflict_with": conflict,
            },
        )
    day.events.append(new_event)
    day.events = sort_events(day.events)
    return {"success": True, "message": "事件已新增", "data": new_event}


@app.patch("/api/events/{event_id}")
def edit_event(event_id: str, payload: EventUpdate):
    day = ensure_day(payload.date)
    target = find_event(day.events, event_id)
    if not target:
        raise HTTPException(status_code=404, detail="事件不存在")

    if target["fixed"] and (payload.start_min is not None or payload.end_min is not None):
        raise HTTPException(status_code=400, detail="fixed 事件不允许修改时间")

    updated = dict(target)
    if payload.title is not None:
        updated["title"] = payload.title.strip() or target["title"]
    if payload.start_min is not None:
        updated["start_min"] = payload.start_min
    if payload.end_min is not None:
        updated["end_min"] = payload.end_min
    if payload.note is not None:
        updated["note"] = payload.note
    if payload.fixed is not None:
        updated["fixed"] = payload.fixed
    if payload.category is not None:
        updated["category"] = payload.category
    if payload.location is not None:
        updated["location"] = payload.location
    if payload.description is not None:
        updated["description"] = payload.description
    if payload.priority is not None:
        updated["priority"] = payload.priority

    validate_time_range(updated["start_min"], updated["end_min"])
    conflict = has_conflict(updated, day.events, exclude_id=event_id)
    if conflict:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TIME_CONFLICT",
                "message": "编辑后时间冲突",
                "conflict_with": conflict,
            },
        )
    target.update(updated)
    day.events = sort_events(day.events)
    return {"success": True, "message": "事件已更新", "data": target}


@app.delete("/api/events/{event_id}")
def delete_event(event_id: str, date: str = Query(..., description="YYYY-MM-DD")):
    day = ensure_day(date)
    target = find_event(day.events, event_id)
    if not target:
        raise HTTPException(status_code=404, detail="事件不存在")
    day.events.remove(target)
    return {"success": True, "message": "事件已删除", "data": target}


@app.post("/api/events/{event_id}/complete")
def complete_event(event_id: str, payload: CompleteRequest):
    day = ensure_day(payload.date)
    if payload.completed:
        target = find_event(day.events, event_id)
        if not target:
            raise HTTPException(status_code=404, detail="事件不存在或已完成")
        day.events.remove(target)
        target["status"] = "done"
        day.completed.append(target)
        day.completed = sort_events(day.completed)
        return {"success": True, "message": "事件已标记完成", "data": target}

    target = find_event(day.completed, event_id)
    if not target:
        raise HTTPException(status_code=404, detail="已完成事件不存在")
    target["status"] = "todo"
    conflict = has_conflict(target, day.events)
    if conflict:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "TIME_CONFLICT",
                "message": "恢复后时间冲突",
                "conflict_with": conflict,
            },
        )
    day.completed.remove(target)
    day.events.append(target)
    day.events = sort_events(day.events)
    return {"success": True, "message": "事件已恢复到时间表", "data": target}


@app.post("/api/ai/replan")
def ai_replan(payload: AiReplanRequest):
    day = ensure_day(payload.date)
    snap = snapshot_store()
    raw_text = ""
    llm_summary = ""
    model_used = ""
    raw_actions: list[Any] = []

    try:
        raw_actions, model_used, raw_text, llm_summary = call_qwen_for_actions(
            payload.date, payload.prompt, day, repair_context=None
        )
        actions = normalize_ai_actions(raw_actions, payload.date)
        actions = [a for a in actions if a.get("action") != "invalid"]

        if not actions:
            actions = fallback_actions_from_prompt(payload.prompt, day)
            if not actions:
                return {
                    "success": True,
                    "message": "AI 未识别到可执行变更，已保留原课表",
                    "data": {
                        "applied": [],
                        "errors": [],
                        "raw_actions": raw_actions,
                        "llm_summary": llm_summary,
                        "raw_model_text": raw_text[:4000] if raw_text else "",
                        "schedule": ensure_day(payload.date).model_dump(),
                        "model_used": model_used,
                    },
                }

        applied, errors = apply_actions(payload.date, actions)

        if errors and model_used.startswith("dashscope:"):
            restore_store(snap)
            day = ensure_day(payload.date)
            repair = {
                "instruction": (
                    "上一轮 actions 在校验或落库时失败。请根据 errors 修正后，"
                    "重新输出完整 JSON（含 summary 与 actions）。"
                    "禁止编造 id；fixed 事件禁止改时间；跨天必须带 source_date 与 target_date。"
                ),
                "previous_actions": raw_actions,
                "errors": errors,
            }
            raw_actions, model_used, raw_text, llm_summary = call_qwen_for_actions(
                payload.date, payload.prompt, day, repair_context=repair
            )
            actions2 = normalize_ai_actions(raw_actions, payload.date)
            actions2 = [a for a in actions2 if a.get("action") != "invalid"]
            if actions2:
                applied, errors = apply_actions(payload.date, actions2)

        latest = ensure_day(payload.date)
        msg = "AI 重排已处理"
        if errors:
            msg = "AI 重排已处理（部分动作未通过校验，请查看 errors）"
        return {
            "success": True,
            "message": msg,
            "data": {
                "applied": applied,
                "errors": errors,
                "raw_actions": raw_actions,
                "llm_summary": llm_summary,
                "raw_model_text": raw_text[:4000] if raw_text else "",
                "schedule": latest.model_dump(),
                "model_used": model_used,
            },
        }
    except Exception:
        restore_store(snap)
        raise

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)