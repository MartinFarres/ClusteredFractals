#!/usr/bin/env python3
import subprocess
import sys

def main():
    if len(sys.argv) < 2:
        print("[ERROR] Usage: run_and_check.py <program> [args...]", flush=True)
        sys.exit(1)

    program = sys.argv[1]
    args = sys.argv[2:]

    try:
        print("[TASK] Master is running...", flush=True)
        subprocess.run([program] + args, check=True)
        print("[SUCCESS] Program finished with exit code 0", flush=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Program exited with code {e.returncode}", flush=True)
    except FileNotFoundError:
        print(f"[ERROR] Program '{program}' not found", flush=True)
    except Exception as e:
        print(f"[ERROR] Unexpected exception: {str(e)}", flush=True)

if __name__ == "__main__":
    main()
