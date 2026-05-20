# General Service - Logging Instructions for API/Function Calls

This document provides instructions for implementing logging and exception handling in every API endpoint and function in a general-purpose service.

## Core Requirements

### 1. Docstring Format

Every function/API must have a docstring that includes:

- **General Description**: Explains the function/API's purpose
- **Processing Steps**: Numbered list outlining all steps performed

**Required format example:**
```python
"""
Brief description of what this function/API does.

This function/API is used for [general description of purpose].

Processing Steps:
Step 1: [Description of step 1]
Step 2: [Description of step 2]
Step 3: [Description of step 3]
...
"""
```

### 2. Exception Handling Structure

Every function or API must contain:

1. **Outer Try-Except Block**: Wraps the entire function
2. **Step-Level Try-Except Blocks**: Used only for API calls or external service calls
3. **Start Logging**: Log immediately at function entry
4. **End Logging**: Log either before return (on success) or in exception handler (on failure)

### 3. Logging at Each Step

For every step listed in the docstring:
- **Business logic steps**: Do _not_ wrap in try-except; exceptions should propagate to the outer block
- **API call steps**: MUST be wrapped in a try-except block
- Log before executing API/external calls
- Log after successful API/external call
- Log on errors if an API call fails

### 4. Logging Levels

Use these logging levels:
- **INFO**: Start/end/milestone events
- **DEBUG**: Step progress, interim details
- **WARNING**: Non-critical issues detected
- **ERROR**: Exceptions or operation failures
- **CRITICAL**: System-level or unrecoverable issues

## Log Format Structure

### Log Message Parameters

All log messages automatically include (via auto-detection):
- `time`: Timestamp
- `level`: Log level (`INFO`, `DEBUG`, `WARNING`, `ERROR`, `CRITICAL`)
- `service_name`: Service name configured for your project (default may be `"service"`)
- `object_name`: Automatically detected from class name (e.g., `"InstanceLauncher"`, `"HTTP_SERVER"`)
- `log_type`: Auto-detected as `"function"` for methods or `"api"` for endpoint handlers
- `name`: Automatically detected from function/method name

You only need to provide:
- `message`: Main log message (required)
- `**kwargs`: Additional key-value context (optional)

### Text Format

When the `logs-format` feature flag is set to `"text"` (the default):

**Format:**
```
[timestamp] | level | {service_name}.{object_name}.{log_type}.{name} | key:value pairs | main_message
```

**Example:**
```
[2025-12-17 20:18:46] | INFO | service.InstanceLauncher.function.create_record | offer_id:12345 | machine_id:67890 | docker_image:image:tag | Function started
```

**Structure:**
- `[timestamp]`: `[YYYY-MM-DD HH:MM:SS]`
- `level`: `INFO`, `DEBUG`, `WARNING`, `ERROR`, `CRITICAL`
- `{service_name}.{object_name}.{log_type}.{name}`: Service, class, type, and function/action
- `key:value pairs`: Pipe-separated additional context
- `main_message`: Main descriptive log message

### JSON Format

When `logs-format` is set to `"json"`:

**Format:**
```json
{
  "time": "2025-12-17T20:18:46.123456",
  "level": "INFO",
  "service_name": "service",
  "object_name": "InstanceLauncher",
  "log_type": "function",
  "name": "create_record",
  "message": "Function started",
  "offer_id": "12345",
  "machine_id": "67890",
  "docker_image": "image:tag"
}
```

**Note:** `object_name`, `log_type`, and `name` are automatically set by the logger; do not supply them manually.

## Implementation Pattern

### Function Template

