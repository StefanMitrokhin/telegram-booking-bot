"""CallbackData definitions."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData

FSM_ABORT = "fsm:abort"
NOOP = "noop"


class MenuCD(CallbackData, prefix="menu"):
    action: str


class SvcsCD(CallbackData, prefix="svcs"):
    page: int


class SvcCD(CallbackData, prefix="svc"):
    id: int


class SpCD(CallbackData, prefix="sp"):
    service_id: int
    specialist_id: int


class CalCD(CallbackData, prefix="cal"):
    service_id: int
    specialist_id: int
    year: int
    month: int


class DayCD(CallbackData, prefix="day"):
    service_id: int
    specialist_id: int
    ymd: int


class SlotsCD(CallbackData, prefix="slots"):
    service_id: int
    specialist_id: int
    ymd: int
    page: int


class SlotCD(CallbackData, prefix="slot"):
    service_id: int
    specialist_id: int
    ymd: int
    minute: int


class OkCD(CallbackData, prefix="ok"):
    service_id: int
    specialist_id: int
    ymd: int
    minute: int


class MyCD(CallbackData, prefix="my"):
    page: int


class BkCD(CallbackData, prefix="bk"):
    action: str
    id: int
    page: int


class AdmCD(CallbackData, prefix="adm"):
    action: str


class ASvcCD(CallbackData, prefix="asvc"):
    action: str
    id: int
    page: int


class ASpCD(CallbackData, prefix="asp"):
    action: str
    id: int
    page: int


class ALinkCD(CallbackData, prefix="alink"):
    specialist_id: int
    service_id: int


class ASchCD(CallbackData, prefix="asch"):
    action: str
    specialist_id: int
    item_id: int


class AWeekCD(CallbackData, prefix="awd"):
    specialist_id: int
    weekday: int


class ACalCD(CallbackData, prefix="acal"):
    purpose: str
    specialist_id: int
    year: int
    month: int


class ADateCD(CallbackData, prefix="adt"):
    purpose: str
    specialist_id: int
    ymd: int


class AExcCD(CallbackData, prefix="aex"):
    action: str
    specialist_id: int
    ymd: int


class ABkCD(CallbackData, prefix="abk"):
    action: str
    id: int
    ymd: int


class AExpCD(CallbackData, prefix="aexp"):
    period: str
    kind: str


class ABrCD(CallbackData, prefix="abr"):
    action: str
