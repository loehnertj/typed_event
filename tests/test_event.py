import pytest
import inspect
from unittest.mock import Mock
from typed_event import Event, event, CancelEvent

# TBD:
# binding to class event:
# XXX: Expectation? Should invoke both on Cls.foo and instance.foo?
# XXX: how about subclassing, invoke for all subclasses?
# How should the self parameter work?


@pytest.fixture
def ev1():
    @event
    def ev1():
        """Event 1"""

    return ev1


@pytest.fixture
def ev2():
    @event(strict=False, exceptions="raise")
    def ev2(a: int):
        """Event 2"""

    return ev2


@pytest.fixture
def Cls():
    class Cls:
        # Tell type checkers that this event-like method does not receive an
        # implicit self argument. Keep `@staticmethod` closest to the function,
        # so `@event` remains the descriptor that creates bound copies.
        @event
        @staticmethod
        def ev1(*, a: int):
            pass

        @event
        def ev2(self, /, *, a: int):
            pass

    return Cls


def test_no_runtime_check_of_handler_signature():
    """Handlers with wrong signature can be subscribed."""

    @event(exceptions="group")
    def ev(*, a: int):
        pass

    # No error at subscription time, even though handler has wrong signature.
    # Type checkers will flag this as error.
    ev += lambda: None  # type:ignore
    ev += lambda b: None  # type:ignore
    # This is actually OK, since the default arg value makes it compatible with the prototype's signature. The handler will receive a=1 when invoked.
    ev += lambda a, b=1: None
    with pytest.raises(ExceptionGroup):
        ev(a=1)


def test__event_docstring(ev1):
    """Docstring is passed through"""
    assert ev1.__doc__ == "Event 1"


def test_event_signature():
    """parameter names and annotations are passed"""

    @event
    def ev(*, a: int):
        pass

    sig = inspect.signature(ev)
    assert len(sig.parameters) == 1
    p = sig.parameters["a"]
    assert p.name == "a"
    assert p.annotation is int


def test_event_signature_check(ev2):
    """Calling event with bad parameters raises TypeError"""
    ev = ev2

    with pytest.raises(TypeError):  # a is missing
        ev()
    with pytest.raises(TypeError):  # b is extra
        ev(1, b=1)
    with pytest.raises(TypeError):  # 2, 3 are extra
        ev(1, 2, 3)
    # This does not constitute an error, since type hints are not enforced.
    ev("not an integer")
    # Can use kwarg syntax as well
    ev(a=1)


@pytest.mark.parametrize(
    "handler,iserror",
    [
        (lambda a, b: None, True),
        (lambda a, b=1: None, False),
        # args are passed as given. Use *, / in signature to make clear what is passed.
        (lambda *args: None, False),
        (lambda **kwargs: None, True),
        # a is missing
        (lambda b, c: None, True),
    ],
)
def test_event_handler_signature(ev2, handler, iserror):
    """Event *handler* signature is not enforced when subscribing.

    Handler with wrong signature will raise TypeError when invoked.

    Handler may specify additional params with default value, and/or catch
    values in ``**kwargs``.
    """
    # Never fails
    ev2 += handler
    if iserror:
        with pytest.raises(TypeError):
            ev2(1)
    else:
        ev2(1)


def test_event_str(ev1, Cls):
    o = Cls()
    assert str(ev1) == "<Unbound Event ev1.<locals>.ev1()>"
    assert str(Cls.ev1) == "<Unbound Event Cls.<locals>.Cls.ev1(a)>"
    assert str(Cls.ev2) == "<Unbound Event Cls.<locals>.Cls.ev2(self, a)>"
    assert str(o.ev1) == "<Bound Event Cls.<locals>.Cls.ev1(a)>"
    assert str(o.ev2) == "<Bound Event Cls.<locals>.Cls.ev2(self, a)>"


def test_event_no_kwarg():
    """Cannot define event with kwargs"""
    with pytest.raises(TypeError):

        @event
        def ev(kwarg=1):
            pass


def test_event_no_args():
    """Cannot define event with *args"""
    with pytest.raises(TypeError):

        @event
        def ev(*args):
            pass


