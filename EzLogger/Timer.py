import time
from contextlib import contextmanager
import statistics
import inspect

try :
    import torch
except ImportError:
    pass

class Timer:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Timer, cls).__new__(cls)
            # Put any initialization here.
        return cls._instance
    
    def __init__(self):
        self.metrics = {}
        self.text_list = []

    @contextmanager
    def __call__(self, text="", enable=True, verbose=False, gpu=False):
        stack = inspect.stack()
        for i in range(len(stack)):
            caller = stack[i].function
            if caller in ['__call__', '__enter__', 'inner', '<module>']:
                continue
            if text == "":
                text = caller
            else:
                text = caller + " -> " + text
            break

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
                print(text, f"{end - start:.4f} s")
            
            if text != "":
                self.update_metrics(text, end - start)

    def update_metrics(self, text, elapsed):
        if text not in self.metrics:
            self.metrics[text] = []
        self.metrics[text].append(elapsed)

    def get_average_time(self, text):
        if text in self.metrics:
            average_time = self.metrics[text]['total_time'] / self.metrics[text]['count']
            return average_time
        else:
            return 0

    def print_metrics(self):
        print("\033[1m" + "-" * 100 + "\033[0m")  # Bold line for separator
        if not self.metrics:
            print("No metrics to display.")
            return
        
        max_text_width = max(len(text) for text in self.metrics)

        headers = [
            f"{'Task':<{max_text_width}}", "N Runs", "Tot(ms)", "Avg(ms)","Med(ms)","Min(ms)","Max(ms)",
        ]
        header_text = "\t".join(f"\033[4m\033[1m{header}\033[0m" for header in headers)
        print(f"{header_text}")
        
        colors = [
            "\033[97m",  # White for task name
            "\033[93m",  # Bright Yellow for total runs
            "\033[92m",  # Bright Green for total time
            "\033[96m",  # Bright Cyan for average time
            "\033[94m",  # Bright Blue for median time
            "\033[95m",  # Bright Magenta for max time
            "\033[91m"   # Bright Red for min time
        ]

        sorted_metrics = sorted(self.metrics.items(), key=lambda item: statistics.median(item[1]), reverse=True)
        
        for text, data in sorted_metrics:
            timings = data
            count = len(timings)
            total_time = sum(timings) * 1000
            average_time = total_time  / count if count > 0 else 0
            median_time = statistics.median(timings) * 1000 if count > 0 else 0
            min_time = min(timings) * 1000
            max_time = max(timings) * 1000
            
            values = [
                f"{text:<{max_text_width}}",
                f"{count:>4}",
                f"{total_time:.1f}",
                f"{average_time:.1f}",
                f"{median_time:.1f}",
                f"{min_time:.1f}",
                f"{max_time:.1f}",
            ]
            # Apply colors to each column
            colored_values = [colors[i] + value + "\033[0m" for i, value in enumerate(values)]
            print("\t".join(colored_values))
        print("\033[1m" + "-" * 100 + "\033[0m")

if __name__ == "__main__":
    timer = Timer()

    @timer(text="f1")
    def f1():
        time.sleep(0.25)

    f1()

    @timer(text="f2")
    def f2():
        time.sleep(0.25)
        f1()

    f2()

    fn = lambda x: f2()
    fn(1)

    with timer(text="f3"):
        time.sleep(0.25)

    #with timer(text="verylongtextdescriptionasdasd"):
    #    time.sleep(0.25)

    timer.print_metrics()