"""Dynamic scenario decorator module for system tests.

This module provides a decorator that allows specifying mandatory weblog environment variables
for test scenarios, replacing the previous @scenarios annotations.
"""

import functools
from collections.abc import Callable



def dynamic_scenario(mandatory: dict[str, str]) -> Callable:
    """Decorator that creates a dynamic scenario with specified mandatory weblog environment variables.

    This decorator replaces the previous @scenarios.X annotations with a more flexible approach
    that explicitly declares the required environment variables for each test scenario.

    Args:
        mandatory: Dictionary of environment variables that must be set for the weblog
                  in this scenario. Keys are environment variable names and values are their values.

    Returns:
        A decorator function that can be applied to test classes.

    """

    def decorator(cls: type) -> type:
        # Store the mandatory environment variables on the class
        cls._weblog_env_mandatory = mandatory

        # Create a dynamic scenario class for this specific test
        class_name = f"DynamicScenario_{cls.__name__}"

        # Get the original __init__ method
        original_init = cls.__init__

        # Define a new __init__ method that sets up the weblog environment
        @functools.wraps(original_init)
        def new_init(self, *args, **kwargs):
            # Set up the weblog environment with the mandatory variables
            if hasattr(self, "weblog_env") and isinstance(self.weblog_env, dict):
                for key, value in mandatory.items():
                    if value != "None":  # Skip None values
                        self.weblog_env[key] = value

            # Call the original __init__ method
            original_init(self, *args, **kwargs)

        # Replace the __init__ method
        cls.__init__ = new_init

        return cls

    return decorator
