#!/usr/bin/env python3
"""
build_engine.py - Build C++ engine shared library for Linux.

Usage:
  python build_engine.py                    # Build with g++ (requires g++ installed)
  python build_engine.py --use-wsl          # Build via WSL (requires WSL installed on Windows)
"""

import subprocess
import sys
from pathlib import Path


def _engine_paths():
    agents_dir = Path(__file__).resolve().parent
    source_path = agents_dir / "engine.cpp"
    library_path = agents_dir / "_engine.so"
    return agents_dir, source_path, library_path


def build_with_gcc(force: bool = False) -> bool:
    """Build using system g++ (Unix/Linux/WSL)."""
    agents_dir, source_path, library_path = _engine_paths()
    
    if not force and library_path.exists() and library_path.stat().st_mtime >= source_path.stat().st_mtime:
        print(f"_engine.so is up-to-date, skipping build. Use --force to rebuild.")
        return True
    
    cmd = [
        "g++",
        "-std=c++20",
        "-O2",
        "-march=x86-64",
        "-mtune=generic",
        "-shared",
        "-fPIC",
        "-static-libstdc++",
        "-static-libgcc",
        str(source_path),
        "-o",
        str(library_path),
    ]
    
    print(f"Building with g++...")
    print(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(agents_dir))
    
    if result.returncode == 0:
        print(f"✅ Built successfully: {library_path}")
        print(f"   File size: {library_path.stat().st_size / 1024 / 1024:.2f} MB")
        # Check if it's ELF format
        try:
            magic = library_path.read_bytes()[:4]
            if magic == b'\x7fELF':
                print("   Format: ELF (Linux-compatible) ✓")
            else:
                print(f"   Format: Unknown (magic: {magic.hex()})")
        except Exception as e:
            print(f"   Format check failed: {e}")
        return True
    else:
        print(f"❌ Build failed with return code {result.returncode}")
        return False


def build_with_wsl(force: bool = False) -> bool:
    """Build via WSL on Windows."""
    import platform
    
    if platform.system() != "Windows":
        print("WSL option is for Windows only. Use g++ directly on Linux/macOS.")
        return False
    
    agents_dir, source_path, library_path = _engine_paths()
    
    if not force and library_path.exists() and library_path.stat().st_mtime >= source_path.stat().st_mtime:
        print(f"_engine.so is up-to-date, skipping build. Use --force to rebuild.")
        return True
    
    # Convert path to WSL path
    wsl_path = str(agents_dir).replace("\\", "/").replace("C:", "/mnt/c")
    
    cmd = [
        "wsl",
        "bash",
        "-c",
        f"cd {wsl_path} && g++ -std=c++20 -O2 -march=x86-64 -mtune=generic -shared -fPIC -static-libstdc++ -static-libgcc engine.cpp -o _engine.so",
    ]
    
    print(f"Building via WSL...")
    print(f"  Command: {' '.join(cmd[:3])} ...")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print(f"✅ Built successfully via WSL: {library_path}")
        return True
    else:
        print(f"❌ WSL build failed with return code {result.returncode}")
        print("\n   To fix, ensure WSL is installed with build tools:")
        print("   PowerShell (as Admin):")
        print("     wsl --install")
        print("   Then in WSL terminal:")
        print("     sudo apt-get update && sudo apt-get install -y build-essential")
        return False


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Build C++ engine shared library for Linux")
    parser.add_argument(
        "--use-wsl",
        action="store_true",
        help="Build via WSL (Windows + WSL required)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force rebuild even if _engine.so is up-to-date",
    )
    args = parser.parse_args()
    
    if args.use_wsl:
        success = build_with_wsl(force=args.force)
    else:
        success = build_with_gcc(force=args.force)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()