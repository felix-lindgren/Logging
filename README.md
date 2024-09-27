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
Added to each file since a singleton is used to store data between files
```
from EzLogger import Timer
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
```
```
-------------------------------------------------------------------------------------------------------------
Function                                Runs    Total(ms)   Median(ms)      Avg(ms)      Min(ms)      Max(ms)
-------------------------------------------------------------------------------------------------------------
Function B                                 5       1063.1        212.5        212.6        212.0        213.2
└─Function A                               5        521.1        104.3        104.2        103.7        104.8

Function 0                                 1        100.8        100.8        100.8        100.8        100.8
└─Function 1                               1        100.8        100.8        100.8        100.8        100.8
```