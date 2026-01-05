#!/usr/bin/env python3
"""
Convert VRM (glTF/GLB) files to FBX using available local tools.

Auto mode preference order:
  1) Blender (bpy) if `blender` is on PATH
  2) Assimp CLI if `assimp` is on PATH
  3) pyassimp if installed
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Optional


def _which(tool: str) -> Optional[str]:
    return shutil.which(tool)


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")


def _convert_with_blender(vrm_path: str, fbx_path: str, blender_bin: str) -> None:
    # Use a small temp script to avoid leaving state in the user's Blender config.
    script = f"""\
import bpy
import sys

argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else []
if len(argv) != 2:
    raise SystemExit("Usage: blender -b --python <script> -- <input.vrm> <output.fbx>")
in_path, out_path = argv

# Clear default scene.
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)

# Import VRM as glTF (VRM is GLB with extensions).
bpy.ops.import_scene.gltf(filepath=in_path)

# Export FBX with conservative options.
bpy.ops.export_scene.fbx(
    filepath=out_path,
    use_selection=False,
    apply_scale_options='FBX_SCALE_UNITS',
    add_leaf_bones=False,
)
"""
    with tempfile.NamedTemporaryFile("w", suffix="_vrm_to_fbx.py", delete=False) as tmp:
        tmp.write(script)
        tmp_path = tmp.name
    try:
        _run([blender_bin, "-b", "--python", tmp_path, "--", vrm_path, fbx_path])
    finally:
        os.unlink(tmp_path)
    if not os.path.exists(fbx_path):
        raise RuntimeError("Blender reported success but output FBX was not created")


def _convert_with_assimp(vrm_path: str, fbx_path: str, assimp_bin: str) -> None:
    _run([assimp_bin, "export", vrm_path, fbx_path])


def _convert_with_pyassimp(vrm_path: str, fbx_path: str) -> None:
    try:
        import pyassimp  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("pyassimp is not installed") from exc
    scene = pyassimp.load(vrm_path)
    try:
        pyassimp.export(scene, fbx_path, file_type="fbx")
    finally:
        pyassimp.release(scene)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert VRM to FBX.")
    parser.add_argument("input", help="Path to input .vrm")
    parser.add_argument("output", help="Path to output .fbx")
    parser.add_argument(
        "--method",
        choices=["auto", "blender", "assimp", "pyassimp"],
        default="auto",
        help="Conversion backend to use.",
    )
    args = parser.parse_args()

    vrm_path = os.path.abspath(args.input)
    fbx_path = os.path.abspath(args.output)

    if not os.path.exists(vrm_path):
        print(f"Input not found: {vrm_path}", file=sys.stderr)
        return 2

    try:
        if args.method in ("auto", "blender"):
            blender_bin = _which("blender")
            if blender_bin:
                _convert_with_blender(vrm_path, fbx_path, blender_bin)
                print(f"FBX written via Blender: {fbx_path}")
                return 0
            if args.method == "blender":
                raise RuntimeError("Blender not found on PATH")

        if args.method in ("auto", "assimp"):
            assimp_bin = _which("assimp")
            if assimp_bin:
                _convert_with_assimp(vrm_path, fbx_path, assimp_bin)
                print(f"FBX written via assimp: {fbx_path}")
                return 0
            if args.method == "assimp":
                raise RuntimeError("assimp not found on PATH")

        if args.method in ("auto", "pyassimp"):
            _convert_with_pyassimp(vrm_path, fbx_path)
            print(f"FBX written via pyassimp: {fbx_path}")
            return 0

    except Exception as exc:
        print(f"Conversion failed: {exc}", file=sys.stderr)
        return 1

    print(
        "No conversion backend found. Install Blender or assimp, "
        "or install pyassimp and try again.",
        file=sys.stderr,
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
