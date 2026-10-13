from pathlib import Path

from deskos.ui.device import load_glb_positions

MODEL_PATH = Path(__file__).parents[2] / "assets/models/raspberry_pi_4_model.glb"


def test_bundled_glb_loads_multiple_mesh_triangle_batches() -> None:
    geometry = load_glb_positions(MODEL_PATH)

    assert len(geometry.batches) > 1
    assert geometry.triangle_count > 0
    assert all(
        len(batch.vertices) > 0 and len(batch.vertices) % 9 == 0 for batch in geometry.batches
    )


def test_bundled_glb_batches_preserve_material_colors() -> None:
    geometry = load_glb_positions(MODEL_PATH)

    assert any(batch.color != (0.70, 0.76, 0.82, 1.0) for batch in geometry.batches)
    assert all(0.0 <= channel <= 1.0 for batch in geometry.batches for channel in batch.color)
