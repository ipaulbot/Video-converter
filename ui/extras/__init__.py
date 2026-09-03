"""Optional extras: the BallBuster XT easter-egg game.

Kept in its own package because it is roughly a tenth of the project (about
2,200 lines plus nine graphics and an audio file) serving a hidden feature. A
build that does not want it can exclude `ui.extras` without touching the app.

Import through this package rather than reaching for the module directly:

    from ui.extras import BallBusterWidget

`BallBusterWidget` is the game. It was previously exposed under two names --
`ui.snood_widget.SnoodWidget` and a one-line `ui.ballbuster_widget` alias
module that existed only to rename it. The alias module is gone; the class
keeps both names here for the same reason it had them, which is that the code
is a Snood clone and the product calls it BallBuster.
"""
from ui.extras.snood_widget import SnoodWidget
from ui.extras.snood_widget import SnoodWidget as BallBusterWidget

__all__ = ["BallBusterWidget", "SnoodWidget"]
