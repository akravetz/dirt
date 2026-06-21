"""Local execution for claimed breeding logbook cloud commands."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.cloud_contract import (
    BreedingBulkCullPayload,
    BreedingBulkMovePayload,
    BreedingBulkPlantFactsPayload,
    BreedingBulkPlantNotePayload,
    BreedingBulkSexPayload,
    BreedingClonePlantsPayload,
    BreedingCreatePlantNotePayload,
    BreedingCreateSeedLotPayload,
    BreedingGerminatePlantsPayload,
    ClaimedCommand,
)
from dirt_shared.models import (
    CrossEvent,
    Plant,
    PlantEvent,
    PlantLine,
    PlantLkuSex,
    PlantLocationHistory,
    PlantNote,
    SeedLot,
    SeedLotLkuSexType,
    Tent,
)
from dirt_shared.services.scope import require_default_site_pk


class BreedingCommandError(ValueError):
    """Raised when a breeding command cannot be applied locally."""


@dataclass(frozen=True)
class _ResolvedTent:
    site_pk: int
    tent_pk: int
    name: str
    role: str


class BreedingCommandExecutor:
    def __init__(
        self,
        engine: AsyncEngine,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._clock = clock

    async def execute(self, item: ClaimedCommand) -> dict[str, Any]:
        payload = item.payload
        async with AsyncSession(self._engine) as session, session.begin():
            if isinstance(payload, BreedingCreateSeedLotPayload):
                return await self._create_seed_lot(session, item.site_id, payload)
            if isinstance(payload, BreedingGerminatePlantsPayload):
                return await self._germinate(session, item.site_id, payload)
            if isinstance(payload, BreedingClonePlantsPayload):
                return await self._clone(session, item.site_id, payload)
            if isinstance(payload, BreedingBulkSexPayload):
                return await self._bulk_sex(session, payload)
            if isinstance(payload, BreedingBulkMovePayload):
                return await self._bulk_move(session, item.site_id, payload)
            if isinstance(payload, BreedingBulkPlantFactsPayload):
                return await self._bulk_update_facts(session, payload)
            if isinstance(payload, BreedingBulkCullPayload):
                return await self._bulk_cull(session, payload)
            if isinstance(payload, BreedingCreatePlantNotePayload):
                return await self._create_note(
                    session,
                    payload,
                    created_by=item.requested_by or None,
                )
            if isinstance(payload, BreedingBulkPlantNotePayload):
                return await self._bulk_create_notes(
                    session,
                    payload,
                    created_by=item.requested_by or None,
                )
        raise BreedingCommandError(f"unsupported breeding payload: {type(payload)}")

    async def _create_seed_lot(
        self,
        session: AsyncSession,
        site_id: str,
        payload: BreedingCreateSeedLotPayload,
    ) -> dict[str, Any]:
        await _require_site_pk(session, site_id)
        await _require_seed_lot_sex_type(session, payload.sex_type_key)

        if payload.source == "purchased":
            line = await _get_or_create_line(
                session,
                project_code=payload.prefix,
                generation_label=payload.generation,
                strain=_require(payload.strain, "strain"),
                cultivar=_require(payload.cultivar, "cultivar"),
                source_name=_require(payload.source_name, "source_name"),
            )
            seed_lot = SeedLot(
                line_id=_pk(line),
                sex_type_key=payload.sex_type_key,
                is_purchased=True,
                vendor_name=payload.vendor_name,
                acquired_at=payload.acquired_at,
                seed_count=payload.seed_count,
                notes=payload.notes,
            )
            session.add(seed_lot)
            await session.flush()
            return _seed_lot_result(seed_lot, line)

        seed_parent = await _require_plant(session, payload.seed_parent_plant_key)
        pollen_parent = await _require_plant(session, payload.pollen_parent_plant_key)
        seed_line = await _require_line(session, seed_parent.line_id)
        pollen_line = await _require_line(session, pollen_parent.line_id)
        line = await _get_or_create_line(
            session,
            project_code=payload.prefix,
            generation_label=payload.generation,
            strain=payload.strain
            or _combined_label(seed_line.strain, pollen_line.strain),
            cultivar=payload.cultivar
            or _combined_label(seed_line.cultivar, pollen_line.cultivar),
            source_name=payload.source_name
            or f"{seed_parent.key} x {pollen_parent.key}",
        )
        cross = CrossEvent(
            resulting_line_id=_pk(line),
            seed_parent_plant_id=_pk(seed_parent),
            pollen_parent_plant_id=_pk(pollen_parent),
            pollinated_at=payload.pollinated_at or self._clock(),
            pollen_parent_is_reversed=payload.pollen_parent_is_reversed,
            notes=payload.notes,
        )
        session.add(cross)
        await session.flush()
        seed_lot = SeedLot(
            line_id=_pk(line),
            sex_type_key=payload.sex_type_key,
            is_purchased=False,
            produced_by_cross_event_id=_pk(cross),
            seed_count=payload.seed_count,
            notes=payload.notes,
        )
        session.add(seed_lot)
        await session.flush()
        result = _seed_lot_result(seed_lot, line)
        result["source_cross_event_id"] = _pk(cross)
        return result

    async def _germinate(
        self,
        session: AsyncSession,
        site_id: str,
        payload: BreedingGerminatePlantsPayload,
    ) -> dict[str, Any]:
        tent = await _require_tent(session, site_id, payload.source_tent_id)
        seed_lot = await _require_seed_lot(session, payload.seed_lot_source_id)
        line = await _require_line(session, seed_lot.line_id)
        occurred_at = payload.germinated_at or self._clock()
        keys = await _allocate_keys(session, _plant_prefix(line), payload.count)
        plants: list[Plant] = []
        for key in keys:
            plant = Plant(
                key=key,
                name=key,
                line_id=_pk(line),
                sex_key="unknown",
                source_seed_lot_id=_pk(seed_lot),
                germinated_at=occurred_at,
            )
            session.add(plant)
            plants.append(plant)
        await session.flush()
        for plant in plants:
            session.add(
                PlantLocationHistory(
                    plant_id=_pk(plant),
                    site_id=tent.site_pk,
                    tent_id=tent.tent_pk,
                    grid_position=None,
                    start_at=occurred_at,
                )
            )
        await session.flush()
        return {
            "created_plant_ids": [_pk(plant) for plant in plants],
            "created_plant_keys": keys,
            "source_seed_lot_id": _pk(seed_lot),
            "line_id": _pk(line),
        }

    async def _clone(
        self,
        session: AsyncSession,
        site_id: str,
        payload: BreedingClonePlantsPayload,
    ) -> dict[str, Any]:
        tent = await _require_tent(session, site_id, payload.source_tent_id)
        mother = await _require_plant(session, payload.mother_plant_key)
        occurred_at = payload.taken_at or self._clock()
        keys = await _allocate_keys(session, f"{mother.key}-C", payload.count)
        clones: list[Plant] = []
        for key in keys:
            clone = Plant(
                key=key,
                name=key,
                line_id=mother.line_id,
                sex_key=mother.sex_key,
                clone_source_plant_id=_pk(mother),
                taken_at=occurred_at,
            )
            session.add(clone)
            clones.append(clone)
        await session.flush()
        for clone in clones:
            session.add(
                PlantLocationHistory(
                    plant_id=_pk(clone),
                    site_id=tent.site_pk,
                    tent_id=tent.tent_pk,
                    grid_position=None,
                    start_at=occurred_at,
                )
            )
        session.add(
            PlantEvent(
                plant_id=_pk(mother),
                is_clone_taken=True,
                occurred_at=occurred_at,
                metadata_json={"clone_keys": keys},
            )
        )
        await session.flush()
        return {
            "mother_plant_id": _pk(mother),
            "mother_plant_key": mother.key,
            "created_plant_ids": [_pk(clone) for clone in clones],
            "created_plant_keys": keys,
        }

    async def _bulk_sex(
        self,
        session: AsyncSession,
        payload: BreedingBulkSexPayload,
    ) -> dict[str, Any]:
        await _require_plant_sex(session, payload.sex_key)
        plants = await _require_plants(session, payload.plant_keys)
        occurred_at = self._clock()
        for plant in plants:
            plant.sex_key = payload.sex_key
            plant.updated_at = occurred_at
            session.add(plant)
            session.add(
                PlantEvent(
                    plant_id=_pk(plant),
                    is_sex_observation=True,
                    occurred_at=occurred_at,
                    metadata_json={"sex_key": payload.sex_key},
                )
            )
        await session.flush()
        return {
            "updated_plant_ids": [_pk(plant) for plant in plants],
            "updated_plant_keys": [plant.key for plant in plants],
            "sex_key": payload.sex_key,
        }

    async def _bulk_move(
        self,
        session: AsyncSession,
        site_id: str,
        payload: BreedingBulkMovePayload,
    ) -> dict[str, Any]:
        tent = await _require_tent(session, site_id, payload.source_tent_id)
        plants = await _require_plants(session, payload.plant_keys)
        occurred_at = self._clock()
        from_tent_ids: dict[str, int | None] = {}
        for plant in plants:
            current = await _current_location(session, _pk(plant))
            if current is not None:
                from_tent_ids[plant.key] = current.tent_id
                current.end_at = occurred_at
                session.add(current)
            else:
                from_tent_ids[plant.key] = None
            plant.updated_at = occurred_at
            session.add(plant)
            session.add(
                PlantLocationHistory(
                    plant_id=_pk(plant),
                    site_id=tent.site_pk,
                    tent_id=tent.tent_pk,
                    grid_position=None,
                    start_at=occurred_at,
                )
            )
            session.add(
                PlantEvent(
                    plant_id=_pk(plant),
                    is_transplant=True,
                    occurred_at=occurred_at,
                    metadata_json={
                        "from_tent_id": from_tent_ids[plant.key],
                        "to_tent_id": tent.tent_pk,
                    },
                )
            )
        await session.flush()
        return {
            "moved_plant_ids": [_pk(plant) for plant in plants],
            "moved_plant_keys": [plant.key for plant in plants],
            "target_tent_id": tent.tent_pk,
            "grid_position": None,
        }

    async def _bulk_update_facts(
        self,
        session: AsyncSession,
        payload: BreedingBulkPlantFactsPayload,
    ) -> dict[str, Any]:
        sex_update = next(
            (update for update in payload.updates if update.field == "sex_key"),
            None,
        )
        if sex_update is not None:
            await _require_plant_sex(session, str(sex_update.value))
        plants = await _require_plants(session, payload.plant_keys)
        occurred_at = self._clock()
        for plant in plants:
            for update in payload.updates:
                if update.field == "sex_key":
                    plant.sex_key = str(update.value)
                elif update.field == "germinated_at":
                    plant.germinated_at = update.value
                elif update.field == "taken_at":
                    plant.taken_at = update.value
                elif update.field == "rooted_at":
                    plant.rooted_at = update.value
                elif update.field == "veg_started_at":
                    plant.veg_started_at = update.value
                elif update.field == "flower_started_at":
                    plant.flower_started_at = update.value
            plant.updated_at = occurred_at
            session.add(plant)
        await session.flush()
        return {
            "updated_plant_ids": [_pk(plant) for plant in plants],
            "updated_plant_keys": [plant.key for plant in plants],
            "updated_fields": [update.field for update in payload.updates],
        }

    async def _bulk_cull(
        self,
        session: AsyncSession,
        payload: BreedingBulkCullPayload,
    ) -> dict[str, Any]:
        plants = await _require_plants(session, payload.plant_keys)
        occurred_at = self._clock()
        for plant in plants:
            plant.culled_at = occurred_at
            plant.culled_reason = payload.reason
            plant.updated_at = occurred_at
            session.add(plant)
            current = await _current_location(session, _pk(plant))
            if current is not None:
                current.end_at = occurred_at
                session.add(current)
        await session.flush()
        return {
            "culled_plant_ids": [_pk(plant) for plant in plants],
            "culled_plant_keys": [plant.key for plant in plants],
            "culled_at": occurred_at.isoformat(),
            "reason": payload.reason,
        }

    async def _create_note(
        self,
        session: AsyncSession,
        payload: BreedingCreatePlantNotePayload,
        *,
        created_by: str | None,
    ) -> dict[str, Any]:
        plant = await _require_plant(session, payload.plant_key)
        observed_at = payload.observed_at or self._clock()
        note = PlantNote(
            plant_id=_pk(plant),
            observed_at=observed_at,
            body=payload.body,
            created_by=created_by,
        )
        session.add(note)
        await session.flush()
        return {
            "source_note_id": _pk(note),
            "plant_id": _pk(plant),
            "plant_key": plant.key,
            "observed_at": observed_at.isoformat(),
        }

    async def _bulk_create_notes(
        self,
        session: AsyncSession,
        payload: BreedingBulkPlantNotePayload,
        *,
        created_by: str | None,
    ) -> dict[str, Any]:
        plants = await _require_plants(session, payload.plant_keys)
        observed_at = payload.observed_at or self._clock()
        notes = [
            PlantNote(
                plant_id=_pk(plant),
                observed_at=observed_at,
                body=payload.body,
                created_by=created_by,
            )
            for plant in plants
        ]
        session.add_all(notes)
        await session.flush()
        return {
            "source_note_ids": [_pk(note) for note in notes],
            "plant_ids": [_pk(plant) for plant in plants],
            "plant_keys": [plant.key for plant in plants],
            "observed_at": observed_at.isoformat(),
        }


async def _require_site_pk(session: AsyncSession, site_id: str) -> int:
    del site_id
    return await require_default_site_pk(session)


async def _require_tent(
    session: AsyncSession,
    site_id: str,
    source_tent_id: int,
) -> _ResolvedTent:
    site_pk = await _require_site_pk(session, site_id)
    tent = await session.get(Tent, source_tent_id)
    if tent is None or tent.site_id != site_pk:
        raise BreedingCommandError(f"unknown source_tent_id: {source_tent_id}")
    return _ResolvedTent(
        site_pk=site_pk,
        tent_pk=source_tent_id,
        name=tent.name,
        role=tent.role,
    )


async def _require_seed_lot(session: AsyncSession, seed_lot_id: int) -> SeedLot:
    seed_lot = await session.get(SeedLot, seed_lot_id)
    if seed_lot is None:
        raise BreedingCommandError(f"unknown seed lot source id: {seed_lot_id}")
    return seed_lot


async def _require_line(session: AsyncSession, line_id: int) -> PlantLine:
    line = await session.get(PlantLine, line_id)
    if line is None:
        raise BreedingCommandError(f"unknown plant line id: {line_id}")
    return line


async def _require_plant(
    session: AsyncSession,
    plant_key: str | None,
) -> Plant:
    if plant_key is None:
        raise BreedingCommandError("missing plant key")
    plant = (await session.exec(select(Plant).where(Plant.key == plant_key))).first()
    if plant is None:
        raise BreedingCommandError(f"unknown plant key: {plant_key}")
    return plant


async def _require_plants(
    session: AsyncSession,
    plant_keys: list[str],
) -> list[Plant]:
    plants = (
        await session.exec(select(Plant).where(col(Plant.key).in_(plant_keys)))
    ).all()
    by_key = {plant.key: plant for plant in plants}
    missing = [key for key in plant_keys if key not in by_key]
    if missing:
        raise BreedingCommandError(f"unknown plant key(s): {', '.join(missing)}")
    return [by_key[key] for key in plant_keys]


async def _require_plant_sex(session: AsyncSession, sex_key: str) -> None:
    row = await session.get(PlantLkuSex, sex_key)
    if row is None:
        raise BreedingCommandError(f"unknown plant sex key: {sex_key}")


async def _require_seed_lot_sex_type(
    session: AsyncSession,
    sex_type_key: str,
) -> None:
    row = await session.get(SeedLotLkuSexType, sex_type_key)
    if row is None:
        raise BreedingCommandError(f"unknown seed lot sex type key: {sex_type_key}")


async def _get_or_create_line(  # noqa: PLR0913
    session: AsyncSession,
    *,
    project_code: str | None,
    generation_label: str | None,
    strain: str,
    cultivar: str,
    source_name: str | None,
) -> PlantLine:
    stmt = (
        select(PlantLine)
        .where(PlantLine.project_code == project_code)
        .where(PlantLine.generation_label == generation_label)
        .where(PlantLine.strain == strain)
        .where(PlantLine.cultivar == cultivar)
        .where(PlantLine.source_name == source_name)
    )
    existing = (await session.exec(stmt)).first()
    if existing is not None:
        return existing
    line = PlantLine(
        project_code=project_code,
        generation_label=generation_label,
        strain=strain,
        cultivar=cultivar,
        source_name=source_name,
    )
    session.add(line)
    await session.flush()
    return line


async def _allocate_keys(
    session: AsyncSession,
    prefix: str,
    count: int,
) -> list[str]:
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    rows = (
        await session.exec(select(Plant.key).where(col(Plant.key).startswith(prefix)))
    ).all()
    used_suffixes = {
        int(match.group(1)) for key in rows if (match := pattern.match(key)) is not None
    }
    next_suffix = max(used_suffixes, default=0) + 1
    keys: list[str] = []
    while len(keys) < count:
        if next_suffix not in used_suffixes:
            keys.append(f"{prefix}-{next_suffix:03d}")
        next_suffix += 1
    return keys


async def _current_location(
    session: AsyncSession,
    plant_id: int,
) -> PlantLocationHistory | None:
    return (
        await session.exec(
            select(PlantLocationHistory)
            .where(PlantLocationHistory.plant_id == plant_id)
            .where(PlantLocationHistory.end_at.is_(None))
        )
    ).first()


def _plant_prefix(line: PlantLine) -> str:
    parts = [line.project_code, line.generation_label]
    prefix = "-".join(part for part in parts if part)
    if prefix:
        return prefix
    return re.sub(r"[^A-Za-z0-9]+", "-", line.strain).strip("-").upper()


def _combined_label(left: str, right: str) -> str:
    if left == right:
        return left
    return f"{left} x {right}"


def _seed_lot_result(seed_lot: SeedLot, line: PlantLine) -> dict[str, Any]:
    return {
        "source_seed_lot_id": _pk(seed_lot),
        "line_id": _pk(line),
        "project_code": line.project_code,
        "generation_label": line.generation_label,
        "strain": line.strain,
        "cultivar": line.cultivar,
        "source_name": line.source_name,
    }


def _require(value: str | None, field_name: str) -> str:
    if value is None:
        raise BreedingCommandError(f"missing {field_name}")
    return value


def _pk(row: Any) -> int:
    row_id = row.id
    if row_id is None:
        raise BreedingCommandError(f"{type(row).__name__} is missing primary key")
    return row_id
