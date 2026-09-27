## EzLogger
Simple logging script for file+console with pip install


```
pip install git+https://github.com/felix-lindgren/Logging
```


## How to use
### Logging
```
from EzLogger import setup_logger
import logging
logger = setup_logger("Annotation", level=logging.INFO)
```

### Timer
Import the shared `ezTimer` in any file, all timings end up in the same report.
```
from EzLogger import ezTimer

with ezTimer("Function 0"):
    with ezTimer("Function 1"):
        time.sleep(0.1)

def worker_function():
    with ezTimer("Function A"):
        time.sleep(0.1)

@ezTimer("Function B")  # or just @ezTimer to use the function name
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
```
```
───────────────────────────────────────────────────────
Function      Runs   Total     P1  Median    P99    Avg
───────────────────────────────────────────────────────
Function B       5  1000.6  200.1   200.1  200.1  200.1
└─Function A     5   500.3  100.1   100.1  100.1  100.1

Function 0       1   100.1  100.1   100.1  100.1  100.1
└─Function 1     1   100.1  100.1   100.1  100.1  100.1
───────────────────────────────────────────────────────
times in ms
```

Columns can be changed once, e.g. at startup, with `Timer(categories=["runs", "total", "self", "median", "max"])` (`Timer()` always returns the shared `ezTimer`).

Available categories: `runs`, `total`, `self` (total minus time in child sections), `min`, `p1`, `median`, `p99`, `max`, `avg`.

`print_metrics` / `format_metrics` (returns the table as a string, e.g. for logging) accept:
- `categories`: override the columns for this report
- `sort_by`: category to sort siblings by (default `"total"`), or `None` for execution order
- `width`: max width, defaults to the terminal width. Long names are truncated and low-priority columns hidden to fit
- `color`: defaults to on for terminals unless `NO_COLOR` is set

`ezTimer(name, enable=False)` makes a section transparent (children attach to its parent), `verbose=True` prints each timing as it happens, and `gpu=True` calls `torch.cuda.synchronize()` around the section.
