#!/usr/bin/env python3
"""
Simple python script that runs the given program and forwards command line arguments. 
For exit code 0 outputs [SUCCESS]. 
For exit code 1 outputs [ERROR].
"""
import subprocess
import sys

def main():
    if len(sys.argv) < 2:
        print("[ERROR] Usage: run_and_check.py <program> [args...]")
        sys.exit(1)

    program = sys.argv[1]
    args = sys.argv[2:]

    try:
        subprocess.run([program] + args, check=True)
        print("[SUCCESS] Program finished with exit code 0")
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Program exited with code {e.returncode}")
    except FileNotFoundError:
        print(f"[ERROR] Program '{program}' not found")
    except Exception as e:
        print(f"[ERROR] Unexpected exception: {str(e)}")

if __name__ == "__main__":
    main()
