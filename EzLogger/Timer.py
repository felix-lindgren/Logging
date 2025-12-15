import time
import shutil

from contextlib import contextmanager
from collections import defaultdict

import statistics
import threading
from threading import local

try:
    import torch
except ImportError:
    pass

class Timer:
    _instance = None

    def __new__(cls, categories=None):
        if cls._instance is None:
            cls._instance = super(Timer, cls).__new__(cls)
            cls._instance.thread_local = local()
            cls._instance.lock = threading.Lock()
            cls._instance.metrics = defaultdict(lambda: {'timings': [], 'children': defaultdict(dict)})
            # Default categories: current ones minus min and max
            cls._instance.categories = categories if categories is not None else ['runs', 'total', 'p1', 'median', 'p99', 'avg']

        return cls._instance

    def __init__(self, categories=None):
        self.ensure_initialized()

    def ensure_initialized(self):
        if not hasattr(self.thread_local, 'initialized'):
            self.thread_local.current_path = []
            self.thread_local.initialized = True

    def reset(self):
        with self.lock:
            self.metrics.clear()

    @contextmanager
    def __call__(self, text, enable=True, verbose=False, gpu=False):
        self.ensure_initialized()  # Ensure initialization before each use
        self.thread_local.current_path.append(text)

        if not enable:
            yield
        else:
            if gpu:
                torch.cuda.synchronize()
            start = time.perf_counter()
            yield
            if gpu:
                torch.cuda.synchronize()
            end = time.perf_counter()
            if verbose:
                print(" -> ".join(self.thread_local.current_path), f"{end - start:.4f} s")
            
            self.update_metrics(end - start)

        self.thread_local.current_path.pop()

    def update_metrics(self, elapsed):
        with self.lock:
            current = self.metrics
            for i, part in enumerate(self.thread_local.current_path):
                if part not in current:
                    current[part] = {'timings': [], 'children': defaultdict(dict)}
                if i == len(self.thread_local.current_path) - 1:  # Only add timing to the last function in the stack
                    current[part]['timings'].append(elapsed)
                current = current[part]['children']

    def print_metrics(self, node=None, depth=0, path=[]):
        n_break_lines = 100
        if node is None:
            if not self.metrics:
                print("No metrics to display.")
                return
            node = self.metrics
            self.max_depth = max(len(key.split(' -> ')) for key in self.flatten_dict(self.metrics))

            # Category display names
            category_names = {
                'runs': 'Runs',
                'total': 'Total(ms)',
                'min': 'Min(ms)',
                'p1': 'P1(ms)',
                'median': 'Median(ms)',
                'p99': 'P99(ms)',
                'max': 'Max(ms)',
                'avg': 'Avg(ms)'
            }

            # Category widths
            category_widths = {
                'runs': 8,
                'total': 12,
                'min': 12,
                'p1': 12,
                'median': 12,
                'p99': 12,
                'max': 12,
                'avg': 12
            }

            # Get terminal width and calculate available space for function names
            terminal_width = shutil.get_terminal_size().columns - 3  # padding
            print(terminal_width)

            # Calculate timing columns width based on selected categories
            timing_columns_width = sum(category_widths[cat] for cat in self.categories) + len(self.categories)
            # Reserve at least 20 chars for function names, but use more if terminal is wide
            self.max_function_width = max(20, terminal_width - timing_columns_width)

            # Build header dynamically
            header = f"{'Function':<{self.max_function_width}}"
            for cat in self.categories:
                width = category_widths[cat]
                header += f" {category_names[cat]:>{width}}"

            print("\033[1m" + "-" * len(header) + "\033[0m")  # Bold line for separator
            print(header)
            print("-" * len(header))

        for idx, (text, data) in enumerate(sorted(node.items(), key=lambda item: statistics.median(item[1]['timings']) if item[1]['timings'] else 0, reverse=True)):

            current_path = path + [text]
            timings = data['timings']
            count = len(timings)

            if count > 0:
                total_time = sum(timings) * 1000
                average_time = total_time / count
                median_time = statistics.median(timings) * 1000
                min_time = min(timings) * 1000
                max_time = max(timings) * 1000

                # Calculate percentiles (1st and 99th)
                if count >= 2:
                    try:
                        percentiles = statistics.quantiles(timings, n=100, method='inclusive')
                        p1_time = percentiles[0] * 1000  # 1st percentile
                        p99_time = percentiles[98] * 1000  # 99th percentile
                    except statistics.StatisticsError:
                        p1_time = min_time
                        p99_time = max_time
                else:
                    p1_time = min_time
                    p99_time = max_time

                # Calculate self time (excluding children)
                child_time = sum(child['timings'][0] for child in data['children'].values() if child['timings']) * 1000
                self_time = total_time - child_time

                indent = ""
                if depth > 0:
                    if idx == len(node) - 1 and depth == 1:
                        indent += "└─"
                    else:
                        indent += "├─"
                    indent += "──" * (depth - 1)

                path_str = current_path[-1]#"->".join(current_path)
                full_name = indent + path_str

                # Truncate function name if it exceeds available width
                if len(full_name) > self.max_function_width:
                    # Leave room for "..." at the end
                    full_name = full_name[:self.max_function_width - 3] + "..."

                # Build data values dict
                data_values = {
                    'runs': count,
                    'total': total_time,
                    'min': min_time,
                    'p1': p1_time,
                    'median': median_time,
                    'p99': p99_time,
                    'max': max_time,
                    'avg': average_time
                }

                # Color codes for each category
                category_colors = {
                    'runs': '\033[93m',      # Yellow
                    'total': '\033[92m',     # Green
                    'min': '\033[95m',       # Magenta
                    'p1': '\033[35m',        # Purple
                    'median': '\033[96m',    # Cyan
                    'p99': '\033[35m',       # Purple
                    'max': '\033[91m',       # Red
                    'avg': '\033[94m'        # Blue
                }

                # Category widths
                category_widths = {
                    'runs': 8,
                    'total': 12,
                    'min': 12,
                    'p1': 12,
                    'median': 12,
                    'p99': 12,
                    'max': 12,
                    'avg': 12
                }

                # Build output string dynamically
                output = f"{full_name:<{self.max_function_width}}"
                for cat in self.categories:
                    color = category_colors[cat]
                    width = category_widths[cat]
                    value = data_values[cat]

                    # Format based on category type
                    if cat == 'runs':
                        output += f" {color}{value:>{width}d}\033[0m"
                    else:
                        output += f" {color}{value:>{width}.1f}\033[0m"

                print(output)
            if data['children']:
                self.print_metrics(data['children'], depth + 1, current_path)

            if depth == 0:
                #print("\033[1m" + "-" * n_break_lines + "\033[0m")
                print()  # Add an extra newline between root trees

    def flatten_dict(self, d, parent_key='', sep=' -> '):
        items = []
        for k, v in d.items():
            new_key = parent_key + sep + k if parent_key else k
            if 'children' in v and v['children']:
                items.extend(self.flatten_dict(v['children'], new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)

if __name__ == "__main__":
    timer = Timer()

    with timer("Function 0"):
        with timer(text="Function 1"):
            time.sleep(0.1)

    def worker_function():
        # Your code here
        with timer("Function A"):
            time.sleep(0.1)

    @timer(text="Function B")
    def thread_function():
        worker_function()
        time.sleep(0.1)  # Simulate some work

    threads = []
    for _ in range(5):  # Create 5 threads
        thread = threading.Thread(target=thread_function)
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    timer.print_metrics()