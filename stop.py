#!/usr/bin/env python3
"""
Cross-platform shutdown script for NoobBook.
Stops both backend (Flask) and frontend (React+Vite) services.
"""
import os
import sys
import platform
import subprocess
import signal
from pathlib import Path

# Color codes for terminal output
class Colors:
  GREEN = '\033[92m'
  YELLOW = '\033[93m'
  RED = '\033[91m'
  RESET = '\033[0m'
  BOLD = '\033[1m'

def print_status(message, color=Colors.GREEN):
  """Print colored status message."""
  print(f"{color}{message}{Colors.RESET}")

def read_pids():
  """Read process IDs from file."""
  pid_file = Path(__file__).parent / ".noobbook_pids"
  pids = {}

  if pid_file.exists():
    with open(pid_file, 'r') as f:
      for line in f:
        if '=' in line:
          key, value = line.strip().split('=')
          pids[key] = int(value)
    pid_file.unlink()  # Remove PID file after reading

  return pids

def kill_process_by_pid(pid, name):
  """Kill process by PID."""
  try:
    if platform.system() == "Windows":
      subprocess.run(['taskkill', '/F', '/PID', str(pid)],
                    capture_output=True, check=False)
    else:
      os.kill(pid, signal.SIGTERM)

    print_status(f"Stopped {name} (PID: {pid})", Colors.GREEN)
    return True
  except Exception as e:
    print_status(f"Could not stop {name} by PID: {e}", Colors.YELLOW)
    return False

def kill_process_by_port(port, name):
  """Kill process using specific port (fallback method)."""
  system = platform.system()

  try:
    if system == "Windows":
      # Find PID using port
      result = subprocess.run(
        ['netstat', '-ano'],
        capture_output=True,
        text=True,
        check=False
      )

      for line in result.stdout.split('\n'):
        if f':{port}' in line and 'LISTENING' in line:
          parts = line.split()
          pid = parts[-1]
          subprocess.run(['taskkill', '/F', '/PID', pid],
                        capture_output=True, check=False)
          print_status(f"Stopped {name} on port {port} (PID: {pid})", Colors.GREEN)
          return True

    elif system == "Darwin":  # macOS
      result = subprocess.run(
        ['lsof', '-ti', f':{port}'],
        capture_output=True,
        text=True,
        check=False
      )

      pids = result.stdout.strip().split('\n')
      for pid in pids:
        if pid:
          subprocess.run(['kill', '-9', pid], check=False)
          print_status(f"Stopped {name} on port {port} (PID: {pid})", Colors.GREEN)
      return bool(pids and pids[0])

    else:  # Linux
      result = subprocess.run(
        ['fuser', '-k', f'{port}/tcp'],
        capture_output=True,
        check=False
      )

      if result.returncode == 0:
        print_status(f"Stopped {name} on port {port}", Colors.GREEN)
        return True

    return False

  except Exception as e:
    print_status(f"Could not stop {name} by port: {e}", Colors.YELLOW)
    return False

def main():
  """Main execution function."""
  print_status(f"\n{'='*60}", Colors.BOLD)
  print_status("NoobBook - Stopping Services", Colors.BOLD)
  print_status(f"{'='*60}\n", Colors.BOLD)

  stopped_count = 0

  # Try to read PIDs from file first
  pids = read_pids()

  # Stop backend
  if 'backend' in pids:
    if kill_process_by_pid(pids['backend'], 'Backend'):
      stopped_count += 1
    else:
      # Fallback to port-based killing
      if kill_process_by_port(5001, 'Backend'):
        stopped_count += 1
  else:
    # No PID file, try port-based killing
    if kill_process_by_port(5001, 'Backend'):
      stopped_count += 1
    else:
      print_status("Backend is not running (port 5001 free)", Colors.YELLOW)

  # Stop frontend
  if 'frontend' in pids:
    if kill_process_by_pid(pids['frontend'], 'Frontend'):
      stopped_count += 1
    else:
      # Fallback to port-based killing
      if kill_process_by_port(5173, 'Frontend'):
        stopped_count += 1
  else:
    # No PID file, try port-based killing
    if kill_process_by_port(5173, 'Frontend'):
      stopped_count += 1
    else:
      print_status("Frontend is not running (port 5173 free)", Colors.YELLOW)

  print_status(f"\n{'='*60}", Colors.BOLD)

  if stopped_count == 0:
    print_status("No services were running", Colors.YELLOW)
  elif stopped_count == 1:
    print_status("1 service stopped successfully", Colors.GREEN)
  else:
    print_status(f"{stopped_count} services stopped successfully", Colors.GREEN)

  print_status(f"{'='*60}\n", Colors.BOLD)

if __name__ == "__main__":
  main()
