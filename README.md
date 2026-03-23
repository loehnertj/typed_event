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
def counter_changed(new_value: int, /):
	"""Fired whenever the counter changes."""


def print_value(new_value: int):
	print("new value:", new_value)


counter_changed += print_value
counter_changed(42)
counter_changed -= print_value
```

Note that by default, `@event` requires you to make it explicit whether values
are passed positionally or as keyword.

### Class events

```python
from typed_event import event


class Counter:
	def __init__(self):
		self._value = 0

	@event
	def changed(value: int, /):
		"""Fired when value changes."""

	def set_value(self, value: int):
		self._value = value
		self.changed(value)  # fire the event


c1 = Counter()
c2 = Counter()

def on_c1(value: int):
	print("c1:", value)

def on_c2(value: int):
	print("c2:", value)

c1.changed += on_c1
c2.changed += on_c2

c1.set_value(1)  # prints "c1: 1"
c2.set_value(2)  # prints "c2: 2"
```

Each instance gets its own bound event with its own listener list.

## Defining event prototypes

Prototype restrictions:

- No default argument values.
- No `*args` / `**kwargs` in the event prototype.
- Strict mode (enabled by default) requires parameters to be explicitly positional-only (`/`) or keyword-only (`*`). Opt-out by using `@event(strict=False)`.

Example with explicit keyword-only parameters:

```python
from typed_event import event


@event
def changed(*, a: int, b: int):
	pass


changed(a=1, b=2)      # ok
# changed(1, 2)         # TypeError
```

**Notes:**

- Listener signatures are not validated at subscription time; a mismatch only fails when invoked.
- Type annotations are **not** runtime-enforced — the name refers to static typing support, not runtime checks.

## Cancellation

Raise `CancelEvent` in a listener to stop processing remaining listeners:

```python
from typed_event import event, CancelEvent


@event
def changed(value: int, /):
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

- `"default"` (default): passes exceptions to `sys.excepthook`.
- `"log"`: logs exceptions via `logging.exception`.
- `"raise"`: re-raises immediately and stops further listeners. I.e. no "handling" at all.
- `"group"`: runs all listeners, then raises `ExceptionGroup` if any failed.

`CancelEvent` is handled separately and is never treated as an error.

## Return values

At most one non-`None` return value is allowed across prototype + listeners.
If multiple handlers return a value, a `RuntimeError` is raised.

## Changing event settings on module / project level

To define many events with changed settings (e.g. different default for `exception`), make an alias decorator like so:

```
from typed_event import event
my_event = event(strict=False, exceptions="log")

@my_event
def event1(): ...

@my_event
def event2(): ...
```

To apply project-wide, define the alias in a helper module and import from there.

## Changelog

### Version 1.0 (23.03.2026)

First release of the library as standalone project. Previously it was part of [ASCII
Designer](https://github.com/loehnertj/ascii_designer).

Minor changes happened (strict mode as default, using sys.excepthook instead of
print). Besides that, comprehensive testing and documentation was added.

## License

Provided under [MIT license](LICENSE).