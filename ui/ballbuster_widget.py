"""BallBuster bubble-shooting Easter-egg widget.

This is simply an alias for the original SnoodWidget implementation so we
avoid duplicating 600+ lines of code.  Having a separate module and class name
lets the rest of the application refer to the game as BallBuster without
touching the core logic.
"""

# pylint: disable=invalid-name
from ui.snood_widget import SnoodWidget as BallBusterWidget
