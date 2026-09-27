import os
import sys
import time
import shutil
import statistics
import threading
from functools import wraps

RESET = '\033[0m'
BOLD = '\033[1m'
DIM = '\033[2m'

# category -> (header, color)
CATEGORIES = {
    'runs':   ('Runs',   '\033[93m'),  # Yellow
    'total':  ('Total',  '\033[92m'),  # Green
    'self':   ('Self',   '\033[32m'),  # Dark green, total minus time spent in children
    'min':    ('Min',    '\033[95m'),  # Magenta
    'p1':     ('P1',     '\033[35m'),  # Purple
    'median': ('Median', '\033[96m'),  # Cyan
    'p99':    ('P99',    '\033[35m'),  # Purple
    'max':    ('Max',    '\033[91m'),  # Red
    'avg':    ('Avg',    '\033[94m'),  # Blue
}
DEFAULT_CATEGORIES = ['runs', 'total', 'p1', 'median', 'p99', 'avg']
# When the table doesn't fit the terminal, columns are hidden in this order
DROP_ORDER = ['min', 'max', 'p1', 'p99', 'self', 'avg', 'runs', 'median', 'total']
MIN_NAME_WIDTH = 16


def _validate_categories(categories):
    unknown = [c for c in categories if c not in CATEGORIES]
    if unknown:
        raise ValueError(f"Unknown timer categories {unknown}, choose from {list(CATEGORIES)}")
    return list(categories)


def _new_node():
    return {'timings': [], 'children': {}}


class _Section:
    """Returned by `ezTimer(...)`, usable both as a context manager and as a decorator."""

    def __init__(self, timer, name, enable, verbose, gpu):
        self.timer = timer
        self.name = name
        self.enable = enable
        self.verbose = verbose
        self.gpu = gpu

    def __enter__(self):
        if self.name is None:
            raise TypeError("ezTimer() needs a name when used as a context manager")
        if self.enable:
            self.timer._start(self.name, self.gpu)
        return self

    def __exit__(self, *exc_info):
        if self.enable:
            self.timer._stop(self.verbose, self.gpu)
        return False

    def __call__(self, func):
        name = self.name or func.__qualname__

        @wraps(func)
        def wrapper(*args, **kwargs):
            with _Section(self.timer, name, self.enable, self.verbose, self.gpu):
                return func(*args, **kwargs)
        return wrapper


