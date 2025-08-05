"""
KSEB 메인 서버의 일정(Event) 관련 API와 상호작용하는 LangChain 도구 모음.
"""

# 표준 라이브러리
import json
from datetime import datetime, timedelta
from typing import Optional, List

# 서드파티 라이브러리
import httpx
from langchain.tools import tool
from pydantic import BaseModel, Field

# 로컬 애플리케이션 라이브러리
from src.utils.api_client import client

# --- 도구 입력을 위한 Pydantic 스키마 정의 ---


class GetScheduleInput(BaseModel):
    """get_schedule 도구의 입력 스키마."""

    schedule_type: str = Field(
        ..., description="가져올 일정의 종류. 'personal' 또는 'group'이어야 합니다."
    )
    group_id: Optional[int] = Field(
        None, description="schedule_type이 'group'일 경우의 그룹 ID."
    )
    start_date: Optional[str] = Field(
        None,
        description="조회 시작 날짜 (YYYY-MM-DD 형식). 지정하지 않으면 모든 일정을 가져옵니다.",
    )
    end_date: Optional[str] = Field(
        None,
        description="조회 종료 날짜 (YYYY-MM-DD 형식). start_date와 함께 사용되어야 합니다.",
    )
    jwt_token: str = Field(..., description="API 인증을 위한 JWT 토큰.")


class CreateScheduleInput(BaseModel):
    """create_schedule 도구의 입력 스키마."""

    title: str = Field(..., description="생성할 일정의 제목.")
    start_time: str = Field(
        ..., description="일정 시작 시간 (ISO 8601 형식, 예: '2025-08-02T15:00:00')."
    )
    end_time: str = Field(
        ..., description="일정 종료 시간 (ISO 8601 형식, 예: '2025-08-02T16:00:00')."
    )
    schedule_type: str = Field(
        "personal", description="생성할 일정의 종류. 'personal' 또는 'group'."
    )
    group_id: Optional[int] = Field(
        None, description="schedule_type이 'group'일 경우의 그룹 ID."
    )
    jwt_token: str = Field(..., description="API 인증을 위한 JWT 토큰.")


class UpdateScheduleInput(BaseModel):
    """update_schedule 도구의 입력 스키마."""

    event_id: int = Field(
        ...,
        description="수정할 일정의 ID. 이 ID를 모를 경우, 먼저 일정을 조회하여 ID를 알아내야 한다고 사용자에게 안내해야 합니다.",
    )
    current_title: Optional[str] = Field(
        None, description="수정할 일정의 현재 제목. AI가 알고 있는 경우, 응답에 활용하기 위해 전달합니다."
    )
    title: Optional[str] = Field(None, description="새로운 일정 제목.")
    start_time: Optional[str] = Field(
        None, description="새로운 시작 시간 (ISO 8601 형식)."
    )
    end_time: Optional[str] = Field(
        None, description="새로운 종료 시간 (ISO 8601 형식)."
    )
    group_id: Optional[int] = Field(
        None, description="수정할 일정이 그룹 일정일 경우의 그룹 ID."
    )
    jwt_token: str = Field(..., description="API 인증을 위한 JWT 토큰.")


class DeleteScheduleInput(BaseModel):
    """delete_schedule 도구의 입력 스키마."""

    event_id: int = Field(
        ...,
        description="삭제할 일정의 ID. 이 ID를 모를 경우, 먼저 일정을 조회하여 ID를 알아내야 한다고 사용자에게 안내해야 합니다.",
    )
    title: Optional[str] = Field(
        None, description="삭제할 일정의 제목. AI가 알고 있는 경우, 응답에 활용하기 위해 전달합니다."
    )
    group_id: Optional[int] = Field(
        None, description="삭제할 일정이 그룹 일정일 경우의 그룹 ID."
    )
    jwt_token: str = Field(..., description="API 인증을 위한 JWT 토큰.")


class RecommendMeetingInput(BaseModel):
    """recommend_meeting_time 도구의 입력 스키마."""

    group_id: int = Field(..., description="회의 시간을 추천받을 그룹의 ID.")
    duration_minutes: int = Field(60, description="원하는 회의 시간(분 단위).")
    start_date: Optional[str] = Field(
        None,
        description="검색을 시작할 날짜 (YYYY-MM-DD 형식). 지정하지 않으면 오늘부터 검색합니다. '다음 주' 같은 요청이 있으면, 오늘 날짜를 기준으로 다음 주 월요일 날짜를 계산하여 이 필드에 넣어야 합니다.",
    )
    search_days: int = Field(
        7, description="지정된 start_date로부터 며칠까지 가능한 시간을 검색할지 여부."
    )
    jwt_token: str = Field(..., description="API 인증을 위한 JWT 토큰.")