```python
async def function_name(self, param1, param2):
    """
    Brief description of what this function does.

    This function is used for [general description].

    Processing Steps:
    Step 1: [Description of step 1 - business logic]
    Step 2: [Description of step 2 - API call]
    Step 3: [Description of step 3 - business logic]
    """
    try:
        # ✅ Log function start - object_name, log_type, and name are auto-detected
        await self.logger.info(
            "Function started",
            param1=param1,
            param2=param2
        )

        # Step 1: Business logic (no try-except)
        await self.logger.debug("Starting step 1: [description]")

        # Step 1 logic (no try-except)
        step1_result = perform_step1()

        await self.logger.debug("Step 1 completed", step1_result=step1_result)

        # Step 2: API call (must use try-except)
        try:
            await self.logger.debug("Starting step 2: [API call description]")

            # Actual API call
            step2_result = await api_call(step1_result)

            await self.logger.debug("Step 2 completed", step2_result=step2_result)
        except Exception as e:
            await self.logger.error(
                "Error in step 2: [API call description]",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

        # Step 3: Business logic (no try-except)
        await self.logger.debug("Starting step 3: [description]")

        # Step 3 logic (no try-except)
        result = process_result(step2_result)

        await self.logger.debug("Step 3 completed", result=result)

        # ✅ Log successful completion
        await self.logger.info("Function ended successfully", result=result)

        return result

    except Exception as e:
        # ✅ Log exception at function level (includes API and business logic errors)
        await self.logger.error(
            "Function ended with exception",
            error=str(e),
            error_type=type(e).__name__
        )
        raise  # or return error_response
```

## Compliance Criteria

### Function/API Compliance Checklist

Every function/API must satisfy **all** of the following to be considered **fully compliant**:

#### ✅ **Docstring** 
- Contains a complete docstring with:
  - A general description of the function/API
  - A numbered list of processing steps (`Step 1`, `Step 2`, etc.)
  - Each step clearly and explicitly described

#### ✅ **Whole Function Error Handling**
- Entire function wrapped in an outer `try-except` block
- Outer except block logs function-level exceptions
- Exceptions must be re-raised (not silenced)

#### ✅ **Function Start Log**
- Log at function entry (immediately upon entering)
- Use `INFO` level (`log_type` auto-detected as `"function"` or `"api"`)
- Include all relevant input parameters as kwargs
- Message should be `"Function started"` or `"API call started"`
- **Note:** Only supply message and kwargs—object/class/function context is auto-detected

#### ✅ **Function End Log**
- Log before every return (on success) or in the exception handler (on error)
- On success: `INFO` with message `"Function ended successfully"`
- On error: `ERROR` with message `"Function ended with exception"`
- Include all relevant outputs/results as kwargs

#### ✅ **Proper Exception Handling in Steps**
- **Only** API/external calls are individually wrapped in `try-except`
- **Business logic** should _not_ be individually wrapped—those exceptions propagate to the main block
- API call try-except requirements:
  - Log before the API/external call (`DEBUG`)
  - Log after successful API/external call (`DEBUG`)
  - Log errors in except block (`ERROR`), including `error` and `error_type`
  - Always re-raise exceptions
- Let business logic step exceptions propagate outward

### Compliance Levels

| Level | Criteria Met | Status                  |
|-------|--------------|------------------------|
| **Fully Compliant**   | All 5 criteria         | ✅ Production Ready      |
| **Partially Compliant**| 3-4 criteria           | ⚠️ Needs Improvement    |
| **Non-Compliant**     | 0-2 criteria           | ❌ Must Be Fixed        |

### Common Non-Compliance Issues

1. **Missing Docstring**: Docstring lacks detailed processing steps
2. **No Outer Try-Except**: Function has no error-handling wrapper
3. **Missing Start Log**: No entry log at function entry point
4. **Missing End Log**: No log before return or on exception
5. **Wrong Exception Pattern**: Wrapping business logic or not wrapping API calls
6. **Incomplete Logging**: Critical log points missing

### Example Compliant Function

