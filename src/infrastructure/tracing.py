"""
OpenTelemetry tracing configuration for Azure AI Agents.

Centralizes tracing setup with support for:
- Azure Monitor (Application Insights)
- OpenAI SDK instrumentation
- Azure AI Agents instrumentation
- Console telemetry output for debugging
"""
import os
import sys
import logging

logger = logging.getLogger(__name__)


def setup_tracing() -> bool:
    """
    Configure OpenTelemetry tracing with Azure Monitor and AI Agents instrumentation.
    
    This follows the latest Azure AI Agent Service patterns from Microsoft docs.
    
    Returns:
        True if tracing was configured successfully, False otherwise.
    """
    try:
        # Avoid re-initializing tracing on reruns
        if os.environ.get("OTEL_CONFIGURED") == "true":
            logger.info("Tracing already configured; skipping re-initialization")
            return True

        from azure.ai.projects import AIProjectClient
        from azure.identity import (
            AzureCliCredential,
            VisualStudioCodeCredential,
            EnvironmentCredential,
            ManagedIdentityCredential,
            ChainedTokenCredential,
        )
        from azure.monitor.opentelemetry import configure_azure_monitor
        from azure.core.settings import settings
        from opentelemetry import trace
        
        # Get project endpoint
        project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
        if not project_endpoint:
            logger.warning("AZURE_AI_PROJECT_ENDPOINT not set - tracing disabled")
            return False
        
        credential = ChainedTokenCredential(
            EnvironmentCredential(),
            AzureCliCredential(),
            VisualStudioCodeCredential(),
            ManagedIdentityCredential(),
        )
        
        project_client = AIProjectClient(
            credential=credential,
            endpoint=project_endpoint,
        )
        
        # Get Application Insights connection string from project telemetry
        connection_string = project_client.telemetry.get_application_insights_connection_string()
        
        if not connection_string:
            logger.warning("No Application Insights connected - tracing disabled")
            return False
        
        logger.info("Retrieved Application Insights connection string from project")
        
        # Enable content recording for debugging (captures AI message content)
        # Note: This may capture sensitive data - disable in production
        os.environ["AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED"] = "true"
        os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "true"
        
        # Enable Azure SDK tracing
        settings.tracing_implementation = "opentelemetry"
        
        # Configure Azure Monitor with Application Insights
        configure_azure_monitor(
            connection_string=connection_string,
            enable_live_metrics=True,
        )
        
        logger.info("Azure Monitor configured with Application Insights")
        
        # Silence noisy loggers immediately after configure_azure_monitor
        logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.ERROR)
        logging.getLogger('azure.monitor.opentelemetry.exporter').setLevel(logging.WARNING)
        logging.getLogger('azure.monitor.opentelemetry.exporter.export._base').setLevel(logging.WARNING)
        
        # Instrument Azure AI Projects SDK (for agents.create_version, etc.)
        try:
            from azure.ai.projects.telemetry import AIProjectInstrumentor
            if os.environ.get("OTEL_PROJECTS_INSTRUMENTED") != "true":
                AIProjectInstrumentor().instrument()
                os.environ["OTEL_PROJECTS_INSTRUMENTED"] = "true"
                logger.info("Azure AI Projects SDK instrumentation enabled")
        except ImportError as e:
            logger.warning(f"azure-ai-projects telemetry not available: {e}")
        
        # Instrument Azure AI Agents SDK (for legacy agents if used)
        try:
            from azure.ai.agents.telemetry import AIAgentsInstrumentor
            if os.environ.get("OTEL_AGENTS_INSTRUMENTED") != "true":
                # Pass True to enable content recording in traces
                AIAgentsInstrumentor().instrument(enable_content_recording=True)
                os.environ["OTEL_AGENTS_INSTRUMENTED"] = "true"
                logger.info("Azure AI Agents SDK instrumentation enabled")
        except ImportError as e:
            logger.warning(f"azure-ai-agents telemetry not available: {e}")
        
        # Instrument OpenAI SDK (for responses.create() calls)
        try:
            from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
            if os.environ.get("OTEL_OPENAI_INSTRUMENTED") != "true":
                OpenAIInstrumentor().instrument()
                os.environ["OTEL_OPENAI_INSTRUMENTED"] = "true"
                logger.info("OpenAI SDK instrumentation enabled")
        except ImportError as e:
            logger.warning(f"opentelemetry-instrumentation-openai-v2 not installed: {e}")
        
        os.environ["OTEL_CONFIGURED"] = "true"
        logger.info("OpenTelemetry tracing configured successfully")
        return True
        
    except ImportError as e:
        logger.warning(f"Tracing packages not installed: {e}")
        return False
    except Exception as e:
        logger.warning(f"Failed to configure tracing: {e}")
        return False


def enable_console_telemetry():
    """
    Enable console telemetry output for debugging.
    
    This outputs trace information to stdout for local debugging
    without requiring Azure Monitor.
    """
    try:
        from azure.ai.agents.telemetry import enable_telemetry
        enable_telemetry(destination=sys.stdout)
        logger.info("Console telemetry enabled")
    except ImportError:
        logger.warning("azure-ai-agents telemetry not available for console output")


def get_tracer(name: str = __name__):
    """
    Get an OpenTelemetry tracer for manual span creation.
    
    Use this to create custom spans around your agent operations.
    
    Example:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("my_operation"):
            # Your code here
            pass
    
    Args:
        name: The name for the tracer (typically __name__)
        
    Returns:
        OpenTelemetry Tracer instance, or a no-op tracer if tracing not configured
    """
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        # Return a dummy tracer that does nothing
        class NoOpTracer:
            def start_as_current_span(self, name, **kwargs):
                class NoOpSpan:
                    def __enter__(self): return self
                    def __exit__(self, *args): pass
                    def set_attribute(self, *args): pass
                    def record_exception(self, *args): pass
                    def set_status(self, *args): pass
                return NoOpSpan()
        return NoOpTracer()
