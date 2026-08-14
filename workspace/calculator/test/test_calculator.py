import math
import sys
from pathlib import Path

import pytest

CODING = Path(__file__).parents[1] / "Coding"
sys.path.insert(0, str(CODING))

from calculator import (  # noqa: E402
    DEFAULT_STRATEGIES,
    CalculatorEngine,
    OperationStrategy,
    create_calculator,
)


@pytest.mark.parametrize(
    ("operation", "left", "right", "expected"),
    [
        ("add", 2.0, 3.0, 5.0),
        ("subtract", 7.0, 2.0, 5.0),
        ("multiply", 4.0, 2.5, 10.0),
        ("divide", 9.0, 2.0, 4.5),
        ("power", 2.0, 8.0, 256.0),
    ],
)
def test_standard_operations(operation, left, right, expected):
    calculator = create_calculator()

    assert calculator.calculate(operation, left, right) == expected


def test_history_contains_only_successful_operations_and_can_be_cleared():
    calculator = CalculatorEngine()

    calculator.calculate("add", 1.0, 2.0)
    with pytest.raises(ZeroDivisionError, match="divide by zero"):
        calculator.calculate("divide", 1.0, 0.0)

    history = calculator.get_history()
    assert len(history) == 1
    assert history[0].model_dump() == {
        "operation": "add",
        "left": 1.0,
        "right": 2.0,
        "result": 3.0,
    }
    calculator.clear_history()
    assert calculator.get_history() == ()


@pytest.mark.parametrize(
    ("operation", "left", "right"),
    [
        ("modulo", 1.0, 2.0),
        ("add", "1", 2.0),
        ("add", True, 2.0),
        ("add", math.inf, 2.0),
        ("add", math.nan, 2.0),
    ],
)
def test_invalid_inputs_are_rejected(operation, left, right):
    with pytest.raises(ValueError, match="invalid calculation request"):
        create_calculator().calculate(operation, left, right)


@pytest.mark.parametrize(("left", "right"), [(0.0, -1.0), (-2.0, 0.5), (10.0, 1000.0)])
def test_non_finite_or_non_real_power_results_are_rejected(left, right):
    with pytest.raises(ValueError, match="finite real result"):
        create_calculator().calculate("power", left, right)


class ConstantStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return 42.0


def test_strategies_are_injectable():
    strategies = dict(DEFAULT_STRATEGIES)
    strategies["add"] = ConstantStrategy()

    assert create_calculator(strategies).calculate("add", 1.0, 2.0) == 42.0


def test_strategy_configuration_is_validated():
    with pytest.raises(ValueError, match="missing operation strategies"):
        CalculatorEngine({})

    strategies = dict(DEFAULT_STRATEGIES)
    strategies["add"] = object()
    with pytest.raises(TypeError, match="OperationStrategy"):
        CalculatorEngine(strategies)


def test_default_strategies_are_immutable_and_required_operations_are_canonical():
    with pytest.raises(TypeError):
        DEFAULT_STRATEGIES["add"] = ConstantStrategy()

    strategies = dict(DEFAULT_STRATEGIES)
    strategies.pop("power")
    with pytest.raises(ValueError, match="missing operation strategies: power"):
        CalculatorEngine(strategies)


class InfiniteStrategy(OperationStrategy):
    def execute(self, left: float, right: float) -> float:
        return math.inf


def test_injected_strategy_cannot_record_non_finite_result():
    strategies = dict(DEFAULT_STRATEGIES)
    strategies["add"] = InfiniteStrategy()
    calculator = create_calculator(strategies)

    with pytest.raises(ValueError, match="result must be finite"):
        calculator.calculate("add", 1.0, 2.0)
    assert calculator.get_history() == ()


class AdversarialResultStrategy(OperationStrategy):
    def __init__(self, result):
        self.result = result

    def execute(self, left: float, right: float):
        return self.result


@pytest.mark.parametrize("result", [True, "3.0", None, 1 + 2j, math.nan, math.inf])
def test_injected_strategy_result_is_strictly_validated_and_not_recorded(result):
    strategies = dict(DEFAULT_STRATEGIES)
    strategies["add"] = AdversarialResultStrategy(result)
    calculator = create_calculator(strategies)

    with pytest.raises(ValueError, match="finite real number"):
        calculator.calculate("add", 1.0, 2.0)
    assert calculator.get_history() == ()
