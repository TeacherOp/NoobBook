#!/usr/bin/env python3
"""
Cross-platform startup script for NoobBook.
Starts both backend (Flask) and frontend (React+Vite) concurrently.
"""
import os
import sys
import platform
import subprocess
import signal
import time
from pathlib import Path

# Color codes for terminal output (works on most terminals)
class Colors:
  GREEN = '\033[92m'
  BLUE = '\033[94m'
  YELLOW = '\033[93m'
  RED = '\033[91m'
  RESET = '\033[0m'
  BOLD = '\033[1m'

def print_status(message, color=Colors.GREEN):
  """Print colored status message."""
  print(f"{color}{message}{Colors.RESET}")

def get_venv_python():
  """Get the path to Python executable in virtual environment."""
  system = platform.system()
  venv_dir = Path(__file__).parent / "backend" / "venv"

  if system == "Windows":
    return venv_dir / "Scripts" / "python.exe"
  else:  # Linux, macOS
    return venv_dir / "bin" / "python"

def check_venv():
  """Check if virtual environment exists."""
  venv_python = get_venv_python()
  if not venv_python.exists():
    print_status("Virtual environment not found!", Colors.RED)
    print_status("Please create it first:", Colors.YELLOW)
    print("  cd backend")
    print("  python -m venv venv")
    print("  source venv/bin/activate  # macOS/Linux")
    print("  venv\\Scripts\\activate     # Windows")
    print("  pip install -r requirements.txt")
    return False
  return True

def check_node_modules():
  """Check if node_modules exists."""
  node_modules = Path(__file__).parent / "frontend" / "node_modules"
  if not node_modules.exists():
    print_status("node_modules not found!", Colors.RED)
    print_status("Please install dependencies first:", Colors.YELLOW)
    print("  cd frontend")
    print("  npm install")
    return False
  return True

def start_backend():
  """Start Flask backend server."""
  backend_dir = Path(__file__).parent / "backend"
  venv_python = get_venv_python()

  print_status(f"\n{Colors.BOLD}Starting Backend (Flask)...{Colors.RESET}", Colors.BLUE)
  print_status(f"Directory: {backend_dir}", Colors.BLUE)
  print_status(f"URL: http://localhost:5001", Colors.BLUE)

  # Start backend process
  process = subprocess.Popen(
    [str(venv_python), "run.py"],
    cwd=str(backend_dir),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    bufsize=1
  )

  return process

def start_frontend():
  """Start Vite frontend dev server."""
  frontend_dir = Path(__file__).parent / "frontend"

  print_status(f"\n{Colors.BOLD}Starting Frontend (Vite)...{Colors.RESET}", Colors.GREEN)
  print_status(f"Directory: {frontend_dir}", Colors.GREEN)
  print_status(f"URL: http://localhost:5173", Colors.GREEN)

  # Determine npm command based on OS
  npm_cmd = "npm.cmd" if platform.system() == "Windows" else "npm"

  # Start frontend process
  process = subprocess.Popen(
    [npm_cmd, "run", "dev"],
    cwd=str(frontend_dir),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    universal_newlines=True,
    bufsize=1
  )

  return process

def save_pids(backend_pid, frontend_pid):
  """Save process IDs to file for stop script."""
  pid_file = Path(__file__).parent / ".noobbook_pids"
  with open(pid_file, 'w') as f:
    f.write(f"backend={backend_pid}\n")
    f.write(f"frontend={frontend_pid}\n")

def stream_output(process, prefix, color):
  """Stream process output with colored prefix."""
  for line in process.stdout:
    print(f"{color}[{prefix}]{Colors.RESET} {line.rstrip()}")

def main():
  """Main execution function."""
  print_status(f"\n{'='*60}", Colors.BOLD)
  print_status("NoobBook - Starting Services", Colors.BOLD)
  print_status(f"{'='*60}\n", Colors.BOLD)

  # Check prerequisites
  if not check_venv():
    sys.exit(1)

  if not check_node_modules():
    sys.exit(1)

  try:
    # Start both services
    backend_process = start_backend()
    time.sleep(2)  # Give backend time to start
    frontend_process = start_frontend()

    # Save PIDs for stop script
    save_pids(backend_process.pid, frontend_process.pid)

    print_status(f"\n{'='*60}", Colors.BOLD)
    print_status("Services Started Successfully!", Colors.GREEN)
    print_status(f"{'='*60}", Colors.BOLD)
    print_status("\nBackend:  http://localhost:5001", Colors.BLUE)
    print_status("Frontend: http://localhost:5173", Colors.GREEN)
    print_status(f"\n{Colors.YELLOW}Press Ctrl+C to stop all services{Colors.RESET}\n")

    # Stream output from both processes
    import threading

    backend_thread = threading.Thread(
      target=stream_output,
      args=(backend_process, "BACKEND", Colors.BLUE),
      daemon=True
    )
    frontend_thread = threading.Thread(
      target=stream_output,
      args=(frontend_process, "FRONTEND", Colors.GREEN),
      daemon=True
    )

    backend_thread.start()
    frontend_thread.start()

    # Wait for processes to complete or Ctrl+C
    while True:
      if backend_process.poll() is not None:
        print_status("\nBackend process stopped unexpectedly!", Colors.RED)
        frontend_process.terminate()
        break
      if frontend_process.poll() is not None:
        print_status("\nFrontend process stopped unexpectedly!", Colors.RED)
        backend_process.terminate()
        break
      time.sleep(1)

  except KeyboardInterrupt:
    print_status("\n\nShutting down services...", Colors.YELLOW)
    backend_process.terminate()
    frontend_process.terminate()

    # Wait for graceful shutdown
    backend_process.wait(timeout=5)
    frontend_process.wait(timeout=5)

    print_status("Services stopped successfully!", Colors.GREEN)

  except Exception as e:
    print_status(f"\nError: {str(e)}", Colors.RED)
    sys.exit(1)

if __name__ == "__main__":
  main()