# --- 헬퍼 함수 ---
async def _make_api_call(
    method: str,
    endpoint: str,
    jwt_token: str,
    params: Optional[dict] = None,
    json_data: Optional[dict] = None,
) -> dict:
    """메인 서버에 API 호출을 수행하는 헬퍼 함수."""
    headers = {"Authorization": f"Bearer {jwt_token}"}
    try:
        response = await client.request(
            method,
            endpoint,
            headers=headers,
            params=params,
            json=json_data,
            timeout=20.0,
        )
        response.raise_for_status()
        if response.status_code == 204:
            return {"success": True}
        return response.json()
    except httpx.HTTPStatusError as e:
        error_message = f"API 오류: {e.response.status_code} - {e.response.text}"
        print(error_message)
        return {"error": error_message}
    except httpx.RequestError as e:
        error_message = f"요청 오류: {e}"
        print(error_message)
        return {"error": error_message}


def _find_available_slots(
    schedules_bundle: dict,
    search_start: datetime,
    search_end: datetime,
    duration_minutes: int,
    time_window_start_hour: int = 9,
    time_window_end_hour: int = 22,
) -> List[dict]:
    """
    [개선된 알고리즘]
    모든 일정을 통합하고 정렬하여 '바쁜 시간' 목록을 만든 후,
    그 사이의 '빈 시간'을 찾아 다양한 시간대의 회의를 추천.
    """
    busy_intervals = []
    actual_data = schedules_bundle.get("data", schedules_bundle)

    all_events = []
    personal_events = actual_data.get("personalEvents") or actual_data.get("personal_events", [])
    group_events = actual_data.get("groupEvents") or actual_data.get("group_events", [])
    all_events.extend(personal_events)
    all_events.extend(group_events)

    # 1. 모든 이벤트를 '바쁜 시간' 간격으로 변환
    for event in all_events:
        start_str = event.get('start') or event.get('startDatetime')
        end_str = event.get('end') or event.get('endDatetime')

        if not (start_str and end_str):
            continue

        start_dt = datetime.fromisoformat(start_str)
        end_dt = datetime.fromisoformat(end_str)

        # '하루 종일' 일정 처리
        if event.get('allDay'):
            day_start = start_dt.replace(hour=time_window_start_hour, minute=0, second=0, microsecond=0)
            day_end = start_dt.replace(hour=time_window_end_hour, minute=0, second=0, microsecond=0)
            busy_intervals.append((day_start, day_end))
        else:
            busy_intervals.append((start_dt, end_dt))

    # 2. 겹치는 '바쁜 시간' 병합
    if not busy_intervals:
        merged_busy = []
    else:
        busy_intervals.sort(key=lambda x: x[0])
        merged_busy = [busy_intervals[0]]
        for current_start, current_end in busy_intervals[1:]:
            last_start, last_end = merged_busy[-1]
            if current_start < last_end:
                merged_busy[-1] = (last_start, max(last_end, current_end))
            else:
                merged_busy.append((current_start, current_end))

    # 3. '빈 시간'을 찾아 회의 가능한 모든 슬롯 추출
    all_possible_slots = []
    test_time = search_start.replace(hour=time_window_start_hour, minute=0)

    while test_time < search_end:
        day_end = test_time.replace(hour=time_window_end_hour, minute=0)

        # 현재 test_time이 포함된 '바쁜 시간' 찾기
        is_busy = False
        for busy_start, busy_end in merged_busy:
            if test_time < busy_end and test_time + timedelta(minutes=duration_minutes) > busy_start:
                # 이 '바쁜 시간'이 끝나는 시간으로 바로 점프
                test_time = busy_end
                is_busy = True
                break

        if is_busy:
            continue

        # 현재 시간이 업무 시간을 벗어나면 다음 날로 이동
        if test_time.hour < time_window_start_hour:
            test_time = test_time.replace(hour=time_window_start_hour, minute=0)

        potential_end = test_time + timedelta(minutes=duration_minutes)
        if potential_end <= day_end:
            all_possible_slots.append({"start": test_time.isoformat(), "end": potential_end.isoformat()})

        # 30분 단위로 다음 시간 탐색
        test_time += timedelta(minutes=30)
        if test_time.hour >= time_window_end_hour:
            test_time = (test_time + timedelta(days=1)).replace(hour=time_window_start_hour, minute=0)

    # 4. 다양한 시간대의 추천 슬롯 선택
    if not all_possible_slots:
        return []

    recommendations = []
    slots_by_day = {}
    for slot in all_possible_slots:
        day = slot["start"][:10]
        if day not in slots_by_day:
            slots_by_day[day] = {"morning": [], "afternoon": []}

        start_hour = int(slot["start"][11:13])
        if start_hour < 14:
            slots_by_day[day]["morning"].append(slot)
        else:
            slots_by_day[day]["afternoon"].append(slot)

    # 날짜 순으로 정렬된 키
    sorted_days = sorted(slots_by_day.keys())

    # 최대 9개까지 다양한 슬롯 선택
    for day in sorted_days:
        if len(recommendations) >= 9:
            break
        if slots_by_day[day]["morning"]:
            recommendations.append(slots_by_day[day]["morning"][0]) # 각 날짜의 첫 오전 슬롯

        if len(recommendations) >= 9:
            break
        if slots_by_day[day]["afternoon"]:
            recommendations.append(slots_by_day[day]["afternoon"][0]) # 각 날짜의 첫 오후 슬롯

    # 만약 위에서 9개가 채워지지 않았다면, 가장 빠른 시간부터 순서대로 채움
    if len(recommendations) < 9:
        # 이미 추가된 슬롯을 제외하고 추가
        existing_starts = {r['start'] for r in recommendations}
        for slot in all_possible_slots:
            if len(recommendations) >= 9:
                break
            if slot['start'] not in existing_starts:
                recommendations.append(slot)

    return recommendations[:9]