def test_event_no_kwargs():
    """Cannot define event with **kwargs"""
    with pytest.raises(TypeError):

        @event
        def ev(**kwargs):
            pass


def test_module_event_fire(ev1):
    """Module-level event notification works in principle"""
    ev1 += (m := Mock())
    ev1()
    m.assert_called_with()


def test_event_force_namedargs():
    """If signature forces named args, ev cannot be called with positional args.

    Handlers get indeed passed named args.
    """

    @event
    def ev(*, a, b):
        pass

    ev += (m := Mock())
    with pytest.raises(TypeError):
        ev(1, 2)  # type:ignore
    ev(a=1, b=2)
    m.assert_called_with(a=1, b=2)


def test_event_posargs():
    """If signature forces positional args, ev cannot be called with named args.

    Handlers get indeed passed positional args.
    """

    @event
    def ev(a, b, /):
        pass

    ev += (m := Mock())
    with pytest.raises(TypeError):
        ev(a=1, b=2)  # type:ignore
    ev(1, 2)
    m.assert_called_with(1, 2)


def test_class_event_fire(Cls):
    """Object-level event notification works in principle"""
    o = Cls()
    o.ev1 += (m := Mock())
    o.ev1(a=1)
    m.assert_called_with(a=1)


def test_class_handler_separation(Cls):
    """Instances have separate handler lists"""
    o1 = Cls()
    o2 = Cls()
    o1.ev1 += (m1 := Mock())
    o2.ev1 += (m2 := Mock())
    o1.ev1(a=1)
    o2.ev1(a=2)
    m1.assert_called_once_with(a=1)
    m2.assert_called_once_with(a=2)


def test_event_copy_instance(Cls):
    """event can be copied from one instance to another (retaining handlers)"""
    o1 = Cls()
    o2 = Cls()
    o1.ev1 += (m1 := Mock())
    o2.ev1 = o1.ev1
    assert o2.ev1 is o1.ev1
    o2.ev1(a=2)
    m1.assert_called_once_with(a=2)
    o1.ev1 -= m1
    o2.ev1(a=1)
    m1.assert_called_once_with(a=2)


def test_class_self_handling(Cls):
    """self argument is not allowed"""
    o = Cls()

    with pytest.raises(TypeError):
        Cls.ev2(a=1)
    with pytest.raises(TypeError):
        o.ev2(a=2)
    o.ev2(o, a=3)


def test_staticmethod_event_outermost():
    """@staticmethod wrapping @event breaks descriptor protocol: instances share handlers.

    When @staticmethod is the outer decorator, Cls.ev returns the unwrapped function,
    bypassing the Event descriptor's __get__ that creates bound copies. This causes
    all instances to share the same listener list instead of having separate ones.
    This demonstrates what NOT to do.
    """

    class Cls:
        @staticmethod
        @event
        def ev(*, a: int):
            pass

    o1 = Cls()
    o2 = Cls()
    o1.ev += (m1 := Mock(return_value=None))
    o2.ev += (m2 := Mock(return_value=None))

    # Both instances share the same listener list because the descriptor
    # protocol was bypassed. Calling either fires both handlers.
    o1.ev(a=1)
    m1.assert_called_once_with(a=1)
    m2.assert_called_once_with(a=1)  # Both handlers fire! This is wrong.


def test_staticmethod_event_innermost():
    """@event can wrap @staticmethod."""

    class Cls:
        @event
        @staticmethod
        def ev(*, a: int):
            pass

    Cls.ev += (m := Mock())
    Cls.ev(a=1)
    m.assert_called_once_with(a=1)


def test_exception_policy_log(caplog):
    """log policy logs errors and continues with later listeners."""

    @event(exceptions="log")
    def ev(a: int, /):
        pass

    def bad(a: int):
        raise ValueError("boom")

    good = Mock()
    ev += bad
    ev += good

    with caplog.at_level("ERROR"):
        ev(1)

    good.assert_called_once_with(1)
    # Check that the exception was logged with its traceback
    assert len(caplog.records) > 0
    assert any(
        record.exc_info and "boom" in str(record.exc_info[1])
        for record in caplog.records
    )


