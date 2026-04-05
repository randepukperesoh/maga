from app.celery_app import celery_app
from app.services.training_runtime import run_training_job


@celery_app.task(name="training.run_model")
def run_model_training_task(
    *,
    epochs: int,
    learning_rate: float,
    model_family: str,
    base_weights: dict[str, float],
    base_trained_steps: int,
    dataset_size: int = 0,
    defect_rate: float | None = None,
    notebook_defect_prior: float | None = None,
    dataset_items: list[dict] | None = None,
) -> dict:
    return run_training_job(
        epochs=epochs,
        learning_rate=learning_rate,
        model_family=model_family,
        base_weights=base_weights,
        base_trained_steps=base_trained_steps,
        dataset_size=dataset_size,
        defect_rate=defect_rate,
        notebook_defect_prior=notebook_defect_prior,
        dataset_items=dataset_items,
    )
