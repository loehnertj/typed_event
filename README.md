# typed-event

Strongly-typed events for Python via an `@event` decorator.

`typed-event` lets you define an event from a function/method prototype, then
subscribe listeners with `+=` and unsubscribe with `-=`.

## Installation

```bash
pip install typed-event
```

## Quick start

### Module-level event

```python
from typed_event import event


@event
def counter_changed(new_value: int):
	"""Fired whenever the counter changes."""


def print_value(new_value: int):
	print("new value:", new_value)


counter_changed += print_value
counter_changed(42)
counter_changed -= print_value
```

### Class events

```python
from typed_event import event


class Counter:
	@event
	def changed(value: int):
		"""Fired when value changes."""


c1 = Counter()
c2 = Counter()

def on_c1(value: int):
	print("c1:", value)

def on_c2(value: int):
	print("c2:", value)

c1.changed += on_c1
c2.changed += on_c2

c1.changed(1)  # only on_c1
c2.changed(2)  # only on_c2
```

Each instance gets its own bound event with its own listener list.

## Behavior and guarantees

- Event signatures are copied from the prototype (name, parameters, annotations, docstring).
- Calling an event validates arguments using normal Python call semantics.
- Listener signatures are not validated at subscription time; a mismatch fails when invoked.
- Type annotations are not runtime-enforced.

## Defining event prototypes

Prototype restrictions:

- No default argument values.
- No `*args` / `**kwargs` in the event prototype.
- Optional strict mode (`strict=True`) requires parameters to be explicitly positional-only (`/`) or keyword-only (`*`).

Example with explicit keyword-only parameters:

```python
from typed_event import event


@event
def changed(*, a: int, b: int):
	pass


changed(a=1, b=2)      # ok
# changed(1, 2)         # TypeError
```

## Cancellation

Raise `CancelEvent` in a listener to stop processing remaining listeners:

```python
from typed_event import event, CancelEvent


@event
def changed(value: int):
	pass


def first(value: int):
	raise CancelEvent()


def second(value: int):
	print("never called")


changed += first
changed += second
changed(1)
```

## Exception handling policy

Set via `@event(exceptions=...)`:

- `"default"`: passes exceptions to `sys.excepthook`.
- `"log"`: logs exceptions via `logging.exception`.
- `"raise"`: re-raises immediately and stops further listeners.
- `"group"`: runs all listeners, then raises `ExceptionGroup` if any failed.

`CancelEvent` is handled separately and is never treated as an error.

## Return values

At most one non-`None` return value is allowed across prototype + listeners.
If multiple handlers return a value, a `RuntimeError` is raised.
