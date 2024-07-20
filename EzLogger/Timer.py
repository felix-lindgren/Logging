import time
from contextlib import contextmanager
import statistics
import inspect
from collections import defaultdict
from threading import local

try:
    import torch
except ImportError:
    pass

class Timer:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Timer, cls).__new__(cls)
            cls._instance.thread_local = local()

            # Put any initialization here.
        return cls._instance
    
    def __init__(self):
        if not hasattr(self.thread_local, 'initialized'):
            self.reset()
            self.thread_local.initialized = True

    def reset(self):
        self.thread_local.metrics = defaultdict(lambda: {'timings': [], 'children': defaultdict(dict)})
        self.thread_local.current_path = []

    @contextmanager
    def __call__(self, text="", enable=True, verbose=False, gpu=False):
        stack = inspect.stack()
        caller = None
        for i in range(len(stack)):
            caller = stack[i].function
            if caller not in ['__call__', '__enter__', 'inner', '<module>']:
                break

        if text == "":
            text = caller

        self.thread_local.current_path.append(text)

        if not enable:
            yield
        else:
            if gpu:
                torch.cuda.synchronize()
            start = time.time()
            yield
            if gpu:
                torch.cuda.synchronize()
            end = time.time()
            if verbose:
                print(" -> ".join(self.thread_local.current_path), f"{end - start:.4f} s")
            
            self.update_metrics(end - start)

        self.thread_local.current_path.pop()

    def update_metrics(self, elapsed):
        current = self.thread_local.metrics
        for i, part in enumerate(self.thread_local.current_path):
            if part not in current:
                current[part] = {'timings': [], 'children': defaultdict(dict)}
            if i == len(self.thread_local.current_path) - 1:  # Only add timing to the last function in the stack
                current[part]['timings'].append(elapsed)
            current = current[part]['children']

    def print_metrics(self, node=None, depth=0, path=[]):
        n_break_lines = 100
        if node is None:
            print("\033[1m" + "-" * n_break_lines + "\033[0m")  # Bold line for separator
            if not self.thread_local.metrics:
                print("No metrics to display.")
                return
            node = self.thread_local.metrics
            self.max_depth = max(len(key.split(' -> ')) for key in self.flatten_dict(self.thread_local.metrics))
            
            # Print header
            print(f"{'Function':<35} {'Runs':>8} {'Total(ms)':>12} {'Self(ms)':>12} {'Avg(ms)':>12} {'Min(ms)':>12} {'Max(ms)':>12}")
            print("-" * n_break_lines)

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
                
                print(f"{indent+path_str:<35} "
                    f"\033[93m{count:>8d}\033[0m "
                    f"\033[92m{total_time:>12.1f}\033[0m "
                    f"\033[96m{self_time:>12.1f}\033[0m "
                    f"\033[94m{average_time:>12.1f}\033[0m "
                    f"\033[95m{min_time:>12.1f}\033[0m "
                    f"\033[91m{max_time:>12.1f}\033[0m")
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

    @timer(text="f1")
    def f1():
        time.sleep(0.25)

    @timer(text="f2")
    def f2():
        time.sleep(0.25)
        f1()

    @timer(text="f3")
    def f3():
        time.sleep(0.25)
        f2()
        f1()

    f1()
    f2()
    f3()

    timer.print_metrics()