# Hướng dẫn Build C++ Engine cho Kaggle

## Vấn đề

Kaggle nộp submissions bị lỗi: `invalid ELF header` khi load `_engine.so`

**Nguyên nhân**: File `.so` được build trên Windows không tương thích với Linux của Kaggle.
- Windows ELF header khác Linux ELF header
- Kaggle chạy Linux, nên cần `.so` được build trên Linux

## Giải pháp

### Cách 1: Build trên WSL (Windows Subsystem for Linux) - **Nhanh nhất**

Nếu bạn chưa cài WSL:

```powershell
# PowerShell (run as Admin)
wsl --install

# Sau khi reboot, cài build tools:
wsl -d Ubuntu -- sudo apt-get update
wsl -d Ubuntu -- sudo apt-get install -y build-essential
```

Build engine:

```bash
cd path/to/Kaggle-ConnectX-Minimax/Agents
python build_engine.py --use-wsl --force
```

Hoặc chạy trực tiếp trong WSL:

```bash
cd /mnt/c/path/to/Agents
python build_engine.py --force
```

### Cách 2: Build trên máy Linux/Mac

Nếu bạn có Linux hoặc Mac:

```bash
cd Agents
python build_engine.py --force
```

### Cách 3: GitHub Actions (Tự động)

Workflow tại `.github/workflows/build-engine.yml` sẽ tự build trên Linux mỗi khi bạn push code.

1. Commit các thay đổi:
```bash
git add -A
git commit -m "Fix: Remove .so from gitignore, add build scripts"
git push
```

2. GitHub Actions sẽ chạy tự động, build `.so` trên Linux, rồi commit lại.

3. Pull về máy:
```bash
git pull
```

## Kiểm tra

Sau khi build, kiểm tra format:

```bash
# On Linux/WSL:
file Agents/_engine.so
```

Output phải như thế này:
```
Agents/_engine.so: ELF 64-bit LSB shared object, x86-64, version 1 (SYSV), dynamically linked, ...
```

Hoặc dùng Python:
```python
from pathlib import Path
so_file = Path("Agents/_engine.so")
magic = so_file.read_bytes()[:4]
print("ELF compatible" if magic == b'\x7fELF' else f"Unknown format: {magic.hex()}")
```

## Troubleshooting

### WSL không tìm g++
```bash
wsl -d Ubuntu -- sudo apt-get install -y build-essential
```

### Lỗi "bash: g++: command not found"
Build tools chưa cài trong WSL. Chạy:
```bash
wsl -d Ubuntu -- sudo apt-get update && sudo apt-get install -y build-essential
```

### File quá lớn
File `.so` có thể từ 2-5 MB, đó là bình thường.

## Sau khi build

Commit file mới vào repo:
```bash
git add Agents/_engine.so
git commit -m "Build: Update _engine.so for Linux"
git push
```

Sau đó submit lên Kaggle. Lần này sẽ không bị lỗi ELF header.
