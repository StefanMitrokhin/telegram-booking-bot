"""FSM state groups."""

from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ClientStates(StatesGroup):
    waiting_phone = State()


class SvcCreate(StatesGroup):
    name = State()
    duration = State()
    price = State()
    description = State()


class SvcEdit(StatesGroup):
    value = State()


class SpCreate(StatesGroup):
    name = State()
    bio = State()


class SpEdit(StatesGroup):
    value = State()


class SchInterval(StatesGroup):
    start = State()
    end = State()


class SchCustom(StatesGroup):
    start = State()
    end = State()


class BroadcastStates(StatesGroup):
    text = State()
    preview = State()


class ExportStates(StatesGroup):
    date_from = State()
    date_to = State()
