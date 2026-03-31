import pytest
from unittest.mock import MagicMock
from app.pipelines.callbacks import LoggingCallbacks, add_session_to_memory

@pytest.mark.asyncio
async def test_add_session_to_memory_success():
    context = MagicMock()
    # It needs to be an async mock
    from unittest.mock import AsyncMock
    context.add_session_to_memory = AsyncMock()
    
    await add_session_to_memory(context)
    context.add_session_to_memory.assert_awaited_once()

def test_logging_callbacks_init():
    callbacks = LoggingCallbacks()
    assert callbacks.logger is not None

def test_logging_callbacks_before_agent():
    logger = MagicMock()
    callbacks = LoggingCallbacks(logger=logger)
    
    context = MagicMock()
    context.agent_name = "test-agent"
    context.invocation_id = "123"
    context.state.to_dict.return_value = {"key": "val"}
    
    user_content = MagicMock()
    user_content.model_dump.return_value = {"text": "hello"}
    context.user_content = user_content
    
    callbacks.before_agent(context)
    logger.info.assert_called()
    logger.debug.assert_called()

def test_logging_callbacks_after_agent():
    logger = MagicMock()
    callbacks = LoggingCallbacks(logger=logger)
    
    context = MagicMock()
    context.agent_name = "test-agent"
    context.invocation_id = "123"
    context.state.to_dict.return_value = {"key": "val"}
    
    user_content = MagicMock()
    user_content.model_dump.return_value = {"text": "hello"}
    context.user_content = user_content
    
    callbacks.after_agent(context)
    logger.info.assert_called()
    logger.debug.assert_called()

def test_logging_callbacks_before_model():
    logger = MagicMock()
    callbacks = LoggingCallbacks(logger=logger)
    
    context = MagicMock()
    llm_request = MagicMock()
    
    callbacks.before_model(context, llm_request)
    logger.debug.assert_called()

def test_logging_callbacks_after_model():
    logger = MagicMock()
    callbacks = LoggingCallbacks(logger=logger)
    
    context = MagicMock()
    llm_response = MagicMock()
    llm_response.usage = MagicMock()
    llm_response.usage.prompt_tokens = 10
    llm_response.usage.completion_tokens = 20
    llm_response.usage.total_tokens = 30
    
    callbacks.after_model(context, llm_response)
    logger.debug.assert_called()

def test_logging_callbacks_before_tool():
    logger = MagicMock()
    callbacks = LoggingCallbacks(logger=logger)
    
    tool = MagicMock()
    tool.name = "test_tool"
    tool_context = MagicMock()
    kwargs = {"arg": "val"}
    
    callbacks.before_tool(tool, kwargs, tool_context)
    logger.debug.assert_called()

def test_logging_callbacks_after_tool():
    logger = MagicMock()
    callbacks = LoggingCallbacks(logger=logger)
    
    tool = MagicMock()
    tool.name = "test_tool"
    args = {"arg": "val"}
    tool_context = MagicMock()
    tool_response = {"status": "success"}
    
    callbacks.after_tool(tool, args, tool_context, tool_response)
    logger.debug.assert_called()
