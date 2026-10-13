"""Native GLArea device view with worker-loaded GLB triangles and PNG fallback."""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from threading import Thread
from typing import Any

try:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk

    GTK_AVAILABLE = True
except (ImportError, ValueError):  # permits parser tests without GTK
    GTK_AVAILABLE = False


@dataclass(frozen=True, slots=True)
class TriangleBatch:
    """One material-coloured, world-transformed triangle stream."""

    vertices: tuple[float, ...]
    color: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class ModelGeometry:
    """Renderable triangle batches extracted from every scene node."""

    batches: tuple[TriangleBatch, ...]

    @property
    def vertices(self) -> tuple[float, ...]:
        """Flattened positions, retained for lightweight geometry consumers."""
        return tuple(coordinate for batch in self.batches for coordinate in batch.vertices)

    @property
    def triangle_count(self) -> int:
        return sum(len(batch.vertices) // 9 for batch in self.batches)


_MAT4 = tuple[float, ...]
_IDENTITY: _MAT4 = (1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0)
_COMPONENT_FORMATS = {5121: "B", 5123: "H", 5125: "I"}


def _matrix_multiply(left: _MAT4, right: _MAT4) -> _MAT4:
    """Multiply column-major glTF matrices so ``left`` is applied last."""
    return tuple(
        sum(left[row + column * 4] * right[column + source * 4] for column in range(4))
        for source in range(4)
        for row in range(4)
    )


def _node_matrix(node: dict[str, Any]) -> _MAT4:
    if "matrix" in node:
        matrix = node["matrix"]
        if not isinstance(matrix, list) or len(matrix) != 16:
            raise ValueError("node matrix must contain 16 values")
        return tuple(float(value) for value in matrix)

    translation = node.get("translation", (0.0, 0.0, 0.0))
    rotation = node.get("rotation", (0.0, 0.0, 0.0, 1.0))
    scale = node.get("scale", (1.0, 1.0, 1.0))
    if len(translation) != 3 or len(rotation) != 4 or len(scale) != 3:
        raise ValueError("invalid node TRS")
    x, y, z, w = (float(value) for value in rotation)
    sx, sy, sz = (float(value) for value in scale)
    tx, ty, tz = (float(value) for value in translation)
    # glTF uses T * R * S; each column of R is scaled for column-major storage.
    return (
        (1 - 2 * (y * y + z * z)) * sx,
        (2 * (x * y + z * w)) * sx,
        (2 * (x * z - y * w)) * sx,
        0.0,
        (2 * (x * y - z * w)) * sy,
        (1 - 2 * (x * x + z * z)) * sy,
        (2 * (y * z + x * w)) * sy,
        0.0,
        (2 * (x * z + y * w)) * sz,
        (2 * (y * z - x * w)) * sz,
        (1 - 2 * (x * x + y * y)) * sz,
        0.0,
        tx,
        ty,
        tz,
        1.0,
    )


def _transform_point(
    matrix: _MAT4, point: tuple[float, float, float]
) -> tuple[float, float, float]:
    x, y, z = point
    transformed = (
        matrix[0] * x + matrix[4] * y + matrix[8] * z + matrix[12],
        matrix[1] * x + matrix[5] * y + matrix[9] * z + matrix[13],
        matrix[2] * x + matrix[6] * y + matrix[10] * z + matrix[14],
        matrix[3] * x + matrix[7] * y + matrix[11] * z + matrix[15],
    )
    if transformed[3] == 0:
        raise ValueError("node transform produced a point at infinity")
    return tuple(value / transformed[3] for value in transformed[:3])


def _read_accessor(
    document: dict[str, Any],
    binary: bytes,
    accessor_index: int,
    *,
    expected_type: str,
    formats: dict[int, str],
) -> list[tuple[float, ...]]:
    accessors = document.get("accessors", [])
    views = document.get("bufferViews", [])
    try:
        accessor = accessors[accessor_index]
        view = views[accessor["bufferView"]]
    except (IndexError, KeyError, TypeError) as exc:
        raise ValueError("accessor has no usable buffer view") from exc
    component_type = accessor.get("componentType")
    component_format = formats.get(component_type)
    if component_format is None or accessor.get("type") != expected_type:
        raise ValueError(f"unsupported {expected_type} accessor")
    components = 3 if expected_type == "VEC3" else 1
    component_size = struct.calcsize("<" + component_format)
    item_size = component_size * components
    stride = view.get("byteStride", item_size)
    if not isinstance(stride, int) or stride < item_size:
        raise ValueError("invalid accessor stride")
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    count = accessor.get("count")
    if not isinstance(start, int) or not isinstance(count, int) or count < 0:
        raise ValueError("invalid accessor range")
    end = start + (max(count - 1, 0) * stride) + item_size
    if start < 0 or end > len(binary):
        raise ValueError("accessor extends beyond GLB binary chunk")
    unpacker = "<" + component_format * components
    return [
        tuple(float(value) for value in struct.unpack_from(unpacker, binary, start + item * stride))
        for item in range(count)
    ]


def _positions(
    document: dict[str, Any], binary: bytes, accessor_index: int
) -> list[tuple[float, float, float]]:
    values = _read_accessor(
        document, binary, accessor_index, expected_type="VEC3", formats={5126: "f"}
    )
    return [(value[0], value[1], value[2]) for value in values]


def _indices(document: dict[str, Any], binary: bytes, accessor_index: int) -> list[int]:
    values = _read_accessor(
        document, binary, accessor_index, expected_type="SCALAR", formats=_COMPONENT_FORMATS
    )
    return [int(value[0]) for value in values]


def _base_color(
    document: dict[str, Any], primitive: dict[str, Any]
) -> tuple[float, float, float, float]:
    material_index = primitive.get("material")
    if material_index is None:
        return (0.70, 0.76, 0.82, 1.0)
    try:
        material = document.get("materials", [])[material_index]
        factor = material.get("pbrMetallicRoughness", {}).get(
            "baseColorFactor", (1.0, 1.0, 1.0, 1.0)
        )
    except (IndexError, TypeError) as exc:
        raise ValueError("primitive references an invalid material") from exc
    if not isinstance(factor, list | tuple) or len(factor) != 4:
        raise ValueError("material baseColorFactor must contain four values")
    return tuple(float(value) for value in factor)


def _parse_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    if len(data) < 20:
        raise ValueError("GLB is too short")
    magic, version, length = struct.unpack_from("<4sII", data)
    if magic != b"glTF" or version != 2 or length != len(data):
        raise ValueError("invalid GLB header")
    offset = 12
    json_length, json_type = struct.unpack_from("<I4s", data, offset)
    offset += 8
    if json_type != b"JSON" or offset + json_length > len(data):
        raise ValueError("GLB has no valid JSON chunk")
    document = json.loads(data[offset : offset + json_length].decode("utf-8"))
    offset += json_length
    if offset + 8 > len(data):
        raise ValueError("GLB has no binary chunk")
    binary_length, binary_type = struct.unpack_from("<I4s", data, offset)
    offset += 8
    if binary_type != b"BIN\x00" or offset + binary_length > len(data):
        raise ValueError("GLB has no valid binary chunk")
    return document, data[offset : offset + binary_length]


def load_glb_geometry(path: Path) -> ModelGeometry:
    """Load every indexed TRIANGLES primitive in every glTF scene node.

    Positions are transformed into world coordinates on the worker thread, so the
    GL render path only submits coloured triangles and never parses model data.
    """
    document, binary = _parse_glb(path)
    nodes = document.get("nodes", [])
    meshes = document.get("meshes", [])
    scenes = document.get("scenes", [])
    if not isinstance(nodes, list) or not isinstance(meshes, list) or not isinstance(scenes, list):
        raise ValueError("invalid glTF scene structure")

    roots: list[int] = []
    for scene in scenes:
        roots.extend(scene.get("nodes", []))
    if not roots and nodes:
        roots = list(range(len(nodes)))
    batches: list[TriangleBatch] = []

    def visit(node_index: int, parent: _MAT4, ancestry: frozenset[int]) -> None:
        if node_index in ancestry:
            raise ValueError("cyclic glTF node graph")
        try:
            node = nodes[node_index]
        except IndexError as exc:
            raise ValueError("scene references an invalid node") from exc
        world = _matrix_multiply(parent, _node_matrix(node))
        mesh_index = node.get("mesh")
        if mesh_index is not None:
            try:
                primitives = meshes[mesh_index].get("primitives", [])
            except (IndexError, TypeError) as exc:
                raise ValueError("node references an invalid mesh") from exc
            for primitive in primitives:
                if primitive.get("mode", 4) != 4:
                    continue
                try:
                    position_accessor = primitive["attributes"]["POSITION"]
                    index_accessor = primitive["indices"]
                except KeyError as exc:
                    raise ValueError("triangle primitive requires indexed POSITION data") from exc
                positions = _positions(document, binary, position_accessor)
                indices = _indices(document, binary, index_accessor)
                if len(indices) % 3:
                    raise ValueError("triangle index count is not divisible by three")
                vertices: list[float] = []
                for index in indices:
                    try:
                        vertices.extend(_transform_point(world, positions[index]))
                    except IndexError as exc:
                        raise ValueError("triangle index is outside POSITION accessor") from exc
                if vertices:
                    batches.append(TriangleBatch(tuple(vertices), _base_color(document, primitive)))
        for child in node.get("children", []):
            visit(child, world, ancestry | {node_index})

    for root in roots:
        visit(root, _IDENTITY, frozenset())
    if not batches:
        raise ValueError("model has no indexed triangle primitives")
    return ModelGeometry(tuple(batches))


# Retain the original parser entry point for callers from the first UI draft.
load_glb_positions = load_glb_geometry


if GTK_AVAILABLE:

    class DeviceModelView(Gtk.Stack):
        """GLB triangle renderer that stays idle while its screen is hidden."""

        def __init__(self, model_path: Path, preview_path: Path, low_power: bool = False) -> None:
            super().__init__()
            self._model_path, self._render_enabled = model_path, False
            self._geometry: ModelGeometry | None = None
            self._model_center = (0.0, 0.0, 0.0)
            self._model_scale = 1.0
            self._rotation = (22.0, -32.0)
            self._drag_origin = self._rotation
            self._auto_rotate = True
            self._pinch_origin = 1.0
            self._zoom = 1.0
            self._fps = 15 if low_power else 30
            self._tick_id = 0
            self._gl_ready = False
            self._display_list = 0
            self._area = Gtk.GLArea(hexpand=True, vexpand=True)
            self._area.set_required_version(2, 1)
            self._area.connect("realize", self._on_realize)
            self._area.connect("unrealize", self._on_unrealize)
            self._area.connect("render", self._on_render)
            drag = Gtk.GestureDrag()
            drag.connect("drag-begin", self._on_drag_begin)
            drag.connect("drag-update", self._on_drag_update)
            self._area.add_controller(drag)
            scroll = Gtk.EventControllerScroll.new(Gtk.EventControllerScrollFlags.VERTICAL)
            scroll.connect("scroll", self._on_scroll)
            self._area.add_controller(scroll)
            pinch = Gtk.GestureZoom()
            pinch.connect("begin", self._on_pinch_begin)
            pinch.connect("scale-changed", self._on_pinch)
            self._area.add_controller(pinch)
            self.add_named(self._area, "gl")
            fallback = Gtk.Box(
                orientation=Gtk.Orientation.VERTICAL, spacing=8, valign=Gtk.Align.CENTER
            )
            picture = Gtk.Picture.new_for_filename(str(preview_path))
            picture.set_can_shrink(True)
            picture.set_content_fit(Gtk.ContentFit.CONTAIN)
            fallback.append(picture)
            message = Gtk.Label(label="無法啟用 3D，改用靜態模型預覽")
            message.add_css_class("fallback")
            fallback.append(message)
            self.add_named(fallback, "fallback")
            self.set_visible_child_name("fallback")
            Thread(target=self._load_model, name="deskos-glb-loader", daemon=True).start()

        def _load_model(self) -> None:
            try:
                geometry = load_glb_geometry(self._model_path)
            except (
                OSError,
                ValueError,
                KeyError,
                IndexError,
                UnicodeDecodeError,
                struct.error,
            ) as exc:
                GLib.idle_add(self._model_failed, str(exc))
            else:
                GLib.idle_add(self._model_loaded, geometry)

        def _model_loaded(self, geometry: ModelGeometry) -> bool:
            self._geometry = geometry
            points = list(zip(*[iter(geometry.vertices)] * 3, strict=False))
            minimum = tuple(min(point[axis] for point in points) for axis in range(3))
            maximum = tuple(max(point[axis] for point in points) for axis in range(3))
            self._model_center = tuple((minimum[axis] + maximum[axis]) / 2 for axis in range(3))
            largest_span = max(maximum[axis] - minimum[axis] for axis in range(3))
            self._model_scale = 3.0 / largest_span if largest_span else 1.0
            if self._gl_ready:
                self.set_visible_child_name("gl")
                if self._render_enabled:
                    self._area.queue_render()
            return False

        def _model_failed(self, _message: str) -> bool:
            self.set_visible_child_name("fallback")
            return False

        def _on_realize(self, area: Gtk.GLArea) -> None:
            area.make_current()
            self._gl_ready = area.get_error() is None
            if self._gl_ready and self._geometry is not None:
                self.set_visible_child_name("gl")
            elif not self._gl_ready:
                self.set_visible_child_name("fallback")

        def _on_unrealize(self, area: Gtk.GLArea) -> None:
            if not self._display_list:
                return
            try:
                from OpenGL import GL

                area.make_current()
                if area.get_error() is None:
                    GL.glDeleteLists(self._display_list, 1)
            finally:
                self._display_list = 0

        def _compile_display_list(self, GL: Any) -> None:
            """Upload the static 95k-triangle model once instead of per frame."""
            if self._display_list or self._geometry is None:
                return
            display_list = int(GL.glGenLists(1))
            if not display_list:
                raise RuntimeError("OpenGL display lists are unavailable")
            GL.glNewList(display_list, GL.GL_COMPILE)
            try:
                for batch in self._geometry.batches:
                    GL.glColor4f(*batch.color)
                    GL.glBegin(GL.GL_TRIANGLES)
                    for x, y, z in zip(*[iter(batch.vertices)] * 3, strict=False):
                        GL.glVertex3f(
                            (x - self._model_center[0]) * self._model_scale,
                            (y - self._model_center[1]) * self._model_scale,
                            (z - self._model_center[2]) * self._model_scale,
                        )
                    GL.glEnd()
            finally:
                GL.glEndList()
            self._display_list = display_list

        def _on_render(self, area: Gtk.GLArea, _context: object) -> bool:
            if not self._render_enabled or self._geometry is None:
                return True
            try:
                from OpenGL import GL

                width, height = max(1, area.get_width()), max(1, area.get_height())
                GL.glViewport(0, 0, width, height)
                GL.glClearColor(0.06, 0.10, 0.16, 1.0)
                GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)
                GL.glEnable(GL.GL_DEPTH_TEST)
                GL.glMatrixMode(GL.GL_PROJECTION)
                GL.glLoadIdentity()
                aspect = width / height
                GL.glFrustum(-aspect, aspect, -1.0, 1.0, 2.0, 20.0)
                GL.glMatrixMode(GL.GL_MODELVIEW)
                GL.glLoadIdentity()
                GL.glTranslatef(0.0, 0.0, -max(3.2, 6.0 / self._zoom))
                GL.glRotatef(self._rotation[0], 1.0, 0.0, 0.0)
                GL.glRotatef(self._rotation[1], 0.0, 1.0, 0.0)
                self._compile_display_list(GL)
                GL.glCallList(self._display_list)
            except Exception:
                self.set_visible_child_name("fallback")
            return True

        def _queue_render(self) -> None:
            if self._render_enabled and self.get_visible_child_name() == "gl":
                self._area.queue_render()

        def _on_drag_begin(self, _gesture: Gtk.GestureDrag, _x: float, _y: float) -> None:
            self._auto_rotate = False
            self._drag_origin = self._rotation

        def _on_drag_update(
            self, _gesture: Gtk.GestureDrag, offset_x: float, offset_y: float
        ) -> None:
            self._rotation = (
                self._drag_origin[0] + offset_y * 0.35,
                self._drag_origin[1] + offset_x * 0.35,
            )
            self._queue_render()

        def _on_scroll(self, _controller: Gtk.EventControllerScroll, _dx: float, dy: float) -> bool:
            self._auto_rotate = False
            self._zoom = min(3.0, max(0.45, self._zoom * math.pow(1.12, -dy)))
            self._queue_render()
            return True

        def _on_pinch_begin(self, _gesture: Gtk.GestureZoom, _sequence: object) -> None:
            self._auto_rotate = False
            self._pinch_origin = self._zoom

        def _on_pinch(self, _gesture: Gtk.GestureZoom, scale: float) -> None:
            self._zoom = min(3.0, max(0.45, self._pinch_origin * scale))
            self._queue_render()

        def set_camera_view(self, view: str) -> None:
            rotations = {
                "top": (90.0, 0.0),
                "front": (0.0, 0.0),
                "right": (0.0, 90.0),
                "iso": (22.0, -32.0),
            }
            self._rotation = rotations[view]
            self._zoom = 1.0
            self._auto_rotate = view == "iso"
            self._queue_render()

        def set_render_enabled(self, enabled: bool) -> None:
            self._render_enabled = enabled
            if enabled and self._tick_id == 0:
                self._tick_id = GLib.timeout_add(int(1000 / self._fps), self._tick)
                self._queue_render()
            elif not enabled and self._tick_id:
                GLib.source_remove(self._tick_id)
                self._tick_id = 0

        def _tick(self) -> bool:
            if not self._render_enabled:
                self._tick_id = 0
                return False
            if self._auto_rotate:
                self._rotation = (self._rotation[0], self._rotation[1] + 0.12)
                self._queue_render()
            return True
else:

    class DeviceModelView:  # type: ignore[no-redef]
        def __init__(self, *_: object, **__: object) -> None:
            raise RuntimeError("GTK 4 is unavailable")
