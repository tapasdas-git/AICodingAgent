# Modular Expression Calculator

This isolated Python 3.11+ calculator evaluates complete arithmetic expressions
with exact `decimal.Decimal` arithmetic. Runtime code uses only the standard
library and never calls `eval`, `exec`, or another dynamic execution mechanism.

## Architecture

The public `Calculator` facade coordinates separate source validation,
tokenization, shunting-yard parsing, RPN evaluation, operation strategies, and
immutable history storage. The tokenizer and parser scan each expression once;
the evaluator processes each RPN token once, so normal evaluation is linear in
the number of tokens. Configuration limits bound expression length, token count,
operand count, and parenthesis depth.

Source modules are under `Coding/`, while all automated tests are under `test/`.

## Public API

Add `Coding/` to `PYTHONPATH`, then use the facade:

```python
from calculator import Calculator

calculator = Calculator()
result = calculator.calculate("2 + 3 * 4")
history = calculator.get_history()
calculator.clear_history()
```

`calculate(expression: str) -> Decimal` returns a `Decimal`. Each successful
call appends a frozen `HistoryEntry` containing the original expression, a
whitespace-normalized expression, result, and timezone-aware timestamp.
`get_history()` returns an immutable oldest-first tuple snapshot. Failed calls
are never recorded. `create_calculator()` is available as an equivalent factory
and accepts validated configuration and injectable registry, history, and clock.

## Operators and numeric behavior

The supported operators, from lowest to highest precedence, are:

1. `+` and `-`
2. `*` and `/`
3. unary `-` and `^`
4. parentheses (which group an expression explicitly)

Exponentiation and unary negation associate right-to-left. Other binary
operators associate left-to-right. Integers, decimals, whitespace, negative
values, parentheses, and arbitrarily nested parentheses within configured limits
are accepted. Because operands and results remain `Decimal` values, `0.1 + 0.2`
is exactly `Decimal("0.3")` under the active Decimal context.

## Validation errors

All expected failures use classes from `exceptions.py`. They distinguish empty
input, non-string input, invalid characters, unsupported operators, missing
operands or operators, invalid operator sequences or decimals, empty or
unbalanced parentheses, division by zero, trailing operators, invalid strategy
results, invalid configuration, and configured size-limit violations. Messages
identify the bad token or boundary without exposing an internal traceback as
public output.

## Adding an operator strategy

Subclass `OperatorStrategy`, declare a punctuation symbol, positive precedence,
`"left"` or `"right"` associativity, and implement `apply` with two Decimal
operands. Register the instance on a calculator; tokenizer and evaluator behavior
updates through the registry without editing their core logic:

```python
from decimal import Decimal
from operations import OperatorStrategy

class Maximum(OperatorStrategy):
    symbol, precedence, associativity = "@", 2, "left"

    def apply(self, *operands: Decimal) -> Decimal:
        return max(operands)

calculator.register_operator(Maximum())
assert calculator.calculate("2 @ 5") == Decimal("5")
```

Strategies must return a finite `Decimal`. Registration rejects invalid or
duplicate definitions unless replacement is explicitly requested.

## Running tests

From the repository root:

```bash
python -m pytest -q workspace/calculatorDemoGIT/test
```

The isolated suite covers every operator, precedence and associativity, Decimal
precision, unary negatives, nested parentheses, more than six and 100 operands,
all validation categories, history ordering/isolation, and custom strategies.