# --- LangChain 도구 ---


@tool("get_schedule", args_schema=GetScheduleInput)
async def get_schedule(
    schedule_type: str,
    group_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    jwt_token: str = "",
) -> str:
    """개인 또는 그룹 일정을 기간으로 필터링하여 가져옴."""
    params = {}
    if start_date:
        try:
            # YYYY-MM-DD 형식의 날짜 문자열을 datetime 객체로 변환
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            # 해당 날짜의 시작 시간(00:00:00)으로 설정하고 ISO 형식으로 변환
            params["startDate"] = start_dt.replace(hour=0, minute=0, second=0).isoformat()

            # end_date가 없으면 start_date와 동일하게 설정
            end_dt_str = end_date or start_date
            end_dt = datetime.strptime(end_dt_str, "%Y-%m-%d")
            # 해당 날짜의 끝 시간(23:59:59)으로 설정하고 ISO 형식으로 변환
            params["endDate"] = end_dt.replace(hour=23, minute=59, second=59).isoformat()

        except ValueError:
            return json.dumps({
                "tool": "get_schedule",
                "error": "날짜 형식이 잘못되었습니다. 'YYYY-MM-DD' 형식을 사용해야 합니다."
            })

    if schedule_type == "personal":
        endpoint = "/api/users/me/events"
    elif schedule_type == "group":
        if not group_id:
            return json.dumps(
                {
                    "tool": "get_schedule",
                    "error": "그룹 일정을 조회하려면 group_id가 필요합니다.",
                }
            )
        endpoint = f"/api/groups/{group_id}/events"
    else:
        return json.dumps(
            {
                "tool": "get_schedule",
                "error": "schedule_type은 'personal' 또는 'group'이어야 합니다.",
            }
        )

    result = await _make_api_call("GET", endpoint, jwt_token, params=params)
    return json.dumps({"tool": "get_schedule", "data": result})


@tool("create_schedule", args_schema=CreateScheduleInput)
async def create_schedule(
    title: str,
    start_time: str,
    end_time: str,
    schedule_type: str = "personal",
    group_id: Optional[int] = None,
    jwt_token: str = "",
) -> str:
    """새로운 개인 또는 그룹 일정을 생성함."""
    payload = {
        "title": title,
        "startDatetime": start_time,
        "endDatetime": end_time,
        "allDay": False,
        "themeColor": "#3b82f6",  # 기본 테마 색상 추가
    }
    if schedule_type == "personal":
        endpoint = "/api/users/me/events"
    elif schedule_type == "group":
        if not group_id:
            return "오류: 그룹 일정을 생성하려면 group_id가 필요합니다."
        endpoint = f"/api/groups/{group_id}/events"
    else:
        return "오류: schedule_type은 'personal' 또는 'group'이어야 합니다."
    result = await _make_api_call("POST", endpoint, jwt_token, json_data=payload)
    if "error" in result:
        return f"일정 생성에 실패했습니다: {result['error']}"

    # 성공 시, 생성된 일정 정보를 포함한 JSON 반환
    response_data = {
        "tool": "create_schedule",
        "data": {
            "message": f"'{title}' 일정이 성공적으로 생성되었습니다.",
            "created_event_details": {
                "eventId": result.get("data", {}).get("eventId"), # 백엔드 응답에서 eventId 추출
                "title": title,
                "start": start_time, # 필드 이름 통일 (start_time -> start)
                "end": end_time,     # 필드 이름 통일 (end_time -> end)
                "ownerType": schedule_type.upper(), # "GROUP" 또는 "USER"
                "ownerId": group_id if schedule_type == "group" else None,
                "themeColor": "#22c55e", # 성공 시 녹색
            }
        }
    }
    return json.dumps(response_data)


