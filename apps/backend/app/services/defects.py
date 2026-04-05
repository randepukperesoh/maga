from app.schemas.analysis import CalculationRequest, CalculationResponse
from app.schemas.defect import Defect, DefectIn


class DefectStore:
    def __init__(self) -> None:
        self._items: dict[str, Defect] = {}

    def add(self, defect_id: str, item: DefectIn) -> Defect:
        defect = Defect(id=defect_id, **item.model_dump())
        self._items[defect_id] = defect
        return defect

    def update(self, defect_id: str, item: DefectIn) -> Defect | None:
        if defect_id not in self._items:
            return None
        defect = Defect(id=defect_id, **item.model_dump())
        self._items[defect_id] = defect
        return defect

    def delete(self, defect_id: str) -> bool:
        return self._items.pop(defect_id, None) is not None

    def by_rod(self, rod_id: str) -> list[Defect]:
        return [d for d in self._items.values() if d.rod_id == rod_id]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _kt_for_defect(defect: Defect) -> float:
    params = defect.params or {}
    t = defect.defect_type.lower()

    if t == "crack":
        depth = float(params.get("depth", 0.0))
        width = float(params.get("width", 10.0))
        ratio = depth / max(width, 1e-6)
        return 1.0 + 2.5 * _clamp(ratio, 0.0, 1.0)

    if t == "corrosion":
        depth = float(params.get("depth", 0.0))
        thickness = float(params.get("thickness", 10.0))
        ratio = depth / max(thickness, 1e-6)
        return 1.0 + 1.8 * _clamp(ratio, 0.0, 1.0)

    if t == "section_reduction":
        area_factor = float(params.get("areaFactor", 1.0))
        safe = _clamp(area_factor, 0.2, 1.0)
        return 1.0 / safe

    if t == "material_inhomogeneity":
        e_factor = float(params.get("eFactor", 1.0))
        safe = _clamp(e_factor, 0.3, 1.0)
        return 1.0 + (1.0 - safe)

    return 1.0


def _adjust_stresses(
    request: CalculationRequest, stresses: dict[str, float], store: "DefectStore"
) -> dict[str, float]:
    adjusted = dict(stresses)
    for rod in request.rods:
        rod_defects = store.by_rod(rod.id)
        if not rod_defects:
            continue
        combined_kt = 1.0
        for d in rod_defects:
            combined_kt *= _kt_for_defect(d)
        adjusted[rod.id] = adjusted.get(rod.id, 0.0) * combined_kt
    return adjusted


def apply_defects_to_result(
    request: CalculationRequest, base: CalculationResponse, store: "DefectStore"
) -> CalculationResponse:
    adjusted_steps = [
        step.model_copy(update={"stresses": _adjust_stresses(request, step.stresses, store)})
        for step in base.quasi_static_steps
    ]
    adjusted_final = _adjust_stresses(request, base.stresses, store)
    return CalculationResponse(
        displacements=base.displacements,
        node_displacements=base.node_displacements,
        stresses=adjusted_final,
        analysis_type=base.analysis_type,
        quasi_static_steps=adjusted_steps,
    )


defects = DefectStore()