def test_exception_policy_default(capsys):
    """default policy passes exception to sys.excepthook and continues with later listeners."""

    @event(exceptions="default")
    def ev(a: int, /):
        pass

    def bad(a: int):
        raise ValueError("boom")

    good = Mock()
    ev += bad
    ev += good
    ev(1)

    captured = capsys.readouterr()
    good.assert_called_once_with(1)
    assert "ValueError: boom" in captured.err


def test_exception_policy_raise():
    """raise policy re-raises immediately and stops later listeners."""

    @event(exceptions="raise")
    def ev(a: int, /):
        pass

    def bad(a: int):
        raise ValueError("boom")

    good = Mock()
    ev += bad
    ev += good

    with pytest.raises(ValueError, match="boom"):
        ev(1)

    good.assert_not_called()


def test_exception_policy_group():
    """group policy runs all listeners and raises ExceptionGroup afterwards."""

    @event(exceptions="group")
    def ev(a: int, /):
        pass

    def bad1(a: int):
        raise ValueError("v")

    def bad2(a: int):
        raise RuntimeError("r")

    good = Mock()
    ev += bad1
    ev += good
    ev += bad2

    with pytest.raises(ExceptionGroup) as excinfo:
        ev(1)

    good.assert_called_once_with(1)
    assert len(excinfo.value.exceptions) == 2
    assert isinstance(excinfo.value.exceptions[0], ValueError)
    assert isinstance(excinfo.value.exceptions[1], RuntimeError)


@pytest.mark.parametrize("policy", ["log", "default", "raise", "group"])
def test_cancel_event_bypasses_exception_policy(policy, caplog, capsys):
    """CancelEvent is not treated as an error for any exception policy."""

    @event(exceptions=policy)
    def ev(a: int, /):
        pass

    def stop(a: int):
        raise CancelEvent()

    never_called = Mock()
    ev += stop
    ev += never_called

    with caplog.at_level("ERROR"):
        ev(1)

    never_called.assert_not_called()
    if policy == "log":
        assert caplog.records == []
    if policy == "default":
        captured = capsys.readouterr()
        assert captured.err == ""


def test_invalid_exception_policy():
    """Passing an unknown exception policy raises ValueError at definition time."""
    with pytest.raises(ValueError):

        @event(exceptions="invalid")  # type:ignore
        def ev(a: int, /):
            pass


def test_strict_mode_rejects_positional_or_keyword():
    """strict=True raises TypeError when args are neither pos-only nor kw-only."""
    with pytest.raises(TypeError):

        @event(strict=True)
        def ev(a: int, b: int):
            pass


def test_strict_mode_allows_posonly_and_kwonly():
    """strict=True accepts pos-only and kw-only args (in separate events)."""

    @event(strict=True)
    def ev_pos(a: int, /):
        pass

    @event(strict=True)
    def ev_kw(*, a: int):
        pass


def test_single_handler_return_value():
    """Return value from the one handler that returns non-None is passed through."""

    @event
    def ev(a: int, /):
        pass

    ev += lambda a: a * 2

    result = ev(21)
    assert result == 42


def test_prototype_return_value_raises():
    """RuntimeError is raised when the prototype itself returns non-None."""

    @event
    def ev(a: int, /):
        return a

    with pytest.raises(RuntimeError):
        ev(1)


def test_multiple_return_values_raise():
    """RuntimeError is raised when more than one handler returns a non-None value."""

    @event
    def ev(a: int, /):
        pass

    ev += lambda a: a
    ev += lambda a: a * 2

    with pytest.raises(RuntimeError):
        ev(1)


def test_use_parameterized():
    """myevent = event(strict=False, exceptions="log") can be (re)used to change defaults for multiple events."""

    myevent = event(strict=False, exceptions="log")

    @myevent
    def ev1(a: int, b: int, /):
        pass

    @myevent
    def ev2(a: int, b: int, /):
        pass

    # Both events should have the same defaults
    assert ev1._strict == False
    assert ev1._exceptions == "log"
    assert ev2._strict == False
    assert ev2._exceptions == "log"
