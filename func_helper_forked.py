"""
Helper functions for func_helper.py - utilities for the async action/task framework
"""

import functools
from typing import Any, Callable, Optional, Dict, List
from Action import Action, swap_arg, action_result


class FuncHelper:
    """
    Provides utility functions for working with Action and Task objects
    """
    
    @staticmethod
    def safe_parse(func: Callable) -> Callable:
        """
        Wraps a parse function to handle exceptions gracefully
        
        Args:
            func: Parse function to wrap
            
        Returns:
            Wrapped function that returns original value on exception
        """
        @functools.wraps(func)
        def wrapper(value):
            try:
                return func(value)
            except Exception as e:
                print(f"Parse error in {func.__name__}: {e}")
                return {"result": value}
        return wrapper
    
    @staticmethod
    def safe_check(func: Callable) -> Callable:
        """
        Wraps a check function to handle exceptions gracefully
        
        Args:
            func: Check function to wrap
            
        Returns:
            Wrapped function that returns False on exception
        """
        @functools.wraps(func)
        def wrapper(value):
            try:
                return func(value)
            except Exception as e:
                print(f"Check error in {func.__name__}: {e}")
                return False
        return wrapper
    
    @staticmethod
    def retry_action(func: Callable, max_retries: int = 3) -> Callable:
        """
        Creates a wrapper function that retries on failure
        
        Args:
            func: Function to retry
            max_retries: Maximum number of retries
            
        Returns:
            Wrapped function with retry logic
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    print(f"Attempt {attempt + 1} failed: {e}. Retrying...")
            return None
        return wrapper
    
    @staticmethod
    def log_action(action_name: str) -> Callable:
        """
        Decorator to log action execution
        
        Args:
            action_name: Name of the action for logging
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                print(f"[LOG] Executing action: {action_name}")
                try:
                    result = func(*args, **kwargs)
                    print(f"[LOG] Action {action_name} completed successfully")
                    return result
                except Exception as e:
                    print(f"[LOG] Action {action_name} failed with error: {e}")
                    raise
            return wrapper
        return decorator
    
    @staticmethod
    def validate_args(expected_types: Dict[str, type]) -> Callable:
        """
        Decorator to validate function arguments
        
        Args:
            expected_types: Dict mapping arg names to expected types
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                for key, expected_type in expected_types.items():
                    if key in kwargs:
                        if not isinstance(kwargs[key], expected_type):
                            raise TypeError(
                                f"Argument '{key}' expected {expected_type.__name__}, "
                                f"got {type(kwargs[key]).__name__}"
                            )
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def chain_actions(actions: List[Action]) -> Callable:
        """
        Creates a function that chains multiple actions together
        
        Args:
            actions: List of Action objects to chain
            
        Returns:
            Function that executes all actions in sequence
        """
        def chained_executor(*args, **kwargs):
            result = None
            for action in actions:
                result = action.execute(*args, **kwargs)
                if not result.success:
                    return action_result(False, result.value)
                # Use result as input to next action
                args = (result.value,)
            return result
        return chained_executor
    
    @staticmethod
    def conditional_action(condition: Callable, 
                          true_action: Action, 
                          false_action: Optional[Action] = None) -> Callable:
        """
        Creates a function that conditionally executes actions
        
        Args:
            condition: Function that returns True/False
            true_action: Action to execute if condition is True
            false_action: Action to execute if condition is False
            
        Returns:
            Function that executes based on condition
        """
        def conditional_executor(*args, **kwargs):
            if condition(*args, **kwargs):
                return true_action.execute(*args, **kwargs)
            elif false_action:
                return false_action.execute(*args, **kwargs)
            return action_result(True, None)
        return conditional_executor
    
    @staticmethod
    def parallel_actions(actions: List[Action], async_handler) -> Callable:
        """
        Creates a function that executes actions in parallel (requires async_handler)
        
        Args:
            actions: List of Action objects to execute in parallel
            async_handler: Async_handler instance for concurrent execution
            
        Returns:
            Function that executes all actions in parallel
        """
        def parallel_executor(*args, **kwargs):
            results = {}
            for i, action in enumerate(actions):
                action.async_handler = async_handler
                results[i] = action.execute(*args, **kwargs)
            
            # Check all succeeded
            all_success = all(r.success for r in results.values())
            return action_result(all_success, results)
        return parallel_executor
    
    @staticmethod
    def default_error_handler(action_name: str, error: Exception) -> None:
        """
        Default error handler for actions
        
        Args:
            action_name: Name of the action that failed
            error: The exception that occurred
        """
        import traceback
        error_msg = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        print(f"\n{'='*60}")
        print(f"ACTION FAILED: {action_name}")
        print(f"{'='*60}")
        print(error_msg)
        print(f"{'='*60}\n")
    
    @staticmethod
    def default_success_handler(action_name: str, value: Any) -> None:
        """
        Default success handler for actions
        
        Args:
            action_name: Name of the action that succeeded
            value: The result value from the action
        """
        print(f"[SUCCESS] {action_name}: {value}")
