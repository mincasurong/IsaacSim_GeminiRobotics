"""Backward compatibility wrapper aliasing FrankaDualController to ConveyorDualController."""

try:
    from .conveyor_dual_controller import ConveyorDualController as FrankaDualController, main
except ImportError:
    from conveyor_dual_controller import ConveyorDualController as FrankaDualController, main

if __name__ == '__main__':
    main()
