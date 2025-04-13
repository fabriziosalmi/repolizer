"""
Host Monitor Tool

Real-time monitoring of host system statistics to identify performance issues
and resource constraints during repolizer operation.
"""

import os
import sys
import time
import signal
import psutil
import argparse
import curses
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

# Color definitions for the terminal UI
COLOR_NORMAL = 1
COLOR_WARNING = 2
COLOR_CRITICAL = 3
COLOR_HEADER = 4
COLOR_HIGHLIGHT = 5


class HostMonitor:
    """Monitors host system statistics and displays them in real-time"""
    
    def __init__(self, update_interval: float = 1.0, process_filter: Optional[str] = None):
        """
        Initialize the host monitor
        
        Args:
            update_interval: Time between updates in seconds
            process_filter: Filter to only show processes matching this string
        """
        self.update_interval = update_interval
        self.process_filter = process_filter
        self.running = True
        self.screen = None
        
        # Thresholds for highlighting issues
        self.thresholds = {
            'cpu_percent': {'warning': 70, 'critical': 90},
            'memory_percent': {'warning': 75, 'critical': 90},
            'disk_percent': {'warning': 80, 'critical': 90},
            'open_files': {'warning': 800, 'critical': 1500},
            'io_wait': {'warning': 10, 'critical': 25}
        }
        
        # History for tracking values over time
        self.history = {
            'cpu': [],
            'memory': [],
            'disk_io': [],
            'network': []
        }
        
        # Maximum history points to keep
        self.max_history = 60  # 1 minute at 1 second intervals
        
    def format_bytes(self, bytes_value: int) -> str:
        """Format bytes to human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024:
                return f"{bytes_value:.2f} {unit}"
            bytes_value /= 1024
        return f"{bytes_value:.2f} PB"
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Gather current system statistics"""
        stats = {
            'timestamp': datetime.now(),
            'cpu': {
                'percent': psutil.cpu_percent(interval=0),
                'per_cpu': psutil.cpu_percent(interval=0, percpu=True),
                'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0),
                'ctx_switches': psutil.cpu_stats().ctx_switches,
                'interrupts': psutil.cpu_stats().interrupts,
                'io_wait': None,  # Will be populated on Linux
            },
            'memory': {
                'total': psutil.virtual_memory().total,
                'available': psutil.virtual_memory().available,
                'used': psutil.virtual_memory().used,
                'percent': psutil.virtual_memory().percent,
                'swap_total': psutil.swap_memory().total,
                'swap_used': psutil.swap_memory().used,
                'swap_percent': psutil.swap_memory().percent
            },
            'disk': {
                'io_counters': psutil.disk_io_counters() if hasattr(psutil, 'disk_io_counters') else None,
                'usage': {}
            },
            'network': {
                'io_counters': psutil.net_io_counters(),
                'connections': 0  # Initialize to 0, will be set safely below
            },
            'open_files': {
                'count': 0,
                'processes': {}
            }
        }
        
        # Safely get network connections count
        try:
            stats['network']['connections'] = len(psutil.net_connections())
        except (psutil.AccessDenied, PermissionError):
            # On macOS, this often requires admin privileges
            stats['network']['connections'] = -1  # Indicate permission issue
        except Exception as e:
            # Handle any other exceptions
            stats['network']['connections'] = -1
        
        # Get disk usage for each mount point
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                stats['disk']['usage'][partition.mountpoint] = {
                    'total': usage.total,
                    'used': usage.used,
                    'free': usage.free,
                    'percent': usage.percent
                }
            except (PermissionError, OSError):
                pass
        
        # Get open files count and per-process breakdown
        process_open_files = {}
        total_open_files = 0
        
        for proc in psutil.process_iter(['pid', 'name', 'username', 'open_files']):
            try:
                if self.process_filter and self.process_filter not in proc.info['name'].lower():
                    continue
                    
                proc_files = proc.open_files()
                if proc_files:
                    count = len(proc_files)
                    total_open_files += count
                    process_open_files[proc.info['pid']] = {
                        'name': proc.info['name'],
                        'count': count
                    }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        # Sort processes by open file count and keep top 10
        sorted_processes = sorted(
            process_open_files.items(), 
            key=lambda x: x[1]['count'], 
            reverse=True
        )[:10]
        
        stats['open_files']['count'] = total_open_files
        stats['open_files']['processes'] = {
            pid: info for pid, info in sorted_processes
        }
        
        # Get IO wait time (Linux only)
        try:
            io_wait = psutil.cpu_times_percent().iowait
            stats['cpu']['io_wait'] = io_wait
        except AttributeError:
            stats['cpu']['io_wait'] = 0
        
        return stats
    
    def update_history(self, stats: Dict[str, Any]) -> None:
        """Update metrics history"""
        self.history['cpu'].append(stats['cpu']['percent'])
        self.history['memory'].append(stats['memory']['percent'])
        
        # Track disk IO if available
        if stats['disk']['io_counters']:
            self.history['disk_io'].append(
                stats['disk']['io_counters'].read_bytes + 
                stats['disk']['io_counters'].write_bytes
            )
        
        # Track network IO
        self.history['network'].append(
            stats['network']['io_counters'].bytes_sent +
            stats['network']['io_counters'].bytes_recv
        )
        
        # Trim history if needed
        for key in self.history:
            if len(self.history[key]) > self.max_history:
                self.history[key] = self.history[key][-self.max_history:]
    
    def display_stats(self, stats: Dict[str, Any]) -> None:
        """Display system statistics using curses"""
        if not self.screen:
            return
            
        self.screen.clear()
        height, width = self.screen.getmaxyx()
        
        # Get current timestamp
        timestamp = stats['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
        
        # Display header
        self.screen.attron(curses.color_pair(COLOR_HEADER))
        header = f" Host Monitor - {timestamp} "
        self.screen.addstr(0, (width - len(header)) // 2, header)
        self.screen.attroff(curses.color_pair(COLOR_HEADER))
        
        # Display CPU information
        cpu_percent = stats['cpu']['percent']
        cpu_color = self.get_color_for_value(cpu_percent, 'cpu_percent')
        
        self.screen.addstr(2, 2, "CPU Usage:")
        self.screen.attron(curses.color_pair(cpu_color))
        self.screen.addstr(2, 13, f"{cpu_percent:.1f}%")
        self.screen.attroff(curses.color_pair(cpu_color))
        
        # CPU load
        load_1, load_5, load_15 = stats['cpu']['load_avg']
        self.screen.addstr(2, 25, f"Load: {load_1:.2f}, {load_5:.2f}, {load_15:.2f}")
        
        # IO Wait
        if stats['cpu']['io_wait'] is not None:
            io_wait = stats['cpu']['io_wait']
            io_color = self.get_color_for_value(io_wait, 'io_wait')
            self.screen.addstr(2, 52, "IO Wait:")
            self.screen.attron(curses.color_pair(io_color))
            self.screen.addstr(2, 61, f"{io_wait:.1f}%")
            self.screen.attroff(curses.color_pair(io_color))
        
        # Memory information
        mem_percent = stats['memory']['percent']
        mem_color = self.get_color_for_value(mem_percent, 'memory_percent')
        
        mem_used = self.format_bytes(stats['memory']['used'])
        mem_total = self.format_bytes(stats['memory']['total'])
        
        self.screen.addstr(3, 2, "Memory Usage:")
        self.screen.attron(curses.color_pair(mem_color))
        self.screen.addstr(3, 16, f"{mem_percent:.1f}%")
        self.screen.attroff(curses.color_pair(mem_color))
        self.screen.addstr(3, 23, f"({mem_used} / {mem_total})")
        
        # Swap information
        swap_percent = stats['memory']['swap_percent']
        swap_used = self.format_bytes(stats['memory']['swap_used'])
        swap_total = self.format_bytes(stats['memory']['swap_total'])
        
        self.screen.addstr(4, 2, "Swap Usage:")
        swap_color = self.get_color_for_value(swap_percent, 'memory_percent')
        self.screen.attron(curses.color_pair(swap_color))
        self.screen.addstr(4, 14, f"{swap_percent:.1f}%")
        self.screen.attroff(curses.color_pair(swap_color))
        self.screen.addstr(4, 23, f"({swap_used} / {swap_total})")
        
        # Disk information - show top 3 partitions by usage
        self.screen.addstr(6, 2, "Disk Usage:")
        
        row = 7
        sorted_mounts = sorted(
            stats['disk']['usage'].items(),
            key=lambda x: x[1]['percent'],
            reverse=True
        )[:3]
        
        for mountpoint, usage in sorted_mounts:
            if row >= height - 1:
                break
                
            disk_percent = usage['percent']
            disk_color = self.get_color_for_value(disk_percent, 'disk_percent')
            disk_used = self.format_bytes(usage['used'])
            disk_total = self.format_bytes(usage['total'])
            
            mount_display = mountpoint
            if len(mount_display) > 20:
                mount_display = "..." + mount_display[-17:]
                
            self.screen.addstr(row, 4, f"{mount_display}:")
            self.screen.attron(curses.color_pair(disk_color))
            self.screen.addstr(row, 26, f"{disk_percent:.1f}%")
            self.screen.attroff(curses.color_pair(disk_color))
            self.screen.addstr(row, 33, f"({disk_used} / {disk_total})")
            row += 1
        
        # Open files information
        open_files_count = stats['open_files']['count']
        open_files_color = self.get_color_for_value(open_files_count, 'open_files')
        
        self.screen.addstr(row + 1, 2, "Open Files:")
        self.screen.attron(curses.color_pair(open_files_color))
        self.screen.addstr(row + 1, 14, f"{open_files_count}")
        self.screen.attroff(curses.color_pair(open_files_color))
        
        # Top processes by open files
        self.screen.addstr(row + 2, 2, "Top Processes by Open Files:")
        
        proc_row = row + 3
        for pid, info in stats['open_files']['processes'].items():
            if proc_row >= height - 1:
                break
                
            name = info['name']
            count = info['count']
            if len(name) > 20:
                name = name[:17] + "..."
                
            self.screen.addstr(proc_row, 4, f"{name} (PID {pid}): {count} files")
            proc_row += 1
        
        # Network information
        net_io = stats['network']['io_counters']
        recv = self.format_bytes(net_io.bytes_recv)
        sent = self.format_bytes(net_io.bytes_sent)
        connections = stats['network']['connections']
        
        net_row = 6
        self.screen.addstr(net_row, width // 2, f"Network - Recv: {recv}, Sent: {sent}")
        self.screen.addstr(net_row + 1, width // 2, f"Network Connections: {connections}")
        
        # System uptime
        uptime_seconds = int(time.time() - psutil.boot_time())
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        self.screen.addstr(height - 1, 2, f"System Uptime: {uptime_str}")
        
        # Instructions at the bottom
        help_text = "Press 'q' to quit, 'r' to reset stats"
        self.screen.addstr(height - 1, width - len(help_text) - 2, help_text)
        
        self.screen.refresh()
    
    def get_color_for_value(self, value: float, metric: str) -> int:
        """Get the color based on threshold values"""
        if metric in self.thresholds:
            if value >= self.thresholds[metric]['critical']:
                return COLOR_CRITICAL
            elif value >= self.thresholds[metric]['warning']:
                return COLOR_WARNING
        return COLOR_NORMAL
    
    def init_curses(self) -> None:
        """Initialize the curses interface"""
        self.screen = curses.initscr()
        curses.start_color()
        curses.use_default_colors()
        curses.curs_set(0)  # Hide cursor
        self.screen.keypad(True)
        self.screen.timeout(100)  # Set getch timeout to 100ms
        
        # Initialize color pairs
        curses.init_pair(COLOR_NORMAL, curses.COLOR_WHITE, -1)
        curses.init_pair(COLOR_WARNING, curses.COLOR_YELLOW, -1)
        curses.init_pair(COLOR_CRITICAL, curses.COLOR_RED, -1)
        curses.init_pair(COLOR_HEADER, curses.COLOR_BLACK, curses.COLOR_GREEN)
        curses.init_pair(COLOR_HIGHLIGHT, curses.COLOR_CYAN, -1)
    
    def cleanup_curses(self) -> None:
        """Clean up the curses interface"""
        if self.screen:
            self.screen.keypad(False)
            curses.endwin()
    
    def handle_signal(self, sig, frame) -> None:
        """Handle signals gracefully"""
        self.running = False
    
    def run(self) -> None:
        """Run the monitoring loop"""
        try:
            # Set up signal handlers
            signal.signal(signal.SIGINT, self.handle_signal)
            signal.signal(signal.SIGTERM, self.handle_signal)
            
            # Initialize curses
            self.init_curses()
            
            last_stats = None
            last_io_read = 0
            last_io_write = 0
            
            while self.running:
                # Get current stats
                stats = self.get_system_stats()
                
                # Calculate IO rates if we have previous stats
                if last_stats and stats['disk']['io_counters'] and last_stats['disk']['io_counters']:
                    current_io = stats['disk']['io_counters']
                    last_io = last_stats['disk']['io_counters']
                    
                    read_rate = (current_io.read_bytes - last_io.read_bytes) / self.update_interval
                    write_rate = (current_io.write_bytes - last_io.write_bytes) / self.update_interval
                    
                    stats['disk']['read_rate'] = read_rate
                    stats['disk']['write_rate'] = write_rate
                
                # Update history
                self.update_history(stats)
                
                # Display stats
                self.display_stats(stats)
                
                # Save for next iteration
                last_stats = stats
                
                # Check for user input
                c = self.screen.getch()
                if c == ord('q'):
                    self.running = False
                elif c == ord('r'):
                    # Reset history
                    for key in self.history:
                        self.history[key] = []
                
                # Wait for the next update
                time.sleep(self.update_interval)
                
        except Exception as e:
            self.cleanup_curses()
            print(f"Error: {e}")
        finally:
            self.cleanup_curses()


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Monitor host system statistics")
    parser.add_argument(
        "-i", "--interval",
        type=float,
        default=1.0,
        help="Update interval in seconds (default: 1.0)"
    )
    parser.add_argument(
        "-p", "--process",
        type=str,
        help="Filter to show only processes matching this string"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode (no UI), outputting to stdout or a file"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file path for headless mode. If not specified, prints to stdout"
    )
    parser.add_argument(
        "-c", "--count",
        type=int,
        default=0,
        help="Number of stats to collect before exiting (headless mode only, 0=infinite)"
    )
    
    args = parser.parse_args()
    
    # Check for psutil
    if not psutil:
        print("Error: psutil module is required. Install with 'pip install psutil'")
        sys.exit(1)
    
    if args.headless:
        # Run in headless mode
        run_headless(
            interval=args.interval,
            process_filter=args.process,
            output_file=args.output,
            count=args.count
        )
    else:
        # Run with UI
        monitor = HostMonitor(
            update_interval=args.interval,
            process_filter=args.process
        )
        monitor.run()


def run_headless(interval: float, process_filter: Optional[str] = None, 
                output_file: Optional[str] = None, count: int = 0) -> None:
    """
    Run the monitor in headless mode
    
    Args:
        interval: Update interval in seconds
        process_filter: Filter to show only processes matching this string
        output_file: Path to output file (if None, prints to stdout)
        count: Number of stats to collect before exiting (0 = infinite)
    """
    import json
    from datetime import datetime
    
    # Create a monitor instance but don't use the UI
    monitor = HostMonitor(update_interval=interval, process_filter=process_filter)
    
    # Open output file if specified
    output_fd = None
    if output_file:
        try:
            output_fd = open(output_file, 'w')
            # Write opening bracket for JSON array
            output_fd.write('[\n')
        except Exception as e:
            print(f"Error opening output file: {e}")
            sys.exit(1)
    
    try:
        # Set up signal handlers
        def signal_handler(sig, frame):
            if output_fd:
                # Write closing bracket for JSON array
                output_fd.write('\n]')
                output_fd.close()
            sys.exit(0)
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        collected = 0
        comma_needed = False
        
        while count == 0 or collected < count:
            # Get stats
            stats = monitor.get_system_stats()
            
            # Convert timestamp to ISO format for JSON serialization
            stats['timestamp'] = stats['timestamp'].isoformat()
            
            # Format CPU per-core percentages
            stats['cpu']['per_cpu'] = [round(x, 1) for x in stats['cpu']['per_cpu']]
            
            # Convert to serializable format - handle macOS compatibility
            try:
                if 'open_files' in stats and 'processes' in stats['open_files']:
                    serializable_processes = {}
                    for pid, info in stats['open_files']['processes'].items():
                        # Make sure pid is a string for JSON serialization
                        serializable_processes[str(pid)] = {
                            'name': info['name'],
                            'count': info['count']
                        }
                    stats['open_files']['processes'] = serializable_processes
                
                # Make sure all objects are serializable
                for key in list(stats.keys()):
                    if isinstance(stats[key], dict):
                        for subkey in list(stats[key].keys()):
                            if not isinstance(stats[key][subkey], (str, int, float, list, dict, bool, type(None))):
                                stats[key][subkey] = str(stats[key][subkey])
            
                # Serialize
                json_data = json.dumps(stats, indent=2)
                
                if output_fd:
                    # Write to file with proper JSON array formatting
                    if comma_needed:
                        output_fd.write(',\n')
                    output_fd.write(json_data)
                    comma_needed = True
                else:
                    # Print to stdout with timestamp
                    print(f"--- {stats['timestamp']} ---")
                    print(json_data)
                    print("\n")
                
                collected += 1
            except Exception as e:
                print(f"Error serializing stats: {str(e)}")
                
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print("Monitoring stopped by user")
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        if output_fd:
            # Write closing bracket for JSON array
            try:
                output_fd.write('\n]')
                output_fd.close()
            except:
                pass


if __name__ == "__main__":
    main()