class Timer:
    _instance = None

    def __new__(cls, categories=None):
        if cls._instance is None:
            cls._instance = super(Timer, cls).__new__(cls)
            cls._instance.thread_local = threading.local()
            cls._instance.lock = threading.Lock()
            cls._instance.metrics = {}
            cls._instance.categories = list(DEFAULT_CATEGORIES)
        return cls._instance

    def __init__(self, categories=None):
        if categories is not None:
            self.categories = _validate_categories(categories)

    @property
    def _stack(self):
        # Per-thread stack of (name, start_time) for the currently open sections
        if not hasattr(self.thread_local, 'stack'):
            self.thread_local.stack = []
        return self.thread_local.stack

    def reset(self):
        with self.lock:
            self.metrics.clear()

    def __call__(self, text=None, enable=True, verbose=False, gpu=False):
        """Time a section, either as `with ezTimer("name"):` or as a decorator.

        As a decorator the name defaults to the function's qualified name, so
        `@ezTimer`, `@ezTimer()` and `@ezTimer("name")` all work. Disabled sections
        are transparent: nested sections attach to the enclosing parent.
        """
        if callable(text):
            return _Section(self, None, enable, verbose, gpu)(text)
        return _Section(self, text, enable, verbose, gpu)

    def _start(self, name, gpu):
        if gpu:
            import torch
            torch.cuda.synchronize()
        self._stack.append((name, time.perf_counter()))

    def _stop(self, verbose, gpu):
        if gpu:
            import torch
            torch.cuda.synchronize()
        end = time.perf_counter()
        stack = self._stack
        path = [name for name, _ in stack]
        elapsed = end - stack[-1][1]
        if verbose:
            print(" -> ".join(path), f"{elapsed:.4f} s")
        self._record(path, elapsed)
        stack.pop()

    def _record(self, path, elapsed):
        with self.lock:
            children = self.metrics
            for name in path:
                node = children.setdefault(name, _new_node())
                children = node['children']
            node['timings'].append(elapsed)

    # ------------------------------------------------------------------ report

    @staticmethod
    def _stats(node):
        timings = node['timings']
        if not timings:
            return None
        ms = [t * 1000 for t in timings]
        count = len(ms)
        total = sum(ms)
        if count >= 2:
            percentiles = statistics.quantiles(ms, n=100, method='inclusive')
            p1, p99 = percentiles[0], percentiles[98]
        else:
            p1 = p99 = ms[0]
        child_total = sum(sum(child['timings']) for child in node['children'].values()) * 1000
        return {
            'runs': count,
            'total': total,
            'self': total - child_total,
            'min': min(ms),
            'p1': p1,
            'median': statistics.median(ms),
            'p99': p99,
            'max': max(ms),
            'avg': total / count,
        }

    def _collect_rows(self, nodes, sort_by, prefix, rows, is_root):
        items = [(name, node, self._stats(node)) for name, node in nodes.items()]
        if sort_by is not None:
            items.sort(key=lambda item: item[2][sort_by] if item[2] else float('-inf'), reverse=True)

        for idx, (name, node, stats) in enumerate(items):
            if is_root:
                if idx > 0:
                    rows.append(None)  # Blank line between root trees
                branch, child_prefix = '', ''
            else:
                last = idx == len(items) - 1
                branch = prefix + ('└─' if last else '├─')
                child_prefix = prefix + ('  ' if last else '│ ')
            rows.append((branch, name, stats))
            self._collect_rows(node['children'], sort_by, child_prefix, rows, is_root=False)

    def format_metrics(self, categories=None, sort_by='total', width=None, color=False):
        """Render the collected metrics as a table and return it as a string.

        categories: columns to show, defaults to the ones given to Timer().
        sort_by:    category to sort siblings by (descending), or None to keep
                    the order in which sections were first entered.
        width:      max table width, defaults to the terminal width. Names are
                    truncated and low-priority columns hidden to make it fit.
        """
        categories = _validate_categories(categories) if categories is not None else list(self.categories)
        if sort_by is not None and sort_by not in CATEGORIES:
            raise ValueError(f"Unknown sort_by {sort_by!r}, choose from {list(CATEGORIES)} or None")

        rows = []
        with self.lock:
            self._collect_rows(self.metrics, sort_by, '', rows, is_root=True)
        if not rows:
            return "No metrics to display."

        # Format every cell up front so column widths can fit the actual content
        cells = []
        for row in rows:
            if row is None:
                cells.append(None)
                continue
            _, _, stats = row
            values = {}
            for cat in CATEGORIES:
                if stats is None:
                    values[cat] = '-'
                elif cat == 'runs':
                    values[cat] = str(stats[cat])
                else:
                    values[cat] = f"{stats[cat]:.1f}"
            cells.append(values)

        col_widths = {
            cat: max([len(CATEGORIES[cat][0])] + [len(c[cat]) for c in cells if c is not None])
            for cat in CATEGORIES
        }
        name_width = max([len('Function')] + [len(r[0]) + len(r[1]) for r in rows if r is not None])

        # Shrink the table until it fits: tighter gaps, then truncated names, then fewer columns
        available = width if width is not None else shutil.get_terminal_size().columns - 1

        def table_width(cats, name_w, gap):
            return name_w + sum(gap + col_widths[c] for c in cats)

        gap = 2 if table_width(categories, name_width, 2) <= available else 1
        min_name_width = min(name_width, MIN_NAME_WIDTH)
        hidden = []
        while len(categories) > 1 and table_width(categories, min_name_width, gap) > available:
            victim = next(c for c in DROP_ORDER if c in categories)
            categories.remove(victim)
            hidden.append(victim)
        name_width = max(min_name_width, min(name_width, available - table_width(categories, 0, gap)))
        total_width = table_width(categories, name_width, gap)

        def paint(text, code):
            return f"{code}{text}{RESET}" if color and text else text

        def fit_name(branch, name):
            if len(branch) + len(name) <= name_width:
                return branch, name
            room = name_width - len(branch) - 1
            if room >= 1:
                return branch, name[:room] + '…'
            return (branch + name)[:name_width - 1] + '…', ''

        rule = paint('─' * total_width, DIM)
        header = f"{'Function':<{name_width}}" + ''.join(
            ' ' * gap + f"{CATEGORIES[cat][0]:>{col_widths[cat]}}" for cat in categories
        )
        lines = [rule, paint(header, BOLD), rule]

        for row, values in zip(rows, cells):
            if row is None:
                lines.append('')
                continue
            branch, name = fit_name(row[0], row[1])
            padding = ' ' * (name_width - len(branch) - len(name))
            line = paint(branch, DIM) + (paint(name, BOLD) if not row[0] else name) + padding
            for cat in categories:
                line += ' ' * gap + paint(f"{values[cat]:>{col_widths[cat]}}", CATEGORIES[cat][1])
            lines.append(line)

        lines.append(rule)
        footer = "times in ms"
        if hidden:
            footer += f" · hidden to fit width: {', '.join(hidden)}"
        lines.append(paint(footer, DIM))
        return '\n'.join(lines)

    def print_metrics(self, categories=None, sort_by='total', width=None, color=None):
        """Print the metrics table, see `format_metrics` for the arguments.

        color defaults to on when stdout is a terminal and NO_COLOR isn't set.
        """
        if color is None:
            color = sys.stdout.isatty() and 'NO_COLOR' not in os.environ
        print(self.format_metrics(categories, sort_by, width, color))


# Shared instance, use `from EzLogger import ezTimer` in every file
ezTimer = Timer()


if __name__ == "__main__":
    with ezTimer("Function 0"):
        with ezTimer(text="Function 1"):
            time.sleep(0.1)

    def worker_function():
        # Your code here
        with ezTimer("Function A"):
            time.sleep(0.1)

    @ezTimer(text="Function B")
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

    ezTimer.print_metrics()