@tool("update_schedule", args_schema=UpdateScheduleInput)
async def update_schedule(
    event_id: int,
    current_title: Optional[str] = None,
    title: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    group_id: Optional[int] = None,
    jwt_token: str = "",
) -> str:
    """ID로 기존 일정의 제목, 시작 시간 또는 종료 시간을 수정함."""
    payload = {}
    if title:
        payload["title"] = title
    if start_time:
        payload["startDatetime"] = start_time
    if end_time:
        payload["endDatetime"] = end_time
    if not payload:
        return "오류: 수정할 정보가 없습니다."
    endpoint = (
        f"/api/groups/{group_id}/events/{event_id}"
        if group_id
        else f"/api/users/me/events/{event_id}"
    )
    result = await _make_api_call("PATCH", endpoint, jwt_token, json_data=payload)
    if "error" in result:
        return f"일정 수정에 실패했습니다: {result['error']}"

    display_title = title or current_title or f"일정(ID: {event_id})"

    response_data = {
        "tool": "update_schedule",
        "data": {
            "message": f"'{display_title}' 일정이 성공적으로 수정되었습니다.",
            "updated_event_details": {
                "eventId": event_id,
                "updated_fields": payload
            }
        }
    }
    return json.dumps(response_data)


@tool("delete_schedule", args_schema=DeleteScheduleInput)
async def delete_schedule(
    event_id: int,
    title: Optional[str] = None,
    group_id: Optional[int] = None,
    jwt_token: str = "",
) -> str:
    """ID를 사용하여 기존 일정을 삭제함."""
    endpoint = (
        f"/api/groups/{group_id}/events/{event_id}"
        if group_id
        else f"/api/users/me/events/{event_id}"
    )
    result = await _make_api_call("DELETE", endpoint, jwt_token)
    if "error" in result:
        return f"일정 삭제에 실패했습니다: {result['error']}"

    response_data = {
        "tool": "delete_schedule",
        "data": {
            "message": f"'{title}' 일정이 성공적으로 삭제되었습니다.",
            "deleted_event_details": {
                "eventId": event_id,
                "title": title or f"ID: {event_id}"
            }
        }
    }
    return json.dumps(response_data)


@tool("recommend_meeting_time", args_schema=RecommendMeetingInput)
async def recommend_meeting_time(
    group_id: int,
    duration_minutes: int = 60,
    start_date: Optional[str] = None,
    search_days: int = 7,
    jwt_token: str = "",
) -> str:
    """그룹 멤버들의 일정을 분석하여 회의 시간을 추천. '다음 주'와 같은 시간 표현은 start_date로 변환하여 사용."""
    # start_date가 있으면 파싱하고, 없으면 오늘 날짜를 사용
    if start_date:
        try:
            start_time = datetime.fromisoformat(start_date)
        except ValueError:
            return json.dumps({"tool": "recommend_meeting_time", "error": "잘못된 날짜 형식입니다. YYYY-MM-DD 형식을 사용해주세요."})
    else:
        start_time = datetime.now()

    # 검색 시작 시간을 0시 0분으로 설정
    search_start_time = start_time.replace(hour=0, minute=0, second=0, microsecond=0)
    search_end_time = search_start_time + timedelta(days=search_days)

    endpoint = f"/api/groups/{group_id}/events/all-schedules"
    params = {"from": search_start_time.isoformat(), "to": search_end_time.isoformat()}
    schedules_bundle = await _make_api_call("GET", endpoint, jwt_token, params=params)

    if schedules_bundle.get("error"):
        return json.dumps(
            {"tool": "recommend_meeting_time", "error": schedules_bundle["error"]}
        )

    available_slots = _find_available_slots(
        schedules_bundle, search_start_time, search_end_time, duration_minutes
    )

    if not available_slots:
        return json.dumps(
            {
                "tool": "recommend_meeting_time",
                "data": {"message": "모든 멤버가 참여 가능한 시간을 찾지 못했습니다."},
            }
        )
    return json.dumps(
        {
            "tool": "recommend_meeting_time",
            "data": {"recommendations": available_slots, "group_id": group_id},
        }
    )
