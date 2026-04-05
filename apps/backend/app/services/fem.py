import math

import numpy as np

from app.schemas.analysis import (
    CalculationRequest,
    CalculationResponse,
    NodalLoad,
    QuasiStaticStep,
    QuasiStaticStepResult,
)


def _assemble_stiffness(request: CalculationRequest, node_index: dict[str, int]) -> np.ndarray:
    dof = 2 * len(request.nodes)
    k_global = np.zeros((dof, dof), dtype=float)

    for rod in request.rods:
        i = node_index.get(rod.start_node_id)
        j = node_index.get(rod.end_node_id)
        if i is None or j is None:
            continue

        ni = request.nodes[i]
        nj = request.nodes[j]
        dx = nj.x - ni.x
        dy = nj.y - ni.y
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            continue

        c = dx / length
        s = dy / length
        ae_l = (rod.area * rod.elastic_modulus) / length

        k_local = ae_l * np.array(
            [
                [c * c, c * s, -c * c, -c * s],
                [c * s, s * s, -c * s, -s * s],
                [-c * c, -c * s, c * c, c * s],
                [-c * s, -s * s, c * s, s * s],
            ],
            dtype=float,
        )

        map_dof = [2 * i, 2 * i + 1, 2 * j, 2 * j + 1]
        for r in range(4):
            for c_idx in range(4):
                k_global[map_dof[r], map_dof[c_idx]] += k_local[r, c_idx]

    return k_global


def _run_static_fem(request: CalculationRequest) -> CalculationResponse:
    if not request.nodes:
        return CalculationResponse(displacements={}, stresses={}, analysis_type="static", quasi_static_steps=[])

    node_index = {node.id: idx for idx, node in enumerate(request.nodes)}
    dof = 2 * len(request.nodes)

    k_global = _assemble_stiffness(request, node_index)
    force = np.zeros(dof, dtype=float)

    for load in request.loads:
        idx = node_index.get(load.node_id)
        if idx is None:
            continue
        force[2 * idx] += load.fx
        force[2 * idx + 1] += load.fy

    fixed_dofs: set[int] = set()
    if request.constraints:
        for constraint in request.constraints:
            idx = node_index.get(constraint.node_id)
            if idx is None:
                continue
            if constraint.ux_fixed:
                fixed_dofs.add(2 * idx)
            if constraint.uy_fixed:
                fixed_dofs.add(2 * idx + 1)
    else:
        fixed_dofs.update({0, 1})

    free_dofs = [d for d in range(dof) if d not in fixed_dofs]
    u = np.zeros(dof, dtype=float)

    if free_dofs:
        k_ff = k_global[np.ix_(free_dofs, free_dofs)]
        f_f = force[free_dofs]
        reg = 1e-9 * np.eye(len(free_dofs), dtype=float)
        try:
            u_f = np.linalg.solve(k_ff + reg, f_f)
        except np.linalg.LinAlgError:
            u_f, *_ = np.linalg.lstsq(k_ff + reg, f_f, rcond=None)
        for local_idx, global_idx in enumerate(free_dofs):
            u[global_idx] = u_f[local_idx]

    stresses: dict[str, float] = {}
    for rod in request.rods:
        i = node_index.get(rod.start_node_id)
        j = node_index.get(rod.end_node_id)
        if i is None or j is None:
            stresses[rod.id] = 0.0
            continue

        ni = request.nodes[i]
        nj = request.nodes[j]
        dx = nj.x - ni.x
        dy = nj.y - ni.y
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            stresses[rod.id] = 0.0
            continue

        c = dx / length
        s = dy / length
        axial_strain = (c * (u[2 * j] - u[2 * i]) + s * (u[2 * j + 1] - u[2 * i + 1])) / length
        stresses[rod.id] = rod.elastic_modulus * axial_strain

    displacements = {
        node.id: float(math.hypot(u[2 * idx], u[2 * idx + 1]))
        for idx, node in enumerate(request.nodes)
    }

    return CalculationResponse(displacements=displacements, stresses=stresses, analysis_type="static", quasi_static_steps=[])


def _default_quasi_static_steps() -> list[QuasiStaticStep]:
    return [
        QuasiStaticStep(step_index=1, name="Step 1", load_factor=0.25),
        QuasiStaticStep(step_index=2, name="Step 2", load_factor=0.5),
        QuasiStaticStep(step_index=3, name="Step 3", load_factor=0.75),
        QuasiStaticStep(step_index=4, name="Step 4", load_factor=1.0),
    ]


def _build_step_loads(base_loads: list[NodalLoad], step: QuasiStaticStep) -> list[NodalLoad]:
    factor = step.load_factor
    result: list[NodalLoad] = []
    for base in base_loads:
        fx = step.load_fx if step.load_fx is not None else base.fx * factor
        fy = step.load_fy if step.load_fy is not None else base.fy * factor
        result.append(NodalLoad(node_id=base.node_id, fx=fx, fy=fy))
    return result


def run_fem(request: CalculationRequest) -> CalculationResponse:
    if request.analysis_type != "quasi_static":
        return _run_static_fem(request)

    steps = request.quasi_static_steps or _default_quasi_static_steps()
    step_results: list[QuasiStaticStepResult] = []
    last_result = CalculationResponse(displacements={}, stresses={}, analysis_type="static", quasi_static_steps=[])

    for idx, step in enumerate(steps, start=1):
        normalized_step_index = step.step_index if step.step_index is not None else idx
        step_name = step.name or f"Step {normalized_step_index}"
        step_request = request.model_copy(
            update={
                "loads": _build_step_loads(request.loads, step),
                "analysis_type": "static",
                "quasi_static_steps": [],
            }
        )
        last_result = _run_static_fem(step_request)
        step_results.append(
            QuasiStaticStepResult(
                step_index=normalized_step_index,
                name=step_name,
                load_factor=step.load_factor,
                displacements=last_result.displacements,
                stresses=last_result.stresses,
            )
        )

    return CalculationResponse(
        displacements=last_result.displacements,
        stresses=last_result.stresses,
        analysis_type="quasi_static",
        quasi_static_steps=step_results,
    )