```python
async def compliant_example(self, param1: str, param2: int):
    """
    Example of a fully compliant function.

    This function demonstrates proper logging and exception handling.

    Processing Steps:
    Step 1: Validate input parameters (business logic)
    Step 2: Make API call to external service (API call)
    Step 3: Process API response (business logic)
    """
    try:
        # ✅ Start log
        await self.logger.info(
            "Function started",
            param1=param1,
            param2=param2
        )

        # Step 1: Business logic (do not wrap)
        await self.logger.debug("Starting step 1: Validate input parameters")

        if not param1:
            raise ValueError("param1 cannot be empty")  # Exception propagates outward

        await self.logger.debug("Step 1 completed")

        # Step 2: API call (must wrap)
        try:
            await self.logger.debug("Starting step 2: Make API call")

            response = await self.external_api_call(param1, param2)

            await self.logger.debug("Step 2 completed", response_status=response.status_code)
        except Exception as e:
            await self.logger.error(
                "Error in step 2: API call failed",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

        # Step 3: Business logic (do not wrap)
        await self.logger.debug("Starting step 3: Process response")

        result = process_response(response)  # Can raise, propagates outward

        await self.logger.debug("Step 3 completed", result=result)

        # ✅ End log (success)
        await self.logger.info("Function ended successfully", result=result)

        return result

    except Exception as e:
        # ✅ End log (error)
        await self.logger.error(
            "Function ended with exception",
            error=str(e),
            error_type=type(e).__name__
        )
        raise
```

## Logger Methods (Auto-Detection)

You must use the logger as `self.logger` (do **not** use `self.vastai_logger`):

```python
await self.logger.info(message, **kwargs)
await self.logger.debug(message, **kwargs)
await self.logger.warning(message, **kwargs)
await self.logger.error(message, **kwargs)
await self.logger.critical(message, **kwargs)
```

**Parameters:**
- `message` (`str`): Main log message (required)
- `**kwargs`: Additional context as key-value pairs (optional)

**Auto-Detected Information:**
- `object_name`: Detected from `self.__class__.__name__`
- `log_type`: `"function"` for class methods, `"api"` for endpoint handlers
- `name`: From calling function/method

### Examples

**Simple log:**
```python
await self.logger.info("Function started")
```

**Log with context:**
```python
await self.logger.info(
    "Function started",
    instance_id=instance_id,
    status="processing"
)
```

**Debug log with details:**
```python
await self.logger.debug(
    "Step 1 completed",
    step1_result=step1_result,
    items_processed=len(results)
)
```

**Error log with exception details:**
```python
await self.logger.error(
    "Function ended with exception",
    error=str(e),
    error_type=type(e).__name__,
    instance_id=instance_id
)
```

## Log Type Detection

The logger sets `log_type` automatically:
- `"function"`: Class methods
- `"api"`: API route handlers

## Object Name Detection

Class name is set automatically as `object_name`:
- `InstanceLauncher` → `"InstanceLauncher"`
- `HTTP_SERVER` → `"HTTP_SERVER"`
- etc.

The logger uses `self.__class__.__name__`.

## Important Notes

- All logger methods are **async**—always **await** them
- Logger writes to **stdout** (not files)
- Default format is **"text"** unless otherwise configured
- `object_name`, `log_type`, and function name are **auto-detected**
- Always log `error_type=type(e).__name__` in error logs
- Log relevant context (params, IDs, results); never log sensitive data (passwords, secrets, etc.)
- Logger uses `inspect.currentframe()` for accurate function context, even with nested calls

---

## Migration from Old Format

If updating code from older, manual-style logging:

**Old format (manual parameters):**
```python
await self.logger.info(
    "instanceLauncher",
    LogType.FUNCTION,
    "get_instance_information",
    "Function started",
    instance_id=instance_id
)
```

**New format (auto-detection):**
```python
await self.logger.info(
    "Function started",
    instance_id=instance_id
)
```

**Migration Checklist:**
1. Remove `object_name` parameter (it's auto-detected)
2. Remove the explicit log type parameter (`LogType.FUNCTION` or `LogType.API`)
3. Remove manual function name parameter
4. Keep only the `message` and `**kwargs`
5. All other message/context logic remains the same

Check `LOGGING_MIGRATION_TRACKER.md` for a detailed list of logging updates needed.

---

**Last Updated**: 2025-12-22  
**Version**: 2.0

